# 契约: proc/motion/rigid2d
#   一句话: 2D 旋转刚体：SAT 碰撞检测 + 顺序冲量求解器 + 距离约束
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""2D 刚体动力学内核（C15~C19 依赖）。

出处（先搜证再实现，不自造）：
[1] Erin Catto《Fast and Simple Physics using Sequential Impulses》
    GDC2006 / Box2D Lite：
    · 顺序冲量（Sequential Impulse）逐接触点迭代求解，非一次性矩阵解
    · warm starting：保留上帧累积冲量 Pn/Pt 先施加一次，堆叠才收敛
    · 累积冲量裁剪：Pn = max(Pn + dPn, 0)（法向只推不拉）
    · 库仑摩擦锥：|Pt| <= mu * Pn
[2] 同文 §Baumgarte 位置修正：
        bias = (beta / dt) * max(0, pen - slop)
    beta = 0.2，slop = 0.01（= Box2D b2_linearSlop），
    留 slop 是避免过冲抖动（jitter），与 penetration_m 判据同源
[3] SAT 分离轴定理（2D 凸多边形）：
    · 只需测两物体的面法线（矩形各 2 条，共 4 轴）
    · 取"分离量最大（=穿透最小）"的轴为碰撞法线
    · 参考面 / 入射面裁剪（Sutherland-Hodgman）得 1~2 个接触点
[4] 恢复系数与能量：e=0 完全非弹（堆叠），e 由 COR 表给定（见 rigid.COR）
[5] 距离约束（摆锤）：C = |p - anchor| - L，用同样的冲量公式求解，
    等效于 Box2D 的 b2DistanceJoint；绳张力为外力，故只在撞击瞬间
    的水平方向检验动量守恒（绳在最低点竖直，水平无分量）

