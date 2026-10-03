#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
骨架几何：把物理点变成归一化中心线。

契约: contracts/solver_split.md
改前必读: IMPROVE_solver_split.md
"""

import math
import anchor
from _solver_base import _interp, wind_sign




def skeleton_points(pts, N, L, W, mean=0.90, vfactor=0.38, tip_pp=1.44,
                    samples=60, lift_deg=0.0, dir_deg=0.0):
    """返回 N 个相位，每个相位一条归一化中心线 [(x,y)]（单位：L）

    【铁律39】dir_deg 全局唯一，骨架必须带着风向画出来，
    否则生图模型会各画各的（左吹右 vs 右吹左）。
    分解：沿旗方向 e（伸出）× 垂直旗方向 n（摆动）
    """
    amp_side = tip_pp / 2.0 / L          # 归一化单边振幅
    sg = wind_sign(dir_deg)
    lr = math.radians(lift_deg)
    # lift 定义：0=垂直下垂（无风），90=水平完全展开（强风）
    # 故 e 的 y 分量为负（向下为垂下方向），风力越大越趋向水平
    ex, ey = sg * math.sin(lr), -math.cos(lr)     # 沿旗（被吹出的方向）
    nx, ny = sg * math.cos(lr), math.sin(lr)      # 垂旗（摆动方向，e·n=0）
    out = []
    for i in range(N):
        ph = 360.0 * i / N
        cur = []
        for k in range(samples + 1):
            s = k / samples
            A = _interp(pts, s, 1)
            lag = _interp(pts, s, 2)
            d = mean * anchor._phi(s) / anchor._phi(1.0)   # 沿旗弧长
            o = A * amp_side * math.sin(math.radians(ph - lag))  # 摆动偏移
            cur.append((d * ex + o * nx, d * ey + o * ny * vfactor))
        out.append(cur)
    return out
