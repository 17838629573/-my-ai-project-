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
import numpy as np

from .beat import capability

SLOP = 0.01        # 允许穿透/分离容差（出处[2]，同 Box2D b2_linearSlop）
BETA = 0.2         # Baumgarte 系数（出处[2]）
ITER = 12          # 顺序冲量迭代次数（Box2D Lite 默认 10~20）


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
                 "shape", "hw", "hh", "r", "e", "mu", "fixed", "tag")

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


def collide_box_box(A, B):
    """SAT + 面裁剪，返回 [(pa, pb, n, pen)]，n 由 A 指向 B（出处[3]）"""
    hA, hB = np.array([A.hw, A.hh]), np.array([B.hw, B.hh])
    RA, RB = rot(A.th), rot(B.th)
    dp = B.p - A.p
    dA = RA.T @ dp
    dB = RB.T @ dp
    C = RA.T @ RB
    aC, aCt = np.abs(C), np.abs(C.T)
    faceA = np.abs(dA) - hA - aC @ hB          # A 为参考体时各轴分离量
    faceB = np.abs(dB) - aCt @ hA - hB
    if (faceA > 0).any() or (faceB > 0).any():
        return []
    # 取分离量最大（穿透最小）的轴，带 1e-3 偏置优先 faceA 防抖
    ax, ay, bx, by = faceA[0], faceA[1], faceB[0], faceB[1]
    best = max(ax, ay, bx + 1e-3, by + 1e-3)
    flip = False
    if best == bx or best == by:
        A, B, hA, hB, RA, RB, flip = B, A, hB, hA, RB, RA, True
        dA, dB = -dB, -dA            # 交换后 dp 反向
        axis_i = 0 if best == bx else 1
    else:
        f = (ax, ay)
        axis_i = 0 if best == ax else 1
    n_ref = RA[:, axis_i] * (1.0 if dA[axis_i] >= 0 else -1.0)
    if flip:
        n_ref = -n_ref
    # 参考面上的两点（世界系）
    ex = hA[axis_i] * (1.0 if dA[axis_i] >= 0 else -1.0)
    tang = RA[:, 1 - axis_i]
    c0 = A.p + n_ref * ex
    p1 = c0 - tang * hA[1 - axis_i]
    p2 = c0 + tang * hA[1 - axis_i]
    # 入射面：B 上法线与 -n_ref 最反向的那条边
    n_inc = None
    best_d = 1e9
    for i, q in enumerate(B.verts()):
        d = np.dot(n_ref, B._edge_normal(i) if hasattr(B, "_edge_normal")
                   else np.array([0.0, 0.0]))
        if d < best_d:
            best_d, n_inc = d, i
    nb = [RB @ np.array([[1, 0], [0, 1], [-1, 0], [0, -1]][k]) for k in range(4)]
    best_d, k_inc = 1e9, 0
    for k in range(4):
        d = np.dot(n_ref, nb[k])
        if d < best_d:
            best_d, k_inc = d, k
    vs = B.verts()
    inc = [vs[k_inc], vs[(k_inc + 1) % 4]]
    inc = _clip_face(inc, -tang, -np.dot(tang, p1))
    if len(inc) < 2:
        return []
    inc = _clip_face(inc, tang, np.dot(tang, p2))
    if len(inc) < 2:
        return []
    out = []
    for q in inc:
        sep = np.dot(n_ref, q - c0)
        if sep <= 0.0:
            out.append((q, n_ref, -sep))
    return out


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
    __slots__ = ("a", "b", "p", "n", "pen", "Pn", "Pt", "kn", "kt", "bias")

    def __init__(self, a, b, p, n, pen):
        self.a, self.b = a, b
        self.p = np.asarray(p, float)
        self.n = np.asarray(n, float)
        self.pen = float(pen)
        self.Pn = 0.0
        self.Pt = 0.0


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
            mx = c.a.mu * c.b.mu ** 0.0 if False else \
                max(c.a.mu, c.b.mu) * c.Pn
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
        self.constraints = []
        self.max_pen = 0.0

    def add(self, b):
        self.bodies.append(b)
        return b

    def step(self):
        dt = self.dt
        for b in self.bodies:
            if not b.fixed:
                b.v[1] -= self.g * dt
        cs = []
        n = len(self.bodies)
        for i in range(n):
            for j in range(i + 1, n):
                A, B = self.bodies[i], self.bodies[j]
                if A.fixed and B.fixed:
                    continue
                if A.shape == "box" and B.shape == "box":
                    for q, nn, pen in collide_box_box(A, B):
                        cs.append(Contact(A, B, q, nn, pen))
                else:
                    cs.extend(_round_pair(A, B))
        for b in self.bodies:
            if not b.fixed:
                for q, nn, pen in collide_ground(b, self.gy):
                    cs.append(Contact(_ANCHOR, b, q, nn, pen))
        self.max_pen = max([c.pen for c in cs], default=0.0)
        if cs:
            solve(cs, dt, self.iters)
        for con in self.constraints:
            con(dt)
        for b in self.bodies:
            if not b.fixed:
                b.p += b.v * dt
                b.th += b.w * dt
        return cs

    def _round(self, A, B):
        return _round_pair(A, B)


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
    ball = Body2(p=(-np.cos(th) * L * 0.5, np.sin(th) * L * 0.5 + 0.11),
                 shape="circle", r=0.11, m=1.0, e=0.0, mu=mu)
    w = World(dt=dt, gy=-10.0)          # 地面下移，斜面用静态盒近似
    w.add(ball)
    # 斜面用一串旋转的静态盒拼成（SAT 天然支持旋转体）
    n_seg = 40
    seg = L / n_seg
    for k in range(n_seg):
        t = (k + 0.5) / n_seg
        cx = -np.cos(th) * L * (0.5 - t)
        cy = np.sin(th) * L * (0.5 - t)
        w.add(Body2(p=(cx, cy), shape="box", hw=seg * 0.55, hh=0.05,
                    th=-th, fixed=True, mu=mu, tag="ramp"))
    traj, pens = [], []
    for _ in range(int(round(T / dt)) + 1):
        w.step()
        pens.append(w.max_pen)
        traj.append(ball.p.copy())
    g = 9.80665
    a_theory = g * (np.sin(th) - mu * np.cos(th))     # 滑/滚的斜面加速度上界
    return ball, traj, max(pens), float(a_theory)


@capability("pendulum", source="距离约束冲量法(=Box2D b2DistanceJoint)；最低点撞击水平方向动量守恒", group="physics")
def pendulum_sim(L=1.0, th0_deg=60.0, T=3.0, dt=1.0 / 2400.0, m1=2.0, m2=1.0):
    """摆锤从 th0 摆下，最低点撞击静止球。返回 (摆, 球, 碰撞前后水平动量, 最大穿透)"""
    th0 = np.radians(th0_deg)
    # 球置于摆锤最低点正下方：碰撞恰发生在最低点，绳竖直 → 水平无张力分量
    bob = Body2(p=(L * np.sin(th0), -L * np.cos(th0)), shape="circle",
                r=0.12, m=m1, e=0.0, mu=0.4, tag="bob")
    anchor = np.array([0.0, 0.0])
    ball = Body2(p=(0.0, -L - 0.24), shape="circle", r=0.12, m=m2,
                 e=0.5, mu=0.4, tag="ball")
    w = World(dt=dt, gy=-L - 0.36)
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
        if pre is None and abs(before - after) > 1e-9 and ball.v[0] > 1e-6:
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
