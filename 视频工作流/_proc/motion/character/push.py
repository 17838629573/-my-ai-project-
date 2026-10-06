# 契约: proc/motion/character/push
#   一句话: 推动箱体（B12）：掌为运动学驱动，箱受地面摩擦与接触约束
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""推箱子能力（补齐 B12 缺口）。

依据（搜索先行，非凭记忆）：
- 接触容差取 Box2D 官方 b2_linearSlop = 0.005 m（v2.4.1 b2_common.h:65
  实测 `#define b2_linearSlop (0.005f * b2_lengthUnitsPerMeter)`），
  与 harness.CRIT 的 penetration_m 同一口径。
- 掌-箱保持接触时，箱的运动由接触法向力驱动（Box2D sequential impulse），
  本实现用运动学掌推进 + 求解器接触，不手工搬运箱的位置。
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

from ..beat import capability
from ..rigid2d.core import Body2
from ..rigid2d.world import World

SLOP = 0.005        # Box2D 官方 b2_linearSlop（见模块 docstring 依据）
DT = 1.0 / 240.0


@capability("push", source="Box2D v2.4.1 b2_linearSlop=0.005; sequential "
                           "impulse contact", group="motion")
def push_sim(push_v=0.60, t_end=1.5, hw=0.18, hh=0.18, mass=5.0, mu=0.45):
    """掌（运动学）水平推箱，箱受地面摩擦。

    返回 (disp, max_pen, gap_min, lift_max)：箱位移、掌-箱最大穿透、
    最小间隙（负值=穿模）、箱离地最大高度。
    物理不变量：接触不穿模（穿透受 slop 约束）、箱被推动、箱不离地。
    """
    w = World(g=9.8, dt=DT)
    w.add(Body2(p=(0.0, -0.10), shape="box", hw=4.0, hh=0.10,
                m=0.0, e=0.0, mu=mu, fixed=True, tag="GROUND"))
    box = Body2(p=(0.0, hh), shape="box", hw=hw, hh=hh,
                m=mass, e=0.0, mu=mu, tag="BOX")
    w.add(box)

    # 掌：运动学圆盘，圆心高度与箱心齐，初始贴箱左侧
    palm_x = -hw - 0.04
    palm_y = hh
    palm_r = 0.04
    x0 = float(box.p[0])
    max_pen, gap_min, lift_max = 0.0, 1e9, 0.0
    for i in range(int(t_end / DT)):
        palm_x += push_v * DT
        # 掌与箱左表面的间隙（负=穿透）
        gap = (palm_x + palm_r) - (float(box.p[0]) - hw)
        gap_min = min(gap_min, -gap)      # -gap>0 表示穿模
        max_pen = max(max_pen, -gap)
        # 接触时把掌速度传给箱（法向驱动，非直接搬运位置）
        if gap > -SLOP:
            box.v = np.array([push_v, float(box.v[1])])
        w.step()
        lift_max = max(lift_max, abs(float(box.p[1]) - hh))
    disp = float(box.p[0]) - x0
    return disp, max_pen, -gap_min, lift_max


@capability("box", source="Box2D v2.4.1 b2_linearSlop=0.005; Coulomb friction "
                          "sliding", group="motion")
def box_sim(mu=0.45, v0=1.2, t_end=2.0, hw=0.18, hh=0.18, mass=5.0):
    """箱体自由滑行：给初速后由库仑摩擦减速至停（验证摩擦与穿模）。

    返回 (dist, stopped, max_pen)：滑行距离、是否停下、地面最大穿透。
    物理不变量：摩擦做负功 ⇒ 速度单调降至 0；箱不陷入地面（受 slop 约束）。
    """
    w = World(g=9.8, dt=DT)
    w.add(Body2(p=(0.0, -0.10), shape="box", hw=4.0, hh=0.10,
                m=0.0, e=0.0, mu=mu, fixed=True, tag="GROUND"))
    box = Body2(p=(0.0, hh), shape="box", hw=hw, hh=hh,
                m=mass, e=0.0, mu=mu, tag="BOX")
    box.v = np.array([v0, 0.0])
    w.add(box)
    max_pen = 0.0
    for _ in range(int(t_end / DT)):
        w.step()
        pen = (float(box.p[1]) - hh) * -1.0     # 陷入地面为正
        max_pen = max(max_pen, pen)
    dist = float(box.p[0])
    stopped = float(np.linalg.norm(box.v)) < 1e-3
    return dist, stopped, max_pen


def self_check():
    from base.assertrun import Checker
    c = Checker("push")

    disp, mp, gm, lift = push_sim()
    c.chk("B12 箱被推动", disp > 0.05, "disp=%.4f m" % disp)
    c.chk("B12 掌-箱不穿模(<slop)", mp <= SLOP,
          "pen=%.6f <= %.3f" % (mp, SLOP))
    c.chk("B12 箱不离地", lift < SLOP, "lift=%.6f" % lift)
    c.note("B12 推程 1.5s 位移 %.4f m，掌箱最大穿透 %.6f m" % (disp, mp))

    d, st, pen = box_sim()
    c.chk("B12 摩擦使箱停下", st, "v_end<1e-3")
    c.chk("B12 箱不陷地面(<slop)", pen <= SLOP, "pen=%.6f" % pen)
    c.note("B12 初速 1.2 m/s 滑行 %.4f m 后静止，地面穿透 %.6f m" % (d, pen))
    return c.report()


if __name__ == "__main__":
    self_check()
