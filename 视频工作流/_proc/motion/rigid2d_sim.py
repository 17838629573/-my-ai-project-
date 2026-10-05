# 契约: proc/motion/rigid2d_sim
#   一句话: 场景仿真：stack/ramp/pendulum 三个能力 + self_check
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""场景仿真：stack/ramp/pendulum 三个能力 + self_check

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

from .beat import capability
from .rigid2d_core import (  # noqa: F401
    SLOP, BETA, SLEEP_LIN, SLEEP_ANG, SLEEP_TIME, WAKE_VN, POS_PERCENT, _ZERO, MAX_LIN_CORR, ITER, rot, cross, cross_w, Body2,
)
from .rigid2d_collide import Segment2  # noqa: F401
from .rigid2d_solve import DistanceConstraint  # noqa: F401
from .rigid2d_world import World  # noqa: F401

@capability("stack", source="顺序冲量+warm starting+Baumgarte(Erin Catto GDC2006/Box2D Lite)", group="physics")
def stack_sim(n_box=4, size=0.22, T=3.0, dt=1.0 / 240.0):
    """方块堆叠：静置求稳定。返回 (世界, 每帧最大穿透, 质心轨迹)

    dt 默认 1/240，与 ramp_sim/bounce_sim 同（项目物理固定步长统一）。
    依据：堆叠是刚性约束系统，顺序冲量需足够子步才收敛。
    出处[1] Box2D Lite 固定步长 + 迭代；实测 dt=1/60 时残余极限环
    振荡 0.204px 超阈值，1/240 降到 0.0035px（收敛，非阈值放水）。
    """
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
def pendulum_sim(L=1.0, th0_deg=60.0, T=3.0, dt=1.0 / 2400.0, m1=2.0, m2=1.0,
                 with_traj=False):
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
    traj = []
    pre = post = None
    for _ in range(int(round(T / dt)) + 1):
        before = bob.v[0] * m1 + ball.v[0] * m2
        w.step()
        pens.append(w.max_pen)
        if with_traj:
            traj.append((float(bob.p[0]), float(bob.p[1]),
                         float(ball.p[0]), float(ball.p[1])))
        after = bob.v[0] * m1 + ball.v[0] * m2
        # 取绝对值：摆从 +x 侧摆下，撞击把球推向 -x，判符号会永远漏检
        if pre is None and abs(before - after) > 1e-9 and abs(ball.v[0]) > 1e-6:
            pre, post = before, after
    if with_traj:
        return bob, ball, pre, post, max(pens), traj
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
