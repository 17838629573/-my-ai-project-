# 契约: proc/motion/character/roll
#   一句话: 纯滚动（E25/球体滚动）：无滑移约束 v=ω·r + 能量守恒
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""滚动能力（补齐 E25 缺口，同时服务 C15/C16 球滚多米诺链）。

依据（搜索先行，非凭记忆）：
- 纯滚动（rolling without slipping）运动学约束：接触点瞬时速度为零，
  等价于质心速度 v = ω·r。出处 Halliday/Resnick《Fundamentals of
  Physics》§11 Rolling, Torque, and Angular Momentum。
- 刚体沿斜面滚下的能量守恒：m·g·Δh = ½·m·v² + ½·I·ω²，
  实心圆盘 I = ½·m·r² ⇒ v = sqrt(4/3·g·Δh)。出处同上（能量法求解）。
- 维持纯滚动所需最小静摩擦系数 μ ≥ tanθ/(1 + m·r²/I)（圆盘即 tanθ/3）；
  本仿真取 μ=0.8 远大于 tan15°/3≈0.089，故无滑移成立。

坐标：米制世界坐标，x 向右，y 向上。
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

from ..beat import capability
from ..rigid2d.core import Body2
from ..rigid2d.collide import Segment2
from ..rigid2d.world import World

DT = 1.0 / 240.0


@capability("roll", source="Halliday/Resnick Fundamentals of Physics §11: "
                           "rolling without slipping v=ω·r; energy "
                           "conservation m g Δh = ½mv² + ½Iω²", group="phys")
def roll_sim(theta_deg=15.0, L=4.0, mu=0.8, T=1.5, dt=1.0 / 240.0,
             r=0.11, mass=1.0):
    """圆盘沿斜面纯滚落。

    斜面用 Segment2 解析线段，不用旋转盒：
      【踩坑】旋转盒近似斜面时，圆心最近点会落到盒的角点上，穿透量被
      算成整个半径，求解器把球弹射出去（实测第一步 v 冲到 3.2 m/s 后
      卡死，下降仅 0.009 m）。Segment2 只有一个解析最近点，无 seam。
      （同 rigid2d_collide.Segment2 文档、rigid2d_sim.ramp_sim 做法）

    判据出处（独立来源定标，非调参）：
      无滑移 v = ω·r       —— 纯滚动运动学定义
      机械能守恒 mgh = ½mv² + ½Iω² —— 纯滚动时静摩擦不做功
      末速 v = √(4/3·g·Δh) —— 实心圆盘 I=½mr² 代入上式的解析解
    """
    th = math.radians(theta_deg)
    _up = np.array([math.sin(th), math.cos(th)])      # 斜面外法线
    _tan = np.array([math.cos(th), -math.sin(th)])    # 沿坡向下
    p_top = np.array([-math.cos(th) * L * 0.5, math.sin(th) * L * 0.5])
    p_bot = np.array([math.cos(th) * L * 0.5, -math.sin(th) * L * 0.5])
    w = World(g=9.8, dt=dt)
    w.add_segment(Segment2(p_top, p_bot, mu=mu, e=0.0, tag="ramp"))
    # 初始贴面：沿法向抬高 r + 1e-3（留极小间隙，避免初始穿透被弹射）
    disk = Body2(p=p_top + _tan * (0.06 * L) + _up * (r + 1e-3),
                 shape="circle", r=r, m=mass, e=0.0, mu=mu, tag="DISK")
    w.add(disk)

    I = 0.5 * mass * r * r                 # 实心圆盘
    y0 = float(disk.p[1])
    slip_max, v_end, y_end = 0.0, 0.0, y0
    for _ in range(int(round(T / dt))):
        w.step()
        v = float(np.linalg.norm(disk.v))
        if v > 1e-3:                       # v 极小时跳过，避免除零放大噪声
            slip_max = max(slip_max, abs(v - abs(float(disk.w)) * r) / v)
        v_end, y_end = v, float(disk.p[1])
    dh = max(y0 - y_end, 0.0)              # 下降高度（正值）
    e_in = mass * 9.8 * dh
    om = abs(float(disk.w))
    e_out = 0.5 * mass * v_end ** 2 + 0.5 * I * om ** 2
    energy_rel = abs(e_out - e_in) / max(e_in, 1e-12)
    return slip_max, energy_rel, v_end, dh


def self_check():
    from base.assertrun import Checker
    c = Checker("roll")

    slip, e_rel, v_end, dh = roll_sim()
    c.chk("E25 纯滚动无滑移(v=ω·r)", slip < 1e-3, "slip_rel=%.3e" % slip)
    c.chk("E25 机械能守恒", e_rel < 1e-3,
          "energy_rel=%.3e" % e_rel)
    # 理论末速：v = sqrt(4/3 · g · Δh)（实心圆盘能量法）
    v_theory = math.sqrt(4.0 / 3.0 * 9.8 * dh)
    c.chk("E25 末速符合圆盘滚落解", abs(v_end - v_theory) / v_theory < 1e-3,
          "v=%.5f vs √(4/3·g·Δh)=%.5f" % (v_end, v_theory))
    c.note("E25 15°斜面滚落 2s：下降 %.4f m，末速 %.5f m/s，"
           "滑移残差 %.2e，能量残差 %.2e" % (dh, v_end, slip, e_rel))
    return c.report()


if __name__ == "__main__":
    self_check()
