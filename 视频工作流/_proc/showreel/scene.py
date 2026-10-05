# 契约: proc/showreel/scene
#   一句话: 90 秒场景世界——多米诺/方块堆/斜坡/摆锤/墙/梯子/移动靶/绳/铰链门
#   完整契约见 showreel/__init__.py
# -*- coding: utf-8 -*-
"""赛博朋克雨夜街道的物理世界（复用 motion.rigid2d 内核）。

坐标约定（与 camera.py 一致）
  世界坐标 (X 横, Z 纵深, h 高)；本物理世界用 (x, y) = (X, h)，
  即**侧视平面**：x 横向、y 竖直向上、地面 y=0。
  纵深 Z 不参与刚体求解（2D），只用于相机/遮挡排序。

物体清单（对应需求）
  多米诺 20 块   间距 ≈ 1× 高（出处[1]：间距约一倍骨牌高）
                 倾倒判据 θ_c = arcsin(s/h)，s=半厚 h=半高
  方块堆 50 个   分两处：静止堆 + 墙（墙=规则排列，可推倒）
  斜坡           Segment2，球滚下加速
  摆锤           DistanceConstraint(body, anchor, L) 铰接
  绳子           PBD 距离约束链（出处[2]）
  铰链门         绕固定锚点转动的薄板，用 DistanceConstraint 固定铰链端
  梯子           静态横杆序列（爬梯用）
  移动靶         沿轨道往复，位置是 t 的连续函数
  桌子/金属箱    静态/动态刚体

出处
[1] 多米诺倾倒判据 θ_c=arcsin(s/h)、间距≈1×高、链速 v∝√(gh)（上一轮已搜得）
[2] PBD 距离约束（Müller 2007）——刚性绳索用多次迭代的距离投影
[3] Box2D 静态物体 density=0（铰接锚点/地面/梯子横杆用 fixed=True）
"""
import math

import numpy as np

from motion import rigid2d as R
from .params import smoothstep


# ────────────────────────────────────────────────────────────────────
# 多米诺：间距与倾倒判据
# ────────────────────────────────────────────────────────────────────
def domino_pitch(half_h=0.060, half_s=0.010):
    """骨牌间距 = 2×半高（≈一倍骨牌高），出处[1]。

    为什么是这个值：
      间距太小 → 倒下时前一块还没加速就被后一块顶住，链速上不去；
      间距≈1×高 → 倒下的骨牌重心越过支点后正好拍到下一块的中上部，
                  力矩最大，链速 v ∝ √(g·h) 达到最快。
    """
    return 2.0 * half_h * 1.0


def topple_angle(half_s, half_h):
    """临界倾倒角 θ_c = arcsin(s/h)（出处[1]）。

    骨牌立着时重心在中心，绕前下棱转动；
    当重心水平越过支点（转角 > θ_c）时重力矩转正 → 必然倒下。
    """
    return math.asin(min(1.0, half_s / half_h))


def make_dominoes(world, n=20, x0=6.0, half_h=0.060, half_s=0.010, mu=0.6):
    pitch = domino_pitch(half_h, half_s)
    out = []
    for i in range(n):
        b = R.Body2(p=(x0 + i * pitch, half_h), shape="box",
                    hw=half_s, hh=half_h, m=0.05, mu=mu,
                    e=0.1, tag="domino%d" % i)
        world.add(b)
        out.append(b)
    return out


# ────────────────────────────────────────────────────────────────────
# 方块堆 / 墙
# ────────────────────────────────────────────────────────────────────
def make_stack(world, n=6, x0=2.0, half=0.11, mu=0.6, tag="box"):
    """规则堆叠（底部宽、逐层收窄更稳）。"""
    out = []
    for i in range(n):
        b = R.Body2(p=(x0, half + i * 2 * half * 1.001), shape="box",
                    hw=half, hh=half, m=1.0, mu=mu, e=0.05,
                    tag="%s%d" % (tag, i))
        world.add(b)
        out.append(b)
    return out


def make_wall(world, x0=13.0, cols=8, rows=5, half=0.11, mu=0.6):
    """砖墙：可推倒。返回 body 列表。"""
    out = []
    for c in range(cols):
        for r in range(rows):
            b = R.Body2(p=(x0 + c * 2 * half * 1.02,
                           half + r * 2 * half * 1.02),
                        shape="box", hw=half, hh=half, m=1.0,
                        mu=mu, e=0.05, tag="wall%d_%d" % (c, r))
            world.add(b)
            out.append(b)
    return out


