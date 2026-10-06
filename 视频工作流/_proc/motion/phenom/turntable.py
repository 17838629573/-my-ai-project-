# 契约: proc/motion/phenom
#   一句话: 常见物理现象能力族（leaf_fall/fracture/water_jet/newton_cradle/turntable）
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""旋转平台离心/科氏滑移"""
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


@capability("turntable", source="GAUGE(arXiv:2608.05948) Turntable; "
                                "非惯性系离心力mω²r与科氏力-2mω×v",
            group="phenom")
def turntable_sim(om_p=8.0, r0=0.10, mu_s=0.35, mu_k=0.25, m=1.0,
                  T=2.0, dt=1.0 / 2000.0):
    """旋转平台上的物块：离心力超过静摩擦锥后向外滑移。

    返回 (r_end, slip_started, lateral_deflect)
      r_end            最终半径（应 > r0，被甩出）
      slip_started     是否发生滑移（离心力 > μ_s·m·g）
      lateral_deflect  科氏力导致的横向偏转量（切向位移，m）
    物理（平台参考系）：F_cent = m ω² r（径向外），F_cor = -2m ω × v_rel
    （切向），摩擦 |f| ≤ μ N 指向相对速度反向。
    """
    r, rdot = r0, 0.0
    s = 0.0                      # 切向位移（相对平台）
    sdot = 0.0
    g = G
    slip = False
    n_steps = int(round(T / dt))
    for _ in range(n_steps):
        # 非惯性系力（平台系 2D）：ω = ω ẑ，v_rel = rdot r̂ + sdot ŝ
        #   F_cor = -2m ω × v_rel = 2mω·sdot r̂ - 2mω·rdot ŝ
        f_r = m * om_p * om_p * r + 2.0 * m * om_p * sdot   # 径向：离心+科氏
        f_t = -2.0 * m * om_p * rdot                        # 切向：纯科氏
        # 需求摩擦力（维持相对静止）
        f_need = math.hypot(f_r, f_t)
        f_max = mu_s * m * g
        if not slip and f_need > f_max:
            slip = True
        if not slip:
            continue                              # 静摩擦锁住，随平台转
        # 滑动：动摩擦，方向与相对速度反向
        v_rel = math.hypot(rdot, sdot)
        if v_rel > 1e-12:
            fr = -mu_k * m * g * (rdot / v_rel)
            fs = -mu_k * m * g * (sdot / v_rel)
        else:
            fr = fs = 0.0
        ar = (f_r + fr) / m
        a_s = (f_t + fs) / m
        rdot += ar * dt
        sdot += a_s * dt
        r += rdot * dt
        s += sdot * dt
        if r < 0.0:
            r = 0.0
    return float(r), slip, float(abs(s))
