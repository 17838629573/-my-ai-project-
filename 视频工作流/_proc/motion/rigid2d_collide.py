# 契约: proc/motion/rigid2d_collide
#   一句话: 碰撞检测：SAT 盒-盒、地面、圆-线段（含参考面裁剪）
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""碰撞检测：SAT 盒-盒、地面、圆-线段（含参考面裁剪）

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

# ---------------------------------------------------------------- 碰撞检测
def _Contact(*a, **k):
    """延迟取 Contact：Contact 定义在 solve 层，而 solve 依赖本模块的碰撞检测。

    顶层直接 `from .rigid2d_solve import Contact` 会形成
    collide -> solve -> collide 的导入环（solve 要用本模块的 contacts 装配）。
    按 Python 惯用的打破环手法：把 import 下沉到调用点。
    """
    from .rigid2d_solve import Contact
    return Contact(*a, **k)


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


def collide_box_box_np(A, B):
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


def collide_box_box(A, B):
    """OBB-OBB 接触流形：SAT 选轴 + 顶点包含法（出处[3] Box2D）。

    返回 [(q, n, pen, fid)]，n 由 A 指向 B，pen > 0。
    · 4 条候选轴（A 两根 + B 两根）逐条投影，任一轴分离即不相交；
      重叠量最小的轴即碰撞法线（最小平移方向）。
    · 接触点 = 嵌进对方体内的顶点，按穿透深度取最深的 2 个——
      面-面接触恰好给出 2 点，堆叠才不会单边翘起。
    · pen 用 SAT 重叠量（同一法线下所有接触点共用），不逐点另算，
      否则同一接触面会出现互相矛盾的修正量导致抖动。

    【性能优化｜纯标量 SAT】
    原实现（现 collide_box_box_np）每次调用含 40+ 次 numpy 小数组运算
    （np.dot / @ / .max()），每次固定开销约 1µs，实测单次 0.46 ms——
    81 物体 brute force 下窄相吃掉单步 3/4 耗时。

    2D OBB 的 SAT 只有 4 轴 × 4 顶点，纯 Python float 足矣：小数组上
    numpy 的 per-call 开销远大于计算本身，标量版反而快一个量级。
    等价性由 self_check 的「标量 SAT == numpy 参考实现」守护（随机 5000 对）。
    """
    ahw, ahh = A.hw, A.hh
    bhw, bhh = B.hw, B.hh
    apx, apy = float(A.p[0]), float(A.p[1])
    bpx, bpy = float(B.p[0]), float(B.p[1])
    ca, sa = math.cos(A.th), math.sin(A.th)
    cb, sb = math.cos(B.th), math.sin(B.th)
    ax1, ax2 = ca * ahw, sa * ahh          # A 顶点分量
    ay1, ay2 = sa * ahw, ca * ahh
    bx1, bx2 = cb * bhw, sb * bhh          # B 顶点分量
    by1, by2 = sb * bhw, cb * bhh
    VA = ((apx - ax1 + ax2, apy - ay1 - ay2),
          (apx + ax1 + ax2, apy + ay1 - ay2),
          (apx + ax1 - ax2, apy + ay1 + ay2),
          (apx - ax1 - ax2, apy - ay1 + ay2))
    VB = ((bpx - bx1 + bx2, bpy - by1 - by2),
          (bpx + bx1 + bx2, bpy + by1 - by2),
          (bpx + bx1 - bx2, bpy + by1 + by2),
          (bpx - bx1 - bx2, bpy - by1 + by2))
    best = -1.0
    bxx = bxy = 0.0
    for axx, axy in ((ca, sa), (-sa, ca), (cb, sb), (-sb, cb)):
        v = VA[0]
        amin = amax = v[0] * axx + v[1] * axy
        for v in VA[1:]:
            pr = v[0] * axx + v[1] * axy
            if pr < amin:
                amin = pr
            elif pr > amax:
                amax = pr
        v = VB[0]
        bmin = bmax = v[0] * axx + v[1] * axy
        for v in VB[1:]:
            pr = v[0] * axx + v[1] * axy
            if pr < bmin:
                bmin = pr
            elif pr > bmax:
                bmax = pr
        ov = (amax if amax < bmax else bmax) - (amin if amin > bmin else bmin)
        if ov <= 0.0:
            return []                                  # 找到分离轴
        if best < 0.0 or ov < best:
            best, bxx, bxy = ov, axx, axy
    if (bpx - apx) * bxx + (bpy - apy) * bxy < 0.0:
        bxx, bxy = -bxx, -bxy                          # 法线统一由 A 指向 B
    a_hi = -1e30
    for v in VA:
        pr = v[0] * bxx + v[1] * bxy
        if pr > a_hi:
            a_hi = pr
    b_lo = 1e30
    for v in VB:
        pr = v[0] * bxx + v[1] * bxy
        if pr < b_lo:
            b_lo = pr
    cand = []
    for ai in range(4):
        vx, vy = VA[ai]
        dx, dy = vx - bpx, vy - bpy
        lx = dx * cb + dy * sb
        ly = -dx * sb + dy * cb
        if abs(lx) <= bhw + 1e-9 and abs(ly) <= bhh + 1e-9:
            cand.append((vx * bxx + vy * bxy - b_lo, (vx, vy), ("A", ai)))
    for bi in range(4):
        vx, vy = VB[bi]
        dx, dy = vx - apx, vy - apy
        lx = dx * ca + dy * sa
        ly = -dx * sa + dy * ca
        if abs(lx) <= ahw + 1e-9 and abs(ly) <= ahh + 1e-9:
            cand.append((a_hi - (vx * bxx + vy * bxy), (vx, vy), ("B", bi)))
    if not cand:
        return []
    cand.sort(key=lambda t: -t[0])
    n = np.array([bxx, bxy])
    return [(np.array(v, float), n, float(best), fid)
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
            out.append(_Contact(A, B, A.p + n * A.r, n, pen))
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
                out.append(_Contact(A, B, q, n, pen))
            else:
                out.append(_Contact(A, B, q, -n, pen))
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
                 "p", "v", "w", "inv_m", "inv_I", "fixed", "shape", "_aabb")

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
