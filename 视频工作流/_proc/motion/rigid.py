# 契约: proc/motion/rigid
#   一句话: 刚体物理：半隐式欧拉定步长积分 + 冲量法碰撞响应 + 恢复系数衰减
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""C 组 —— 刚体与弹球（rigid body / bounce）。

出处（先搜证再实现，不自造）：
[1] 半隐式（辛）欧拉 Semi-implicit Euler
        v_{n+1} = v_n + a·dt
        x_{n+1} = x_n + v_{n+1}·dt
    · Erin Catto《Soft Constraints》GDC2011 原文：
      "Semi-implicit Euler is the integrator of choice for most physics
       engines. It is cheap, stable, and works well with rigid body
       constraints."
    · Box2D / Bullet / PhysX 均用它；显式欧拉会持续增能直至 blow up
    · 稳定性条件 dt < 2/ω；必须定步长，与渲染帧率解耦
[2] 定步长累加器（Box2D / moonjump）
        accumulator += dt;  while acc >= FIXED_DT: step(FIXED_DT)
    FIXED_DT = 1/60，保证可复现（回放、联机都依赖确定性）
[3] 冲量法碰撞响应（impulse-based collision response）
        v_rel_n = (v1 - v2)·n
        j = -(1+e)·v_rel_n / (1/m1 + 1/m2)
        v1 += (j/m1)·n ;  v2 -= (j/m2)·n
    · 只在 v_rel_n < 0（相互接近）时施加，否则会把已分离的再拉回
[4] 恢复系数 COR（Univ. Alabama PH105 LeClair 实验手册 / Purdue ME274）
        e = v_after / v_before = sqrt(h1/h0)
        h_n = h_0 · e^(2n)     每跳高度是前一跳的 e²
        动能损失比 ΔE/E = 1 - e²
    典型值（fizziq / superball）：
        superball 0.90  golf 0.85  tennis 0.75  basketball 0.70
        soccer 0.65    steel-on-steel 0.95
[5] 穿透分离（positional correction）：按质量反比沿法线推开，
    避免物体陷进地面/彼此重叠后持续抖动

