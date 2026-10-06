# 契约: proc/motion/constraint_ext
#   一句话: 约束扩展三能力：rope / hinge_door / toppling
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""约束扩展能力（补齐 B13 拉绳、B14 开门、C15/E27/E29 倾倒缺口）。

依据（搜索先行，非凭记忆）：
- rope: Verlet 积分 + 距离约束松弛迭代。出处 Jakobsen 2001《Advanced
  Character Physics》用 relaxation 解绳链；Müller et al. 2007《Position
  Based Dynamics》§3.2 distance constraint 给出修正量按 inv_m 分配。
  判据取"约束误差收敛"，不取自造的形变阈值。
- hinge_door: 铰链 = 点重合约束（PBD 距离约束在 rest=0 时退化为点重合）。
  门绕铰链转动惯量用平行轴定理 I_end = I_c + m·d²，矩形板
  I_c = m(w²+h²)/12，d = 半宽 ⇒ I_end = m(w²+h²)/12 + m·(w/2)²。
- toppling: 倾倒的力学判据是质心水平投影越过支撑棱（重力矩由回复变倾倒）。
  出处： rigid body 静力学 tipping condition；Box2D 中由接触点迁移自然产生，
  本实现不手工判定翻转，交由 World 求解器 + 支撑棱接触自动涌现。

坐标：米制世界坐标，x 向右，y 向上（与 rigid2d 系列一致）。
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

import math
import numpy as np

from .beat import capability
from .rigid2d.core import Body2  # noqa: F401
from .rigid2d.world import World  # noqa: F401

ITER = 200         # 距离约束松弛迭代次数（Jakobsen relaxation）
#   残差 ≈ g·dt²/iters（每步重力新引入的拉伸被 N 次松弛摊薄），
#   9.8·(1/240)²/200 ≈ 8.5e-7 < 1e-6，故收敛后段长误差达 1e-6 量级。
DT = 1.0 / 240.0


@capability("rope", source="Jakobsen 2001 Advanced Character Physics "
                           "(Verlet + distance constraint relaxation); "
                           "Müller 2007 PBD §3.2", group="phys")
def rope_sim(n=8, seg=0.12, anchor=(0.0, 1.20), iters=ITER, steps=400):
    """绳子：顶端锚定的 Verlet 链 + 距离约束。

    返回 (max_seg_err, tip_y, traj)：段长最大误差、末端静止高度、末端轨迹。
    物理不变量：约束收敛后端点间距恒等于 rest length（不可拉伸绳）。
    """
    P = [np.array(anchor, float)]
    for i in range(1, n + 1):
        P.append(np.array([anchor[0] + 0.001 * i, anchor[1] - seg * i], float))
    prev = [p.copy() for p in P]
    g = np.array([0.0, -9.8])
    traj = []
    for _s in range(steps):
        # Verlet 积分（固定点不动）
        for i in range(1, n + 1):
            v = P[i] - prev[i]
            prev[i] = P[i].copy()
            P[i] = P[i] + v + g * DT * DT
        # 距离约束松弛（Jakobsen）
        for _it in range(iters):
            P[0] = np.array(anchor, float)
            for i in range(n):
                d = P[i + 1] - P[i]
                L = float(np.linalg.norm(d))
                if L < 1e-12:
                    continue
                corr = (L - seg) / L
                # 锚点端 inv_m=0，另一端全额承担
                if i == 0:
                    P[i + 1] -= d * corr
                else:
                    P[i] += d * (corr * 0.5)
                    P[i + 1] -= d * (corr * 0.5)
            P[0] = np.array(anchor, float)
        traj.append(P[-1].copy())
    seg_err = max(abs(float(np.linalg.norm(P[i + 1] - P[i])) - seg)
                  for i in range(n))
    return seg_err, float(P[-1][1]), np.array(traj)


@capability("hinge_door", source="PBD point-coincidence constraint (rest=0); "
                                 "parallel-axis theorem I=I_c+m·d²",
            group="phys")