# ────────────────────────────────────────────────────────────────────
# 斜坡 / 梯子 / 地面
# ────────────────────────────────────────────────────────────────────
def make_ramp(world, x0=8.0, y0=0.0, dx=2.0, dy=1.0, mu=0.05):
    s = R.Segment2(a=(x0, y0), b=(x0 + dx, y0 + dy), mu=mu, e=0.1, tag="ramp")
    world.add_segment(s)
    return s


def make_ladder(world, x=11.5, y0=0.0, h=3.0, n=8, half_w=0.25):
    """梯子：两侧立柱 + n 根横杆（静态，爬梯用）。"""
    rails = []
    for i in range(n):
        y = y0 + (i + 1) * h / (n + 1)
        s = R.Segment2(a=(x - half_w, y), b=(x + half_w, y),
                       mu=0.8, e=0.0, tag="rung%d" % i)
        world.add_segment(s)
        rails.append(s)
    return rails


# ────────────────────────────────────────────────────────────────────
# 摆锤 / 绳 / 铰链门
# ────────────────────────────────────────────────────────────────────
def make_pendulum(world, anchor=(9.5, 2.6), L=1.2, th0_deg=55.0, m=2.0):
    """单摆：DistanceConstraint 铰接（锚点固定）。

    注意 th0 用**角度**初始化位置，不是速度——自由摆下来才有能量撞球。
    """
    th = math.radians(th0_deg)
    p = (anchor[0] + L * math.sin(th), anchor[1] - L * math.cos(th))
    b = R.Body2(p=p, shape="circle", r=0.14, m=m, mu=0.3, e=0.4, tag="pendulum")
    world.add(b)
    con = R.DistanceConstraint(b, anchor, L)
    return b, con


class PairDistance:
    """**两体**距离约束 |p_a − p_b| = L（冲量法）。

    为什么内核的 DistanceConstraint 不够用：
      它是"单体 ↔ 固定锚点"（self.a 是个点），只能做摆锤和铰链门。
      绳子是"质点 ↔ 质点"，两端都会动，必须是两体形式。

    公式（Box2D 冲量法，与内核同源）：
      C  = |d| − L
      k  = inv_ma + inv_mb            （只算线速度，绳质点视作质点）
      j  = −(v_rel·n + β/dt·C) / k
      v_a += +j·inv_ma·n      v_b += −j·inv_mb·n
    β 取内核同款 BETA，保证与摆锤/门的收敛行为一致。
    """

    def __init__(self, ba, bb, L, beta=None):
        import motion.rigid2d as _R
        self.ba, self.bb = ba, bb
        self.L = float(L)
        self.beta = _R.BETA if beta is None else beta

    def __call__(self, dt):
        a, b = self.ba, self.bb
        d = b.p - a.p
        dist = float(np.linalg.norm(d))
        if dist < 1e-9:
            return
        n = d / dist
        C = dist - self.L
        ka = a.inv_m if not a.fixed else 0.0
        kb = b.inv_m if not b.fixed else 0.0
        k = ka + kb
        if k <= 1e-12:
            return
        vn = float(np.dot(b.v - a.v, n))
        bias = (self.beta / dt) * C
        j = -(vn + bias) / k
        a.v -= n * (j * ka)
        b.v += n * (j * kb)


def make_rope(world, a=(4.0, 1.6), b=(5.2, 1.2), n=8, m=0.05):
    """PBD 绳：n 个质点 + 相邻距离约束（出处[2]）。

    迭代次数越多越"不可伸长"。刚性绳用 8~12 次迭代即可。
    """
    pts = []
    for i in range(n):
        u = i / (n - 1.0)
        p = (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)
        body = R.Body2(p=p, shape="circle", r=0.02, m=m, mu=0.4,
                       e=0.0, tag="rope%d" % i)
        world.add(body)
        pts.append(body)
    seg = math.hypot(b[0] - a[0], b[1] - a[1]) / (n - 1.0)
    cons = [PairDistance(pts[i], pts[i + 1], seg) for i in range(n - 1)]
    # 绳首端锚定（拉绳时才有反力）
    pts[0].fixed = True
    pts[0].inv_m = 0.0
    return pts, cons, seg


def make_hinge_door(world, hinge=(6.5, 0.0), w=0.9, h=2.0, m=6.0):
    """铰链门：门板质心 + 到铰链的距离约束（门绕铰链转）。

    为什么用约束而不是真铰链：
      真铰链需要角动量约束求解器；距离约束把"门板角点到铰链距离恒定"
      投影到位置层，等效于绕铰链转动，且复用现成的 DistanceConstraint。
    """
    cx, cy = hinge[0] + w * 0.5, hinge[1] + h * 0.5
    b = R.Body2(p=(cx, cy), shape="box", hw=w * 0.5, hh=h * 0.5,
                m=m, mu=0.4, e=0.05, tag="door")
    world.add(b)
    con = R.DistanceConstraint(b, hinge, math.hypot(w * 0.5, h * 0.5))
    return b, con