本模块是纯数值内核，不含任何绘制。
"""
import numpy as np

from .beat import capability

G = 9.80665                 # m/s²（标准重力）
FIXED_DT = 1.0 / 60.0       # 定步长（出处[2]）

# 典型恢复系数（出处[4]）
COR = {"superball": 0.90, "golf": 0.85, "tennis": 0.75,
       "basketball": 0.70, "soccer": 0.65, "steel": 0.95, "putty": 0.10}


class Body:
    """2D 球形刚体。p 为质心高度（米），v 为竖直速度（米/秒）"""
    __slots__ = ("p", "v", "m", "r", "e", "fixed")

    def __init__(self, p=0.0, v=0.0, m=1.0, r=0.11, e=0.75, fixed=False):
        self.p = float(p)
        self.v = float(v)
        self.m = float(m)
        self.r = float(r)
        self.e = float(e)
        self.fixed = bool(fixed)


def integrate(b, dt, g=G):
    """Velocity Verlet 一步（出处[1] 的辛族积分器）

    x_{n+1} = x_n + v_n·dt + ½·a·dt²
    v_{n+1} = v_n + a·dt

    纯半隐式欧拉（v 先更新再 x += v'·dt）对匀加速运动每步系统性偏低
    ½·g·dt²，累积后恢复系数测量会偏小（实测 0.048~0.062m，超出
    restitution_err 阈值 0.05）。Verlet 对常加速度精确，且同属辛积分器，
    长期能量有界不发散。
    """
    b.p = b.p + b.v * dt - 0.5 * g * dt * dt
    b.v = b.v - g * dt


def collide_ground(b, ground=0.0, g=G):
    """地面碰撞：由本步末速度反推真实撞击速度，再施加 COR（出处[4]）

    撞击发生在步内，本步末速度 v1 已含穿透段的加速，
    由能量关系 v_c² = v1² - 2·g·pen 还原撞击瞬间速度 v_c，
    再令 v' = -e·v_c。直接拿 v1 反弹会高估（球越弹越高）。
    返回穿透深度（米），未碰撞为 0。
    """
    if b.fixed or b.p - b.r >= ground:
        return 0.0
    pen = ground - (b.p - b.r)
    vc2 = b.v * b.v - 2.0 * g * max(pen, 0.0)
    vc = np.sqrt(max(vc2, 0.0))
    vc = -vc if b.v < 0 else vc
    b.p = ground + b.r
    b.v = -b.e * vc
    return pen


def collide_pair(a, b):
    """球-球冲量响应（出处[3]）。沿质心连线法线，1D 情形 n=±1

    等质量 + e=1 → 速度交换；异质量 → 动量守恒。
    返回 (穿透深度, 是否发生冲量)
    """
    d = b.p - a.p                       # 1D：b 在 a 右侧为正
    gap = d - (a.r + b.r)
    if gap > 0.0:
        return 0.0, False
    n = 1.0 if d >= 0 else -1.0
    v_rel = (a.v - b.v) * n             # 沿法线的接近速度
    inv_a = 0.0 if a.fixed else 1.0 / a.m
    inv_b = 0.0 if b.fixed else 1.0 / b.m
    inv = inv_a + inv_b
    pen = -gap
    # 位置分离：按质量反比推开（出处[5]）
    if inv > 0:
        a.p -= pen * (inv_a / inv) * n
        b.p += pen * (inv_b / inv) * n
    if v_rel <= 0.0:
        return pen, False               # 已在分离，不再施加冲量
    j = -(1.0 + 0.5 * (a.e + b.e)) * v_rel / inv
    if not a.fixed:
        a.v += j * inv_a * n
    if not b.fixed:
        b.v -= j * inv_b * n
    return pen, True


def simulate(bodies, t_end, dt=FIXED_DT, g=G, ground=0.0, pairs=None):
    """定步长推进，返回 (轨迹 list[list[float]], 最大穿透)

    轨迹[i][k] = 第 i 步第 k 个刚体的质心高度。
    """
    n = int(round(t_end / dt)) + 1
    traj = []
    worst = 0.0
    for _ in range(n):
        for b in bodies:
            if not b.fixed:
                integrate(b, dt, g)
        if pairs:
            for i, j in pairs:
                p, _ = collide_pair(bodies[i], bodies[j])
                worst = max(worst, p)
        for b in bodies:
            p = collide_ground(b, ground)
            worst = max(worst, p)
        traj.append([b.p for b in bodies])
    return traj, worst


# ---------------------------------------------------------------- 弹球
@capability("bounce", source="COR: e=sqrt(h1/h0), h_n=h_0·e^(2n)（UA PH105 LeClair / Purdue ME274）", group="physics")
def bounce_traj(h0, e, t_end, dt=FIXED_DT, g=G, r=0.11):
    """弹球：从 h0 静止下落，返回 (高度序列, 峰值序列)

    峰值取抛物线解析顶点 y + v²/(2g)（出处[4] 的能量关系），
    比直接取采样最大值准，不会因离散步长产生系统性偏低。
    """
    b = Body(p=h0 + r, v=0.0, r=r, e=e)
    hs = []
    peaks = []
    prev_v = 0.0
    n = int(round(t_end / dt)) + 1
    for _ in range(n):
        if prev_v > 0.0 and b.v <= 0.0:
            peaks.append(b.p + b.v * b.v / (2.0 * g))
        prev_v = b.v
        integrate(b, dt, g)
        collide_ground(b, 0.0)
        hs.append(b.p)
    return hs, peaks


def bounce_peaks_theory(h0, e, n_bounce):
    """理论峰值 h_n = h_0·e^(2n)（出处[4]），用于比对"""
    return [h0 * (e ** (2 * k)) for k in range(1, n_bounce + 1)]


# ---------------------------------------------------------------- 两球对撞
@capability("rigid_body", source="半隐式/Verlet定步长积分 + 冲量法碰撞响应（Erin Catto GDC2011 / Box2D）", group="physics")
def two_ball(m1, m2, v1, v2, e=1.0):
    """一维对撞后速度（出处[3] 冲量公式的闭式解）

    等质量 + e=1 → 速度交换；任意质量动量守恒。
    """
    a = Body(p=-1.0, v=v1, m=m1, e=e)
    b = Body(p=1.0, v=v2, m=m2, e=e)
    # 直接置于刚好接触且相互接近
    a.p, b.p = 0.0, a.r + b.r
    collide_pair(a, b)
    return a.v, b.v


def register(cap, src, group):
    """由 motion.beat 注入装饰器，避免本模块 import beat（防环）"""
    def capability(name, source, grp="other"):
        def deco(fn):
            cap[name] = fn
            src[name] = source
            group[name] = grp
            return fn
        return deco
    return capability


def self_check():
    out = []
    e = 0.75
    hs, peaks = bounce_traj(1.0, e, 4.0)
    th = bounce_peaks_theory(1.0, e, 3)
    if len(peaks) >= 3:
        # peaks 是质心高度，要减半径换成离地落差再比理论值
        err = max(abs((peaks[k] - 0.11) - th[k]) for k in range(3))
        out.append(("峰值符合h_0·e^(2n)", err < 0.02, round(err, 5)))
    else:
        out.append(("峰值符合h_0·e^(2n)", False, len(peaks)))
    out.append(("每次高度递减",
                all(peaks[i + 1] < peaks[i] for i in range(len(peaks) - 1)),
                len(peaks)))
    # 高度序列不得为负（不穿地）
    out.append(("不穿地", min(hs) >= 0.11 - 1e-9, round(min(hs), 5)))

    # 等质量 e=1 交换速度
    v1, v2 = two_ball(1.0, 1.0, 2.0, -1.0, 1.0)
    out.append(("等质量弹性交换速度",
                abs(v1 + 1.0) < 1e-9 and abs(v2 - 2.0) < 1e-9,
                (round(v1, 6), round(v2, 6))))
    # 动量守恒（异质量）
    m1, m2, u1, u2 = 2.0, 1.0, 3.0, -1.0
    w1, w2 = two_ball(m1, m2, u1, u2, 1.0)
    p0 = m1 * u1 + m2 * u2
    p1 = m1 * w1 + m2 * w2
    out.append(("异质量动量守恒", abs(p1 - p0) < 1e-9, round(p1 - p0, 12)))
    # 分离中不再施加冲量
    a = Body(p=0.0, v=-1.0, r=0.1)
    b = Body(p=0.15, v=1.0, r=0.1)
    _, hit = collide_pair(a, b)
    out.append(("分离中不施加冲量", not hit, hit))
    # 定步长可复现
    _, pk1 = bounce_traj(1.0, 0.75, 3.0)
    _, pk2 = bounce_traj(1.0, 0.75, 3.0)
    out.append(("定步长可复现", pk1 == pk2, len(pk1)))
    return out


if __name__ == "__main__":
    for name, ok, val in self_check():
        print("%-22s %-5s %s" % (name, "PASS" if ok else "FAIL", val))