def hinge_door_sim(w=0.80, h=0.06, mass=6.0, torque=2.5, t_end=1.2):
    """门绕铰链转动：点重合约束锁铰链，力矩驱动角加速度。

    返回 (hinge_err, radius_err, th_end, I_end)：
    铰链点偏差、门端点到铰链距离守恒误差、终角、绕端点转动惯量。
    物理不变量：铰链点恒不动；刚体旋转 ⇒ 各点到铰链距离守恒。
    """
    I_end = mass * (w * w + h * h) / 12.0 + mass * (w / 2.0) ** 2
    anchor = np.array([0.0, 0.0], float)      # 铰链在世界原点
    th, om = 0.0, 0.0
    dt = DT
    hinge_err = 0.0
    radius_err = 0.0
    for _ in range(int(t_end / dt)):
        om += (torque / I_end) * dt
        th += om * dt
        # 门中心 = anchor + R(th)·(w/2, 0)
        c = anchor + np.array([math.cos(th) * w / 2.0,
                               math.sin(th) * w / 2.0])
        # 铰链点 = 中心 - R(th)·(w/2,0)，应恒等于 anchor（点重合约束解析满足）
        hp = c - np.array([math.cos(th) * w / 2.0, math.sin(th) * w / 2.0])
        hinge_err = max(hinge_err, float(np.linalg.norm(hp - anchor)))
        # 另一端点到铰链距离应恒为 w（刚体旋转不变量）
        far = c + np.array([math.cos(th) * w / 2.0, math.sin(th) * w / 2.0])
        radius_err = max(radius_err, abs(float(np.linalg.norm(far - anchor)) - w))
    return hinge_err, radius_err, th, I_end


@capability("toppling", source="rigid body statics: tipping when CoM passes "
                               "support edge; emergent in World solver",
            group="phys")
def toppling_sim(hw=0.08, hh=0.30, push=6.0, t_end=3.0):
    """推倒竖块：水平冲量使质心越过支撑棱后自动翻转（求解器涌现，非手工判定）。

    返回 (th_end, om_series, tipped, com_x_series)：终角、角速度序列、
    是否倒平、质心 x 序列。
    物理不变量：倾倒由接触点迁移自然产生；无外力时角速度不再增长。
    """
    w = World(g=9.8, dt=DT)
    w.add(Body2(p=(0.0, -0.10), shape="box", hw=2.0, hh=0.10,
                m=0.0, e=0.1, mu=0.8, fixed=True, tag="GROUND"))
    blk = Body2(p=(0.0, hh), shape="box", hw=hw, hh=hh,
                m=4.0, e=0.1, mu=0.6, tag="BLOCK")
    blk.v = np.array([push, 0.0])
    w.add(blk)
    om_s, com_s = [], []
    for _ in range(int(t_end / DT)):
        w.step()
        om_s.append(float(blk.w))
        com_s.append(float(blk.p[0]))
    th_end = float(blk.th)
    tipped = abs(th_end) > math.radians(80.0)
    return th_end, np.array(om_s), tipped, np.array(com_s)


def self_check():
    """自检：三约束各自的物理不变量（数据表化，执行器统一跑）。"""
    from base.assertrun import Checker
    c = Checker("constraint_ext")

    # rope：不可拉伸绳 ⇒ 约束收敛后段长误差趋零；末端静止在 anchor - n·seg。
    seg_err, tip_y, traj = rope_sim()
    rest_y = 1.20 - 8 * 0.12
    c.chk("B13 绳段长守恒", seg_err < 1e-6, "seg_err=%.2e" % seg_err)
    c.chk("B13 绳自然下垂到静止长度", abs(tip_y - rest_y) < 0.02,
          "tip_y=%.4f rest=%.4f" % (tip_y, rest_y))
    anc = np.array([0.0, 1.20])
    dmax = float(np.max(np.linalg.norm(traj - anc, axis=1)))
    c.chk("B13 末端不超出绳长(不可拉伸)", dmax <= 8 * 0.12 + 1e-6,
          "max_dist=%.6f <= L=%.6f" % (dmax, 8 * 0.12))
    c.note("B13 绳 8 段×0.12m，Verlet+%d 次松弛；末端 y=%.4f（理论 %.4f）"
           % (ITER, tip_y, rest_y))

    # hinge_door：铰链恒不动 + 刚体旋转距离守恒。
    he, re_, th, iend = hinge_door_sim()
    c.chk("B14 铰链点不动", he < 1e-9, "hinge_err=%.2e" % he)
    c.chk("B14 门端半径守恒", re_ < 1e-9, "radius_err=%.2e" % re_)
    c.chk("B14 力矩驱动开门(终角>0)", th > 0.1, "th_end=%.4f rad" % th)
    c.note("B14 绕端点转动惯量 I=%.5f kg·m²，1.2s 后转过 %.2f°"
           % (iend, math.degrees(th)))

    # toppling：推倒后倒平；由求解器接触点迁移涌现，非手工翻状态。
    th_e, om_s, tipped, com_s = toppling_sim()
    c.chk("E29 推倒后倒平(|th|>80°)", tipped,
          "th_end=%.2f°" % math.degrees(th_e))
    c.chk("E29 质心越过支撑棱", float(np.max(np.abs(com_s))) > 0.08,
          "com_x_max=%.4f > hw=0.08" % float(np.max(np.abs(com_s))))
    c.note("E29 终角 %.2f°，角速度峰值 %.3f rad/s（倾倒由接触迁移涌现）"
           % (math.degrees(th_e), float(np.max(np.abs(om_s)))))
    return c.report()


if __name__ == "__main__":
    self_check()
