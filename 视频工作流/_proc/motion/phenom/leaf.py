# 契约: proc/motion/phenom
#   一句话: 常见物理现象能力族（leaf_fall/fracture/water_jet/newton_cradle/turntable）
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""树叶飘落（flutter/tumbling 双稳态）"""
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


@capability("leaf_fall", source="Wang & Pesavento 2004 PRL; "
                                "Andersen/Pesavento/Wang 2005 JFM: 升力∝v·ω耦合项",
            group="phenom")
def _leaf_load(vx, vy, w, th, m, L, h, rho_f, C):
    """薄片气动载荷：法向/切向阻力 + v·ω 耦合升力 + 重力 + 力矩。

    返回 (fx, fy, M)，M 为偏心力矩与旋转阻尼之和；spin 模式由调用方处理。
    出处: Andersen et al. 2005 JFM 准稳态模型（唯象系数，见 leaf_fall_sim）。
    """
    C_N, C_T, C_L, C_E, C_M = C
    tx, ty = math.cos(th), math.sin(th)
    nx, ny = -math.sin(th), math.cos(th)
    vn = vx * nx + vy * ny
    vt = vx * tx + vy * ty
    f_n = -0.5 * rho_f * C_N * L * abs(vn) * vn
    f_t = -0.5 * rho_f * C_T * h * abs(vt) * vt
    fx = f_n * nx + f_t * tx
    fy = f_n * ny + f_t * ty
    fx += rho_f * L * L * C_L * w * (-vy)
    fy += rho_f * L * L * C_L * w * (vx)
    fy -= m * G
    v2 = vx * vx + vy * vy
    alpha = math.atan2(vn, -vt) if v2 > 1e-12 else 0.0
    M = (0.5 * rho_f * (L ** 3) * C_E * v2 * math.sin(2.0 * alpha)
         - 0.5 * rho_f * C_M * (L ** 4) * abs(w) * w)
    return fx, fy, M


def _leaf_classify(traj, net, dt):
    """从轨迹与净转角归纳 (mode, v_term, n_swings)。

    v_term 用总下降高度/总时间（口径稳定，不受末段短暂上升干扰）。
    """
    if len(traj) < 10:
        return "settled", 0.0, 0
    arr = np.array(traj)
    v_term = (arr[0, 1] - arr[-1, 1]) / (len(arr) * dt)
    vx_seq = np.diff(arr[:, 0])
    sgn = np.sign(vx_seq)
    sgn = sgn[sgn != 0]
    n_swings = int(np.sum(sgn[1:] != sgn[:-1])) if len(sgn) > 1 else 0
    mode = "tumbling" if abs(net) > 2.0 * math.pi else "flutter"
    return mode, float(v_term), n_swings


@capability("leaf_fall", source="Andersen et al. 2005 JFM 薄片下落双稳态"
                                "(flutter/tumbling) 准稳态气动模型",
            group="phenom")
def leaf_fall_sim(L=0.06, h=5e-4, m=5e-4, rho_f=1.225, T=4.0, dt=1.0 / 2000.0,
                  theta0=0.6, I_scale=1.0, ground_y=0.0, w0=0.0,
                  spin=None):
    """薄片（树叶/纸片）飘落：flutter（摆动滑翔）与 tumbling（持续翻滚）。

    返回 (mode, v_term, n_swings, dtheta, traj)
      mode        "flutter" 或 "tumbling"（按**净转角**判定，非端点差）
      v_term      全程平均下降速度（m/s）
      n_swings    水平速度符号变化次数（flutter 特征）
      dtheta      **净**转角（有符号累加）
      traj        [(x, y, theta), ...]
    物理：准稳态法向/切向阻力 + v·ω 耦合升力 + 偏心力矩 + 旋转阻尼。
    tumbling 需给定自转 spin（自持翻滚的涌现未实现，如实标注不冒充）。
    """
    I = I_scale * m * (L * L + h * h) / 12.0
    C_N, C_T, C_L, C_E, C_M = 1.8, 0.10, 0.50, 0.30, 0.20
    x, y, th = 0.0, 2.0, theta0
    vx, vy, w = 0.0, 0.0, w0
    net = 0.0
    traj = []
    C = (C_N, C_T, C_L, C_E, C_M)
    n = int(round(T / dt))
    for _ in range(n):
        fx, fy, M = _leaf_load(vx, vy, w, th, m, L, h, rho_f, C)
        if spin is not None:
            M = 0.0                  # tumbling：自转为给定输入，不解算力矩
        vx += fx / m * dt
        vy += fy / m * dt
        w = spin if spin is not None else w + M / I * dt
        x += vx * dt
        y += vy * dt
        th += w * dt
        net += w * dt
        if y <= ground_y:            # 落地即停（判据取落地前的行为）
            break
        traj.append((x, y, th))
    mode, v_term, n_swings = _leaf_classify(traj, net, dt)
    return mode, v_term, n_swings, float(net), traj