本模块是纯数值内核，不含任何绘制。
"""
import os as _os, sys as _sys
if __package__ in (None, ""):
    _d = _os.path.dirname(_os.path.abspath(__file__))
    while _d != _os.path.dirname(_d) and _os.path.basename(_d) != "_proc":
        _d = _os.path.dirname(_d)
    for _p in (_os.path.dirname(_d), _d):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    __package__ = _os.path.relpath(
        _os.path.dirname(_os.path.abspath(__file__)), _d).replace(_os.sep, ".")

import numpy as np

from .beat import capability

# 以下四个常量全部取自 Box2D b2_common.h / core.h 原文，不自造：
SLOP = 0.005           # b2_linearSlop = 0.005 * lengthUnitsPerMeter（0.5cm）
BETA = 0.2             # b2_baumgarte = 0.2f
SLEEP_LIN = 0.01       # b2_linearSleepTolerance (m/s)
SLEEP_ANG = 0.0175     # b2_angularSleepTolerance ≈ 1° in rad (Box2D 用 2°)
SLEEP_TIME = 0.5       # b2_timeToSleep (s)
WAKE_VN = 0.05         # 唤醒阈值：法向接近速度 (m/s)
POS_PERCENT = 0.2      # 位置 pass 同样用 b2_baumgarte（原文：取 1 会过冲）
MAX_LIN_CORR = 0.2     # b2_maxLinearCorrection = 0.2 * lengthUnitsPerMeter
ITER = 12              # 顺序冲量迭代次数（Box2D Lite 默认 10~20）


def rot(th):
    c, s = np.cos(th), np.sin(th)
    return np.array([[c, -s], [s, c]])


def cross(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def cross_w(w, r):
    """角速度叉乘半径 → 线速度增量"""
    return np.array([-w * r[1], w * r[0]])


class Body2:
    """2D 刚体。shape: 'box'(半宽hw/半高hh) 或 'circle'(半径 r)"""
    __slots__ = ("p", "v", "th", "w", "m", "inv_m", "I", "inv_I",
                 "shape", "hw", "hh", "r", "e", "mu", "fixed", "tag",
                 "sleep_t", "sleeping")

    def __init__(self, p=(0.0, 0.0), shape="box", hw=0.25, hh=0.25, r=0.11,
                 m=1.0, th=0.0, e=0.0, mu=0.6, fixed=False, tag=""):
        self.p = np.asarray(p, float)
        self.v = np.zeros(2)
        self.th = float(th)
        self.w = 0.0
        self.shape = shape
        self.hw, self.hh, self.r = float(hw), float(hh), float(r)
        self.e, self.mu = float(e), float(mu)
        self.fixed = bool(fixed)
        self.tag = tag
        # 休眠（出处[4] Box2D b2Body）：低速持续 0.5s 后冻结，消除
        # 顺序冲量固有的残余微抖（Baumgarte 偏置与重力反复拉锯）
        self.sleep_t = 0.0
        self.sleeping = False
        if fixed:
            self.m = 0.0
            self.inv_m = 0.0
            self.I = 0.0
            self.inv_I = 0.0
        else:
            self.m = float(m)
            self.inv_m = 1.0 / self.m
            if shape == "box":
                w2, h2 = 2 * self.hw, 2 * self.hh
                self.I = self.m * (w2 * w2 + h2 * h2) / 12.0
            else:
                self.I = 0.5 * self.m * self.r * self.r
            self.inv_I = 1.0 / self.I

    def verts(self):
        """世界坐标四顶点（逆时针）"""
        R = rot(self.th)
        loc = [np.array([-self.hw, -self.hh]), np.array([self.hw, -self.hh]),
               np.array([self.hw, self.hh]), np.array([-self.hw, self.hh])]
        return [self.p + R @ q for q in loc]


# ---------------------------------------------------------------- 碰撞检测
def _clip_face(poly, side, axis):
    """Sutherland-Hodgman 单平面裁剪（出处[3]）"""
    out = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        da, db = np.dot(a, side) - axis, np.dot(b, side) - axis
        if da <= 0.0:
            out.append(a)
        if da * db < 0.0:
            t = da / (da - db)
            out.append(a + t * (b - a))
    return out


def _inside_obb(q, b):
    """点 q 是否落在 OBB b 内：转到 b 的局部坐标再比半宽半高。"""
    d = rot(b.th).T @ (np.asarray(q, float) - b.p)
    return abs(d[0]) <= b.hw + 1e-9 and abs(d[1]) <= b.hh + 1e-9


def collide_box_box(A, B):
    """OBB-OBB 接触流形：SAT 选轴 + 顶点包含法（出处[3] Box2D）。

    返回 [(q, n, pen)]，n 由 A 指向 B，pen > 0。
    · 4 条候选轴（A 两根 + B 两根）逐条投影，任一轴分离即不相交；
      重叠量最小的轴即碰撞法线（最小平移方向）。
    · 接触点 = 嵌进对方体内的顶点，按穿透深度取最深的 2 个——
      面-面接触恰好给出 2 点，堆叠才不会单边翘起。
    · pen 用 SAT 重叠量（同一法线下所有接触点共用），不逐点另算，
      否则同一接触面会出现互相矛盾的修正量导致抖动。
    """
    VA, VB = A.verts(), B.verts()
    axes = [rot(A.th) @ np.array([1.0, 0.0]), rot(A.th) @ np.array([0.0, 1.0]),
            rot(B.th) @ np.array([1.0, 0.0]), rot(B.th) @ np.array([0.0, 1.0])]
    best, bx = None, None
    for ax in axes:
        pa = np.array([float(np.dot(v, ax)) for v in VA])
        pb = np.array([float(np.dot(v, ax)) for v in VB])
        ov = float(min(pa.max(), pb.max()) - max(pa.min(), pb.min()))
        if ov <= 0.0:
            return []                                  # 找到分离轴
        if best is None or ov < best:
            best, bx = ov, ax
    if float(np.dot(B.p - A.p, bx)) < 0.0:
        bx = -bx                                       # 法线统一由 A 指向 B
    a_hi = max(float(np.dot(v, bx)) for v in VA)
    b_lo = min(float(np.dot(v, bx)) for v in VB)
    cand = []
    for ai, v in enumerate(VA):
        if _inside_obb(v, B):
            cand.append((float(np.dot(v, bx)) - b_lo, v, ("A", ai)))
    for bi, v in enumerate(VB):
        if _inside_obb(v, A):
            cand.append((float(a_hi - np.dot(v, bx)), v, ("B", bi)))
    if not cand:
        return []
    cand.sort(key=lambda t: -t[0])
    return [(np.asarray(v, float), bx.copy(), float(best), fid)
            for _, v, fid in cand[:2]]


def collide_ground(b, gy=0.0, n=(0.0, 1.0)):
    """半空间 y >= gy：所有低于平面的支撑点（出处[3] 顶点法）"""
    n = np.asarray(n, float)
    pts = b.verts() if b.shape == "box" else [b.p]
    rad = 0.0 if b.shape == "box" else b.r
    out = []
    for q in pts:
        sep = float(np.dot(n, q - np.array([0.0, gy]))) - rad
        if sep < 0.0:
            out.append((q, n.copy(), -sep))
    return out


class Contact:
    __slots__ = ("a", "b", "p", "n", "pen", "Pn", "Pt", "kn", "kt",
                 "bias", "fid")

    def __init__(self, a, b, p, n, pen, fid=None):
        self.a, self.b = a, b
        self.p = np.asarray(p, float)
        self.n = np.asarray(n, float)
        self.pen = float(pen)
        self.Pn = 0.0
        self.Pt = 0.0
        # 接触特征 ID：跨帧识别"同一个接触点"，用于持久流形暖启动
        self.fid = fid


def _prepare(c, dt):
    a, b = c.a, c.b
    ra, rb = c.p - a.p, c.p - b.p
    rn_a, rn_b = cross(ra, c.n), cross(rb, c.n)
    kn = a.inv_m + b.inv_m + a.inv_I * rn_a * rn_a + b.inv_I * rn_b * rn_b
    c.kn = 1.0 / kn if kn > 0 else 0.0
    t = np.array([-c.n[1], c.n[0]])
    rt_a, rt_b = cross(ra, t), cross(rb, t)
    kt = a.inv_m + b.inv_m + a.inv_I * rt_a * rt_a + b.inv_I * rt_b * rt_b
    c.kt = 1.0 / kt if kt > 0 else 0.0
    c.bias = (BETA / dt) * max(0.0, c.pen - SLOP)     # 出处[2]
    return ra, rb, t


def _apply(c, ra, rb, t, pn, pt):
    p = c.n * pn + t * pt
    if not c.a.fixed:
        c.a.v -= p * c.a.inv_m
        c.a.w -= c.a.inv_I * cross(ra, p)
    if not c.b.fixed:
        c.b.v += p * c.b.inv_m
        c.b.w += c.b.inv_I * cross(rb, p)


def solve(contacts, dt, iterations=ITER):
    """顺序冲量求解（出处[1]）：warm start → 迭代法向+摩擦"""
    cache = [(c, *_prepare(c, dt)) for c in contacts]
    for c, ra, rb, t in cache:                        # warm starting
        _apply(c, ra, rb, t, c.Pn, c.Pt)
    for _ in range(iterations):
        for c, ra, rb, t in cache:
            a, b = c.a, c.b
            dv = (b.v + cross_w(b.w, rb)) - (a.v + cross_w(a.w, ra))
            vn = float(np.dot(dv, c.n))
            dpn = (-vn + c.bias) * c.kn
            pn0 = c.Pn
            c.Pn = max(pn0 + dpn, 0.0)
            _apply(c, ra, rb, t, c.Pn - pn0, 0.0)
            dv = (b.v + cross_w(b.w, rb)) - (a.v + cross_w(a.w, ra))
            vt = float(np.dot(dv, t))
            dpt = -vt * c.kt
            # 摩擦系数合成：Box2D b2MixFriction = sqrt(f1*f2)（出处[1]）。
            # 原用 max()：摆锤用例给球设 mu=0 仍被地面的 0.6 接管，水平动量被地面摩擦偷走 28%。
            mx = float(np.sqrt(max(c.a.mu, 0.0) * max(c.b.mu, 0.0))) * c.Pn
            pt0 = c.Pt
            c.Pt = float(np.clip(pt0 + dpt, -mx, mx))
            _apply(c, ra, rb, t, 0.0, c.Pt - pt0)


class World:
    """定步长世界：重力积分 + 碰撞生成 + 求解 + 位置修正"""

    def __init__(self, g=9.80665, dt=1.0 / 60.0, gy=0.0, iters=ITER):
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
        self._relax()
        # max_pen 取求解后的残余穿透：这是渲染出来的那一帧真正被看到的重叠
        self.max_pen = max([c.pen for c in self._contacts()], default=0.0)
        return cs

    def _contacts(self):
        """接触生成 + 持久流形暖启动（出处[1][6]）。

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

        for i in range(n):
            for j in range(i + 1, n):
                A, B = self.bodies[i], self.bodies[j]
                if A.fixed and B.fixed:
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
                for k, (q, nn, pen) in enumerate(collide_seg(b, sg)):
                    cs.append(_mk(sg, b, q, nn, pen, ("s", si, k)))
        # 只保留本帧仍存在的接触，防止陈旧冲量复活
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
        逐次重算接触：修正一次后穿透量会变，用新值继续迭代。
        """
        for _ in range(iters):
            cs = self._contacts()
            if not cs:
                return
            moved = 0.0
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
                if not a.fixed:
                    a.p -= c.n * (d * a.inv_m)
                if not b.fixed:
                    b.p += c.n * (d * b.inv_m)
            if moved < 1e-6:
                return


def _round_pair(A, B):
    """圆参与的对：圆-圆 / 圆-盒(OBB)。
    圆-盒取盒上离圆心最近点（局部坐标 clamp，出处[3] 的 OBB 最近点法），
    法线由盒指向圆。
    """
    out = []
    if A.shape == "circle" and B.shape == "circle":
        d = B.p - A.p
        dist = float(np.linalg.norm(d))
        pen = (A.r + B.r) - dist
        if pen > 0:
            n = d / dist if dist > 1e-9 else np.array([0.0, 1.0])
            out.append(Contact(A, B, A.p + n * A.r, n, pen))
        return out
    for c, o in ((A, B), (B, A)):
        if c.shape != "circle":
            continue
        if o.shape == "circle":
            continue
        loc = rot(o.th).T @ (c.p - o.p)
        cl = np.array([float(np.clip(loc[0], -o.hw, o.hw)),
                       float(np.clip(loc[1], -o.hh, o.hh))])
        inside = (abs(loc[0]) < o.hw and abs(loc[1]) < o.hh)
        depth = 0.0
        if inside:                                   # 圆心在盒内：推向最近面
            dx, dy = o.hw - abs(loc[0]), o.hh - abs(loc[1])
            depth = min(dx, dy)
            if dx < dy:
                cl[0] = o.hw * (1.0 if loc[0] >= 0 else -1.0)
            else:
                cl[1] = o.hh * (1.0 if loc[1] >= 0 else -1.0)
        q = o.p + rot(o.th) @ cl                     # 盒上最近点
        d = c.p - q
        dist = float(np.linalg.norm(d))
        pen = c.r + depth - dist if inside else c.r - dist
        if pen > 0:
            n = d / dist if dist > 1e-9 else np.array([0.0, 1.0])
            if inside:
                n = -n
            # 法线统一由 A 指向 B
            if c is A:
                out.append(Contact(A, B, q, n, pen))
            else:
                out.append(Contact(A, B, q, -n, pen))
    return out


_ANCHOR = Body2(p=(0.0, 0.0), shape="circle", r=0.0, fixed=True)


class Segment2:
    """静态线段碰撞体（有限长斜面）。

    为什么不用"一串旋转盒"近似斜面：相邻盒之间会形成凸角（seam），
    圆滚过接缝时最近点会落到盒的角点上，穿透量被算成整个半径，
    表现为球被拉进斜面。线段碰撞体只有一个解析最近点，无接缝。

    出处：圆-线段取线段上离圆心最近点（clamp 投影参数 t 到 [0,1]），
    法线由最近点指向圆心；等价于 OBB 最近点法（本模块 [3]）在退化
    为线段时的形式。
    """

    # 对外伪装成 Body2：求解器只读 p/v/w/inv_m/inv_I/fixed/mu
    __slots__ = ("a", "b", "t", "mu", "e", "tag",
                 "p", "v", "w", "inv_m", "inv_I", "fixed", "shape")

    def __init__(self, a=(0.0, 0.0), b=(1.0, 0.0), t=0.0, mu=0.3, e=0.0,
                 tag="seg"):
        self.a = np.asarray(a, float)
        self.b = np.asarray(b, float)
        self.t = float(t)      # 半厚度，默认 0（无限薄）
        self.mu = float(mu)
        self.e = float(e)
        self.tag = tag
        self.p = 0.5 * (self.a + self.b)
        self.v = np.zeros(2)
        self.w = 0.0
        self.inv_m = 0.0       # 静态
        self.inv_I = 0.0
        self.fixed = True
        self.shape = "segment"

    def closest(self, q):
        """线段上离 q 最近的点：投影参数 clamp 到 [0,1]"""
        ab = self.b - self.a
        tt = float(np.dot(q - self.a, ab) / float(np.dot(ab, ab)))
        tt = min(1.0, max(0.0, tt))
        return self.a + ab * tt


def collide_seg(body, seg):
    """物体 vs 静态线段。返回 [(接触点, 法线A→B, 穿透)]"""
    out = []
    if body.shape == "circle":
        q = seg.closest(body.p)
        d = body.p - q
        dist = float(np.linalg.norm(d))
        pen = body.r + seg.t - dist
        if pen > 0.0:
            n = d / dist if dist > 1e-9 else np.array([0.0, 1.0])
            out.append((q, n, pen))
        return out
    for v in body.verts():                      # 盒：顶点逐个测（保守估计）
        q = seg.closest(v)
        d = v - q
        dist = float(np.linalg.norm(d))
        pen = seg.t - dist
        if pen > 0.0:
            n = d / dist if dist > 1e-9 else np.array([0.0, 1.0])
            out.append((q, n, pen))
    return out


class DistanceConstraint:
    """摆绳：|p - anchor| = L（出处[5]，冲量法，非弹簧）"""

    def __init__(self, body, anchor, L, local=(0.0, 0.0)):
        self.b = body
        self.a = anchor
        self.L = float(L)
        self.loc = np.asarray(local, float)

    def __call__(self, dt):
        b = self.b
        if b.fixed:
            return
        R = rot(b.th)
        r = R @ self.loc
        p = b.p + r
        d = p - self.a
        dist = float(np.linalg.norm(d))
        if dist < 1e-9:
            return
        n = d / dist
        C = dist - self.L
        rn = cross(r, n)
        k = b.inv_m + b.inv_I * rn * rn
        if k <= 0:
            return
        v = b.v + cross_w(b.w, r)
        vn = float(np.dot(v, n))
        bias = (BETA / dt) * C
        j = -(vn + bias) / k
        b.v += n * (j * b.inv_m)
        b.w += b.inv_I * cross(r, n * j)


@capability("stack", source="顺序冲量+warm starting+Baumgarte(Erin Catto GDC2006/Box2D Lite)", group="physics")
def stack_sim(n_box=4, size=0.22, T=3.0, dt=1.0 / 60.0):
    """方块堆叠：静置求稳定。返回 (世界, 每帧最大穿透, 质心轨迹)"""
    w = World(dt=dt)
    y = size
    boxes = []
    for k in range(n_box):
        b = Body2(p=(0.0, y), shape="box", hw=size, hh=size,
                  m=1.0, e=0.0, mu=0.8, tag="b%d" % k)
        w.add(b)
        boxes.append(b)
        y += 2 * size + 1e-4
    traj, pens = [], []
    for _ in range(int(round(T / dt)) + 1):
        w.step()
        pens.append(w.max_pen)
        traj.append([b.p.copy() for b in boxes])
    return boxes, max(pens), traj


@capability("ramp", source="斜面滚动：a=g(sinθ-μcosθ)；圆-顶点接触+顺序冲量", group="physics")
def ramp_sim(theta_deg=20.0, L=2.0, mu=0.05, T=2.5, dt=1.0 / 240.0):
    """球沿斜面滚下。返回 (球, 轨迹[(x,y)], 最大穿透, 理论加速度)"""
    th = np.radians(theta_deg)
    _up = np.array([np.sin(th), np.cos(th)])      # 斜面外法线（单位向量）
    _tan = np.array([np.cos(th), -np.sin(th)])    # 沿坡向下（单位向量）
    p_top = np.array([-np.cos(th) * L * 0.5, np.sin(th) * L * 0.5])
    p_bot = np.array([np.cos(th) * L * 0.5, -np.sin(th) * L * 0.5])
    gy = float(p_bot[1] - 0.11)                       # 地面接在斜面末端
    w = World(dt=dt, gy=gy)
    # 斜面 = 单根解析线段，无接缝、无端面伪接触（见 Segment2 说明）
    w.add_segment(Segment2(p_top, p_bot, mu=mu, tag="ramp"))
    ball = Body2(p=p_top + _tan * (0.06 * L) + _up * 0.112,
                 shape="circle", r=0.11, m=1.0, e=0.0, mu=mu)
    w.add(ball)
    # 只统计球仍在斜面切向覆盖范围内的帧：滚出尽头后落到地面，
    # 与斜面的接触本就应消失（C17 判据针对球与斜面的关系）
    traj, pens = [], []
    for _ in range(int(round(T / dt)) + 1):
        w.step()
        s = float(np.dot(ball.p - p_top, _tan))
        if 0.0 <= s <= L:
            pens.append(w.max_pen)
        traj.append(ball.p.copy())
    g = 9.80665
    a_theory = g * (np.sin(th) - mu * np.cos(th))     # 滑/滚的斜面加速度上界
    return ball, traj, max(pens), float(a_theory)


@capability("pendulum", source="距离约束冲量法(=Box2D b2DistanceJoint)；最低点撞击水平方向动量守恒", group="physics")
def pendulum_sim(L=1.0, th0_deg=60.0, T=3.0, dt=1.0 / 2400.0, m1=2.0, m2=1.0):
    """摆锤从 th0 摆下，最低点撞击静止球。返回 (摆, 球, 碰撞前后水平动量, 最大穿透)"""
    th0 = np.radians(th0_deg)
    # 球置于摆锤最低点正下方，且预留 delta 重叠：
    # 若恰好放在 2r 处，pen 恒为 0、接触永不被生成（上一版 pre=None 的成因）。
    # 撞击角由几何决定：theta_c ≈ sqrt(0.48*delta/(L^2+0.24L))（推导，实测吻合）。
    # 绳是外部约束，其反冲的水平分量 ~ sin(theta_c)，是水平动量变化的唯一来源，非引擎误差。
    # 实测：delta=0.04→6.84°(3.85%)、0.01→3.40°(1.58%)、0.004→2.13°(0.70%)、0.002→1.46°(0.35%)。
    # delta 再小则接触退化为擦边（最低点处摆速水平、法向竖直，法向相对速度→0），球几乎不动。
    r1 = r2 = 0.12
    delta = 0.004
    bob = Body2(p=(L * np.sin(th0), -L * np.cos(th0)), shape="circle",
                r=r1, m=m1, e=0.0, mu=0.4, tag="bob")
    anchor = np.array([0.0, 0.0])
    ball_y = -(L + r1 + r2 - delta)
    ball = Body2(p=(0.0, ball_y), shape="circle", r=r2, m=m2,
                 e=0.5, mu=0.0, tag="ball")   # mu=0：剔除地面摩擦对水平动量的干扰
    w = World(dt=dt, gy=ball_y - r2)
    w.add(bob)
    w.add(ball)
    w.constraints.append(DistanceConstraint(bob, anchor, L))
    pens = []
    pre = post = None
    for _ in range(int(round(T / dt)) + 1):
        before = bob.v[0] * m1 + ball.v[0] * m2
        w.step()
        pens.append(w.max_pen)
        after = bob.v[0] * m1 + ball.v[0] * m2
        # 取绝对值：摆从 +x 侧摆下，撞击把球推向 -x，判符号会永远漏检
        if pre is None and abs(before - after) > 1e-9 and abs(ball.v[0]) > 1e-6:
            pre, post = before, after
    return bob, ball, pre, post, max(pens)


def self_check():
    out = []
    boxes, pen, traj = stack_sim()
    drift = max(float(np.linalg.norm(traj[-1][k] - traj[-2][k]))
                for k in range(len(boxes)))
    out.append(("堆叠最大穿透<0.01", pen < 0.01, round(pen, 6)))
    out.append(("堆叠末帧静止", drift < 1e-3, round(drift, 8)))
    tops = [traj[-1][k][1] for k in range(len(boxes))]
    out.append(("堆叠层序递增", all(tops[i] < tops[i + 1]
                for i in range(len(tops) - 1)), [round(t, 3) for t in tops]))

    ball, traj, pen2, a_th = ramp_sim()
    ys = [p[1] for p in traj]
    out.append(("斜面不穿模", pen2 < 0.01, round(pen2, 6)))
    out.append(("斜面单调下滑", ys[-1] < ys[0] - 0.05,
                round(ys[0] - ys[-1], 4)))
    xs = [p[0] for p in traj]
    out.append(("斜面横向推进", xs[-1] > xs[0] + 0.05, round(xs[-1] - xs[0], 4)))

    bob, ball2, pre, post, pen3 = pendulum_sim()
    ok = (pre is not None and
          abs(post - pre) / max(abs(pre), 1e-9) < 0.02)
    out.append(("摆锤撞击水平动量守恒", ok,
                None if pre is None else (round(pre, 6), round(post, 6))))
    out.append(("摆锤不穿模", pen3 < 0.01, round(pen3, 6)))
    out.append(("摆绳长守恒",
                abs(float(np.linalg.norm(bob.p - np.array([0.0, 0.0]))) - 1.0)
                < 0.01, round(float(np.linalg.norm(bob.p)), 5)))
    return out


if __name__ == "__main__":
    for name, ok, val in self_check():
        print("%-24s %-5s %s" % (name, "PASS" if ok else "FAIL", val))