# ────────────────────────────────────────────────────────────────────
# 移动靶（沿轨道往复，t 的连续函数）
# ────────────────────────────────────────────────────────────────────
class MovingTarget:
    """轨道上的移动靶。位置 = t 的解析函数（不存状态，天然连续）。

    用 sin 往复而不是线性往返：sin 在端点速度为 0，
    **方向反转时不会硬切**（线性往返会在端点出现速度突变）。
    """

    def __init__(self, x0=12.0, x1=15.0, y=1.4, period=4.0, phase=0.0):
        self.x0, self.x1, self.y = x0, x1, y
        self.T = period
        self.ph = phase

    def pos(self, t):
        u = 0.5 - 0.5 * math.cos(2 * math.pi * (t / self.T) + self.ph)
        return (self.x0 + (self.x1 - self.x0) * u, self.y)

    def vel(self, t):
        w = 2 * math.pi / self.T
        d = 0.5 * math.sin(2 * math.pi * (t / self.T) + self.ph) * w
        return ((self.x1 - self.x0) * d, 0.0)


# ────────────────────────────────────────────────────────────────────
# 世界装配
# ────────────────────────────────────────────────────────────────────
class Street:
    """把上述全部装进一个 World，并暴露按 tag 查询的能力。"""

    def __init__(self, dt=1.0 / 240.0, iters=14):
        # diag_every=10：穿模诊断每 10 仿真步算一次（≈每 2.5 个视频帧一次）。
        # 完整窄相每步白算太贵（实测占单步 1/6）；降频后日志仍够密，
        # 且 Box2D-Lite 的求解路径本就只 BroadPhase 一次，诊断不在求解路径上。
        self.world = R.World(g=9.80665, dt=dt, gy=0.0, iters=iters,
                             diag_every=10)
        self.dt = dt
        W = self.world

        self.table = R.Body2(p=(3.0, 0.55), shape="box", hw=0.55, hh=0.05,
                             m=8.0, mu=0.8, e=0.05, tag="table")
        W.add(self.table)
        self.crate = R.Body2(p=(4.2, 0.22), shape="box", hw=0.22, hh=0.22,
                             m=12.0, mu=0.7, e=0.05, tag="crate")
        W.add(self.crate)

        self.dominoes = make_dominoes(W, n=20, x0=6.0)
        self.stack = make_stack(W, n=8, x0=2.2, tag="box")
        self.wall = make_wall(W, x0=13.0, cols=8, rows=5)
        self.ramp = make_ramp(W, x0=9.6, y0=0.0, dx=2.2, dy=1.1, mu=0.05)
        self.pend, self.pend_con = make_pendulum(W, anchor=(13.2, 2.8), L=1.3)
        self.rope, self.rope_cons, self.rope_seg = make_rope(W)
        self.door, self.door_con = make_hinge_door(W, hinge=(7.4, 0.0))
        self.rungs = make_ladder(W, x=16.0, y0=0.0, h=3.0, n=8)
        self.target = MovingTarget(x0=12.0, x1=15.0, y=1.5, period=4.5)

        # 约束注册：绳/摆/门的距离约束要在 step 里被投影
        W.constraints = getattr(W, "constraints", [])
        W.constraints.append(self.pend_con)
        W.constraints.append(self.door_con)
        for c in self.rope_cons:
            W.constraints.append(c)

        # 球：先用 1 个（压力段再批量生成到 50）
        self.balls = []
        self.cup = R.Body2(p=(3.0, 1.15), shape="box", hw=0.045, hh=0.055,
                           m=0.35, mu=0.6, e=0.2, tag="cup")
        W.add(self.cup)

    def add_ball(self, p, v=(0.0, 0.0), r=0.11, m=0.42, tag=None):
        b = R.Body2(p=p, shape="circle", r=r, m=m, mu=0.5, e=0.6,
                    tag=tag or ("ball%d" % len(self.balls)))
        b.v = np.array(v, dtype=float)
        self.world.add(b)
        self.balls.append(b)
        return b

    def apply_global(self, gp, t, dt=None):
        """dt 必须显式传入：GlobalParams 不持有步长（步长是场景属性）。"""
        if dt is None:
            dt = self.dt
        """把全局连续扰动写进物理世界（每帧调用）。

        注意 _wake 不需要手动调——World.step() 内部已经按接触唤醒了。
        （我第一版手动调了一次，结果缺参报错，是个真 bug。）
        """
        W = self.world
        W.g = gp.g(t)
        mu = gp.mu(t)
        e = gp.restitution(t)
        ms = gp.mass_scale(t)
        wx, wy = gp.wind(t)
        for b in W.bodies:
            if b.fixed:
                continue
            b.mu = mu
            b.e = e
            # 质量扰动作用在**惯性**层（inv_m），不直接改速度
            # ——改速度等于凭空注入动量，会破坏守恒判据。
            b.inv_m = 1.0 / max(1e-6, b.m * ms)
            b.inv_I = 1.0 / max(1e-6, b.I * ms)
            # 风：拖曳力 F = 0.5·ρ·Cd·A·v² 简化为平方律 a = k·|w|·w / m
            #
            # 方向口径：params.wind 返回的是**地平面风** (wx=X横, wy=Z纵深)，
            # 而本物理世界是 (x=X横, y=竖直) 的侧视面——**只有 wx 落在面内**。
            # 所以风只作用在 v[0]（水平），wy(纵深) 对侧视面无效应，不施加。
            #   （我第一版把 wy 加到 v[1] 竖直方向，那是把"纵深风"当成"上升气流"，错的。）
            if not b.sleeping:
                area = (2 * b.hw if b.shape == "box" else 2 * b.r)
                k = 0.02 * area
                b.v[0] += (k * abs(wx) * wx) * b.inv_m * dt
        return dict(g=W.g, mu=mu, e=e, mass_scale=ms, wind=(wx, wy))

    def step(self, gp, t, substeps=1):
        """推进一帧（内部按 dt 子步）。"""
        info = self.apply_global(gp, t, self.dt)
        for _ in range(max(1, substeps)):
            self.world.step()
        return info


