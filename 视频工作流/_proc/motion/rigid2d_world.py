# 契约: proc/motion/rigid2d_world
#   一句话: World：接触生成、休眠、积分与位置松弛（物理主循环）
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""World：接触生成、休眠、积分与位置松弛（物理主循环）

由 motion/rigid2d.py 按层切出（常量/几何 ← 碰撞 ← 求解 ← World ← 仿真）。
出处与公式同 rigid2d（Erin Catto GDC2006 顺序冲量 / Box2D b2_common 常量）。
"""
import os as _os, sys as _sys, math as _math
if __package__ in (None, ""):
    _d = _os.path.dirname(_os.path.abspath(__file__))
    while _d != _os.path.dirname(_d) and _os.path.basename(_d) != "_proc":
        _d = _os.path.dirname(_d)
    for _p in (_os.path.dirname(_d), _d):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    __package__ = _os.path.relpath(
        _os.path.dirname(_os.path.abspath(__file__)), _d).replace(_os.sep, ".")

import math
import numpy as np

from .rigid2d_core import (  # noqa: F401
    SLOP, BETA, SLEEP_LIN, SLEEP_ANG, SLEEP_TIME, WAKE_VN, POS_PERCENT, _ZERO, MAX_LIN_CORR, ITER, rot, cross, cross_w, Body2,
)
from .rigid2d_collide import (  # noqa: F401
    _ANCHOR,  # 世界锚点（静态、零半径）
    collide_box_box, collide_box_box_np, collide_ground, collide_seg,
    _clip_face, _inside_obb, _round_pair, Segment2,
)
from .rigid2d_solve import (  # noqa: F401
    Contact, solve, _prepare, _apply,
)

class World:
    """定步长世界：重力积分 + 碰撞生成 + 求解 + 位置修正"""

    def __init__(self, g=9.80665, dt=1.0 / 60.0, gy=0.0, iters=ITER,
                 diag_every=1, relax_iters=4):
        self.diag_every = diag_every
        self.relax_iters = relax_iters
        self._diag_n = 0
        self.g = g
        self.dt = dt
        self.gy = gy
        self.iters = iters
        self.bodies = []
        self.segments = []
        self.constraints = []
        self.max_pen = 0.0
        self.peak_pen = 0.0
        self._cache = {}   # 持久流形：{(id(a),id(b),fid): (Pn,Pt)}

    def add(self, b):
        self.bodies.append(b)
        return b

    def add_segment(self, seg):
        self.segments.append(seg)
        return seg

    def step(self):
        dt = self.dt
        for b in self.bodies:
            if not b.fixed:
                b.v[1] -= self.g * dt
        cs = self._contacts()
        self._wake(cs)
        # 撞击瞬间的瞬时重叠（求解前），仅作诊断
        self.peak_pen = max([c.pen for c in cs], default=0.0)
        if cs:
            solve(cs, dt, self.iters)
            # 求解后写回：暖启动要的是"上帧求解收敛后的冲量"，
            # 若在生成接触时就存，存进去的恒为 0，等于没接上流形。
            agg = {}
            for c in cs:
                agg.setdefault((id(c.a), id(c.b)), []).append((c.Pn, c.Pt))
            self._cache = agg
        else:
            self._cache = {}
        for con in self.constraints:
            con(dt)
        self._integrate(dt)
        self._sleep_update(dt)
        self._relax(iters=self.relax_iters)
        # max_pen 取求解后的残余穿透：这是渲染出来的那一帧真正被看到的重叠。
        # 但完整 _contacts() 是窄相全对检测，每步白算一次只为诊断太贵
        # （实测占单步 1/6）。改为降频：diag_every=0 关闭，=N 每 N 步算一次。
        #   出处：Box2D-Lite World::Step 全程只 BroadPhase() 一次，
        #   诊断量不属于求解路径，不应每步重算。
        self._diag_n += 1
        if self.diag_every and self._diag_n % self.diag_every == 0:
            self.max_pen = max(
                [c.pen for c in self._contacts(write_cache=False)], default=0.0)
        return cs

    def _contacts(self, write_cache=True):
        """接触生成 + 持久流形暖启动（出处[1][6]。

        write_cache=False 用于诊断性重算（本帧末尾算 max_pen）：
        只读取已有冲量，绝不写回。step() 原先在末尾无条件重建接触，
        把求解收敛后的 Pn/Pt 覆盖成空槽 → 下一帧暖启动读到空列表，
        warm starting 全程空转，堆叠靠 Baumgarte 反复推离形成极限环。


        关键：接触必须跨帧匹配，把上一帧的累积冲量 Pn/Pt 带到本帧做初值。
        若每帧新建 Contact（Pn 归零），暖启动就是空转——堆叠会缓慢下沉、
        底层微抖，正是 Catto 2005 描述的"冷启动三箱塔滑开"现象。
        """
        cs = []
        n = len(self.bodies)
        new_cache = {}

        def _mk(a, b, q, nn, pen, fid):
            c = Contact(a, b, q, nn, pen, fid)
            # 按"物体对"聚合匹配：接触点 fid 会随微抖漂移导致漏配，
            # 配对级缓存更稳；同对多接触点时按序取用。
            key = (id(a), id(b))
            rev = (id(b), id(a))
            slot = new_cache.get(key, None)
            if slot is None:
                slot = []
                new_cache[key] = slot
            idx = len(slot)
            old = self._cache.get(key) or self._cache.get(rev) or []
            if idx < len(old):
                c.Pn, c.Pt = old[idx]
            return c

        # ── 宽相：包围圆快速排除 ────────────────────────────────────
        # 窄相 SAT 是 O(顶点数) 的 numpy 运算，81 体全对 = 3240 对/步，
        # 实测 1.43 s/步，90 秒长片要跑 8 小时。街道场景物体沿 X 铺开，
        # 包围圆一次平方距离比较能排掉 95% 以上，是收益最高的一步。
        # 包围圆是保守的（盒子旋转时外接圆必包含本体），不会漏接触。
        rad = {}
        for b in self.bodies:
            rad[id(b)] = _math.hypot(b.hw, b.hh) if b.shape == "box" else b.r
        # ── 宽相 0：空间哈希候选对 ──────────────────────────────────
        # 出处：Broadphase 标准做法（Box2D dynamic tree / 均匀网格空间哈希）。
        # 81 体暴力 = 3240 对/步，压力段 131 体 = 8555 对/步，实测 0.276 s/步，
        # 全片 21600 步要 100 分钟。只做候选对筛选、窄相一字不改，
        # 所以数值必须与暴力版逐位一致（自检已验）。
        # 正确性：AABB 相交 ⟺ 存在公共格子。两体 AABB 若相交，交集内任一点
        # 所在格子必被两者同时登记 → 该对必进候选，不会漏接触。
        cell = 1e-6
        for b in self.bodies:
            d = 2.0 * rad[id(b)]
            if d > cell:
                cell = d
        grid = {}
        for i, b in enumerate(self.bodies):
            r = rad[id(b)]
            x0 = int(_math.floor((b.p[0] - r) / cell))
            x1 = int(_math.floor((b.p[0] + r) / cell))
            y0 = int(_math.floor((b.p[1] - r) / cell))
            y1 = int(_math.floor((b.p[1] + r) / cell))
            for ix in range(x0, x1 + 1):
                for iy in range(y0, y1 + 1):
                    grid.setdefault((ix, iy), []).append(i)
        seen = set()
        cand = []
        for bucket in grid.values():
            m = len(bucket)
            if m < 2:
                continue
            for a in range(m):
                for c in range(a + 1, m):
                    i0, j0 = bucket[a], bucket[c]
                    if i0 > j0:
                        i0, j0 = j0, i0
                    k = i0 * n + j0
                    if k in seen:
                        continue
                    seen.add(k)
                    cand.append((i0, j0))
        cand.sort()
        for (i, j) in cand:
            A, B = self.bodies[i], self.bodies[j]
            if A.fixed and B.fixed:
                continue
            dx = A.p[0] - B.p[0]
            dy = A.p[1] - B.p[1]
            rr = rad[id(A)] + rad[id(B)]
            if dx * dx + dy * dy > rr * rr:
                continue
            if A.shape == "box" and B.shape == "box":
                for q, nn, pen, fid in collide_box_box(A, B):
                    cs.append(_mk(A, B, q, nn, pen, fid))
            else:
                for k, c in enumerate(_round_pair(A, B)):
                    c.fid = ("r", k)
                    cs.append(_mk(A, B, c.p, c.n, c.pen, c.fid))
        for b in self.bodies:
            if b.fixed:
                continue
            for k, (q, nn, pen) in enumerate(collide_ground(b, self.gy)):
                cs.append(_mk(_ANCHOR, b, q, nn, pen, ("g", k)))
            for si, sg in enumerate(self.segments):
                # 宽相：线段是静态的，AABB 只算一次（挂在 seg 上）。
                # 街道场景 8 根梯蹬 + 坡面 + 地形瓦片共 50 余段，
                # 若不做筛除就是 81×53 ≈ 4300 次 collide_seg/步，
                #  profiling 实测占全流程 57%（每个盒还要重算 4 个顶点）。
                ab = getattr(sg, "_aabb", None)
                if ab is None:
                    x0 = min(sg.a[0], sg.b[0])
                    x1 = max(sg.a[0], sg.b[0])
                    y0 = min(sg.a[1], sg.b[1])
                    y1 = max(sg.a[1], sg.b[1])
                    ab = (x0, x1, y0, y1)
                    sg._aabb = ab
                x0, x1, y0, y1 = ab
                rr = rad[id(b)] + sg.t
                px, py = float(b.p[0]), float(b.p[1])
                dx = (x0 - px) if px < x0 else (px - x1 if px > x1 else 0.0)
                dy = (y0 - py) if py < y0 else (py - y1 if py > y1 else 0.0)
                if dx * dx + dy * dy > rr * rr:
                    continue
                for k, (q, nn, pen) in enumerate(collide_seg(b, sg)):
                    cs.append(_mk(sg, b, q, nn, pen, ("s", si, k)))
        # 只保留本帧仍存在的接触，防止陈旧冲量复活
        if write_cache:
            self._cache = new_cache
        return cs

    def _wake(self, cs):
        """唤醒判定（出处[4]）：被来势较猛的物体压到、或穿透超 2*slop 时唤醒"""
        for c in cs:
            if not (getattr(c.a, "sleeping", False)
                    or getattr(c.b, "sleeping", False)):
                continue
            if c.pen > 2.0 * SLOP:
                for x in (c.a, c.b):
                    if hasattr(x, "sleeping"):
                        x.sleeping = False
                        x.sleep_t = 0.0
                continue
            dv = c.b.v - c.a.v
            if float(np.dot(dv, c.n)) < -WAKE_VN:
                for x in (c.a, c.b):
                    if hasattr(x, "sleeping"):
                        x.sleeping = False
                        x.sleep_t = 0.0

    def _sleep_update(self, dt):
        for b in self.bodies:
            if b.fixed:
                continue
            slow = (float(np.linalg.norm(b.v)) < SLEEP_LIN
                    and abs(b.w) < SLEEP_ANG)
            b.sleep_t = b.sleep_t + dt if slow else 0.0
            if b.sleep_t >= SLEEP_TIME:
                b.sleeping = True
                b.v[:] = 0.0
                b.w = 0.0

    def _integrate(self, dt):
        for b in self.bodies:
            if not b.fixed and not b.sleeping:
                b.p += b.v * dt
                b.th += b.w * dt

    def _relax(self, iters=4):
        """位置修正：非线性 Gauss-Seidel（Box2D SolvePositionConstraints）。

        只做线分离、不修正角度（Box2D 同款简化，角度由后续冲量收敛）。

        【性能优化｜解析穿透更新】
        原实现每轮迭代都完整重算 _contacts()——窄相全对检测，实测每步 6 次
        调用里有 4 次来自这里，单步 318 ms 中大部分烧在这。

        但本函数只做**平移**修正：接触点随体刚性平移、法线不变。于是穿透量
        的变化可以解析算出，不必重跑窄相：
            pen_new = pen_old - dot(n, Δp_b - Δp_a)
        这与重算窄相在数学上等价（同一刚体平移假设），却省掉 3 次全对检测。

        等价性自检见 self_check 的「解析穿透更新==重算窄相」。
        """
        cs = self._contacts()
        if not cs:
            return
        for _ in range(iters):
            moved = 0.0
            delta = {}
            for c in cs:
                a, b = c.a, c.b
                sm = a.inv_m + b.inv_m
                if sm <= 0.0:
                    continue
                d = POS_PERCENT * max(0.0, c.pen - SLOP) / sm
                # b2_maxLinearCorrection：限制单步位移修正量，防过冲（出处[2]）
                if d > MAX_LIN_CORR:
                    d = MAX_LIN_CORR
                if d <= 0.0:
                    continue
                moved = max(moved, d)
                va = -c.n * (d * a.inv_m)
                vb = c.n * (d * b.inv_m)
                if not a.fixed:
                    a.p = a.p + va
                    da = delta.get(id(a))
                    delta[id(a)] = va if da is None else da + va
                if not b.fixed:
                    b.p = b.p + vb
                    db = delta.get(id(b))
                    delta[id(b)] = vb if db is None else db + vb
            if not delta:
                return
            for c in cs:
                da = delta.get(id(c.a))
                db = delta.get(id(c.b))
                if da is None and db is None:
                    continue
                da = da if da is not None else _ZERO
                db = db if db is not None else _ZERO
                rel = db - da
                c.pen -= float(c.n[0] * rel[0] + c.n[1] * rel[1])
                c.p = c.p + 0.5 * (da + db)
            delta.clear()
            if moved < 1e-6:
                return
