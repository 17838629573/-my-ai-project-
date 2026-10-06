# 契约: proc/motion/phenom
#   一句话: 常见物理现象能力族（leaf_fall/fracture/water_jet/newton_cradle/turntable）
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""牛顿摆（等质量弹性碰撞速度交换）"""
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

G = 9.8


@capability("newton_cradle", source="GAUGE(arXiv:2608.05948) Newton's Cradle; "
                                    "等质量弹性碰撞⇒速度交换",
            group="phenom")
def newton_cradle_sim(n=5, L=0.50, r=0.04, m=0.20, th0=0.60, T=3.0,
                      dt=1.0 / 4000.0, e=0.999):
    """牛顿摆：首球拉起释放，等质量弹性碰撞 ⇒ 末球弹出、中间球静止。

    返回 (v_last, th_mid_win, th_last_win, mom_err, energy_err)
      v_last      末球获得的最大速度（应接近首球入射速度）
      th_mid_win  首次碰撞后 0.25s 窗口内中间球最大角位移（应≈0）
      th_last_win 同窗口内末球最大角位移（应≈th0）
      mom_err     动量守恒误差
      energy_err  能量守恒误差（e<1 时允许少量耗散，故判据看比例）
    注：末球弹出后会摆回二次撞击，届时中间球必然动起来，故中间球"静止"
    只在首次碰撞后的短窗口内判定，这是牛顿摆的正确观测口径。
    碰撞沿切向（摆的切向速度），等质量 ⇒ 交换切向速度（乘 e）。
    """
    th = np.zeros(n)
    om = np.zeros(n)
    th[0] = th0
    # 悬挂点间距 = 2r（刚好接触）
    anchor_x = np.arange(n) * (2.0 * r)
    n_steps = int(round(T / dt))
    v_last = 0.0
    th_mid_win = 0.0
    th_last_win = 0.0
    first_hit = None
    e0 = m * G * L * (1.0 - math.cos(th0))     # 初始势能
    for _step in range(n_steps):
        # 单摆：θ'' = -(g/L) sinθ
        om += (-(G / L) * np.sin(th)) * dt
        th += om * dt
        # 球心位置与切向速度
        pos_x = anchor_x + L * np.sin(th)
        vt = om * L
        # 相邻球接触检测（球心距 < 2r 且互相接近）
        for i in range(n - 1):
            d = pos_x[i + 1] - pos_x[i]
            if d < 2.0 * r and (vt[i] - vt[i + 1]) > 0.0:
                # 等质量弹性碰撞 ⇒ 交换速度（乘恢复系数）
                a, b = e * vt[i + 1], e * vt[i]
                vt[i], vt[i + 1] = a, b
                om[i], om[i + 1] = vt[i] / L, vt[i + 1] / L
                if first_hit is None:
                    first_hit = _step
        v_last = max(v_last, abs(vt[-1]))
        if first_hit is not None and (_step - first_hit) * dt <= 0.25:
            if n > 2:
                th_mid_win = max(th_mid_win,
                                 float(np.max(np.abs(th[1:-1]))))
            th_last_win = max(th_last_win, abs(float(th[-1])))
    # 末态能量（动能 + 势能）
    ek = 0.5 * m * (om * L) ** 2
    ep = m * G * L * (1.0 - np.cos(th))
    energy_err = abs(float(np.sum(ek) + np.sum(ep) - e0)) / max(e0, 1e-12)
    mom_err = abs(float(np.sum(m * om * L * np.cos(th)))) / max(m * L, 1e-12)
    return (float(v_last), float(th_mid_win), float(th_last_win),
            float(mom_err), float(energy_err))