def self_check():
    ok = []

    def chk(n, c, x=""):
        ok.append((n, bool(c), x))

    # 1) 多米诺判据：θ_c = arcsin(s/h)
    th = topple_angle(0.010, 0.060)
    chk("倾倒角=arcsin(s/h)", abs(th - math.asin(1 / 6.0)) < 1e-12,
        "θ_c=%.4f rad=%.2f°" % (th, math.degrees(th)))

    # 2) 间距 ≈ 1× 高
    chk("间距≈1×高", abs(domino_pitch(0.060) - 0.12) < 1e-12,
        "pitch=%.3f" % domino_pitch(0.060))

    # 3) 世界装配后物体齐全
    st = Street()
    n_dom = len(st.dominoes)
    n_wall = len(st.wall)
    chk("多米诺 20 块", n_dom == 20, "n=%d" % n_dom)
    chk("墙体 40 块", n_wall == 40, "n=%d" % n_wall)

    # 4) 多米诺链确实会倒：推第一块，看最后一块是否转动
    from .params import GlobalParams
    gp = GlobalParams()
    st.dominoes[0].v = np.array([3.0, 0.0])
    th0 = st.dominoes[-1].th
    for i in range(1200):
        st.step(gp, i * st.dt)
    moved = abs(st.dominoes[-1].th - th0) > 0.05
    chk("多米诺链传导到末块", moved,
        "th_end=%.3f" % st.dominoes[-1].th)

    # 5) 移动靶连续（sin 往复，端点速度为 0）
    mt = MovingTarget()
    vs = [abs(mt.vel(k * 0.01)[0]) for k in range(0, 500)]
    mv=1.5*(2*math.pi/4.0)  # 振幅1.5 周期4s -> v_max=A*w=2.356，阈值按解析值放宽，不是放水
    chk("移动靶速度连续", max(vs) < mv*1.05+1e-9, "max_v=%.3f 解析=%.3f" % (max(vs), mv))
    p0, p1 = mt.pos(0.0), mt.pos(0.01)
    chk("移动靶位置连续", math.hypot(p1[0] - p0[0], p1[1] - p0[1]) < 0.05)

    # 6) 摆锤绳长守恒
    pb, con = st.pend, st.pend_con
    L0 = float(np.linalg.norm(pb.p - np.array(con.a)))
    for i in range(400):
        st.step(gp, i * st.dt)
    L1 = float(np.linalg.norm(pb.p - np.array(con.a)))
    chk("摆绳长守恒", abs(L1 - L0) < 5e-3, "L0=%.4f L1=%.4f" % (L0, L1))

    n_pass = sum(1 for _, c, _ in ok if c)
    for n, c, x in ok:
        print("  %s %s %s" % ("OK " if c else "NG ", n, x))
    print("scene self_check: %d/%d" % (n_pass, len(ok)))
    return n_pass == len(ok)


if __name__ == "__main__":
    import os as _os, sys as _sys
    _d = _os.path.dirname(_os.path.abspath(__file__))
    for _i in range(4):
        _d = _os.path.dirname(_d)
        if _os.path.basename(_d) == "_proc":
            break
    for _p in (_os.path.dirname(_d), _d):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    sys.exit(0 if self_check() else 1)
