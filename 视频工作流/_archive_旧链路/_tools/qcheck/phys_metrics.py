#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""phys_metrics —— 步态质量的量化指标（从 phys_probe.py 拆出）。

拆出原因：phys_probe.py 加 foot_y_px_seq 后达 346 行 / 12265 字符，
超体积阈值，gate_post 强制拆分。此处划出「指标度量」部分。

阈值来源（业界，非自拟）：
  ECCV 2020《Contact and Human Dynamics from Monocular Video》给出三项
  量化步态指标，直接采用：
    Floating     > 3cm   —— 脚离地悬浮
    Penetration  > 3cm   —— 脚穿入地面
    Skate        > 2cm   —— 支撑期脚滑动（foot sliding）
  MORPHEUS(arXiv 2504.02918) 补充：
    Discard Rate —— 静止陷阱（stillness trap）：模型输出静止轨迹冒充通过

【诚实边界】本模块若拿求解器输出对比求解器期望，必然全 0 ——
那是循环论证不是通过。它的价值在于：渲染结果引入误差后，用同一套
指标度量渲染与真值的偏差。
"""
import math
import os
import sys

import numpy as np

from .phys_probe import _gait_of, foot_tracks, contact_of  # 延迟不成：本模块被 phys_probe 导入，需顶层

# 注意：phys_probe 也导入本模块 —— 这是循环导入。
# 解法：phys_probe 里把 import 放在函数内（延迟），此处顶层导入即可。

_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

FLOAT_M = 0.03
PENET_M = 0.03
SKATE_M = 0.02


def foot_metrics(spec, n_frames, fps=60.0, px_per_m=117.647, ground_y=None):
    """ECCV 2020 三项步态指标（Floating / Penetration / Skate）。

    单位换算：求解器输出是米，本函数统一转米后与业界阈值比。
    """
    tracks, gait = foot_tracks(spec, n_frames, fps)
    contacts = contact_of(spec, n_frames, fps, tracks)
    res = {}
    for side, seq in tracks.items():
        cs = contacts[side]
        pts = [p for p in seq if p is not None]
        if len(pts) < 2:
            res[side] = {"error": "轨迹点不足"}
            continue
        arr = np.array(pts)
        # 地面：取轨迹最低点作为地面近似（若无 ground_y）
        gy = float(arr[:, 1].max()) if ground_y is None else float(ground_y)
        height_m = (gy - arr[:, 1]) / float(px_per_m)

        c = np.array(cs[:len(arr)], dtype=bool)
        floating = float(((height_m > FLOAT_M) & c).sum()) / max(int(c.sum()), 1)
        penetr = float(((height_m < -PENET_M)).sum()) / len(arr)

        # Skate：接触期间的水平位移
        d = np.zeros(len(arr))
        d[1:] = np.sqrt(((arr[1:, 0] - arr[:-1, 0]) ** 2
                         + (arr[1:, 1] - arr[:-1, 1]) ** 2)) / float(px_per_m)
        skate = float(((d > SKATE_M) & c).sum()) / max(int(c.sum()), 1)

        res[side] = {"floating": round(floating, 4),
                     "penetration": round(penetr, 4),
                     "skate": round(skate, 4),
                     "contact_frames": int(c.sum()),
                     "thresholds": {"float_m": FLOAT_M, "penet_m": PENET_M,
                                    "skate_m": SKATE_M}}
    return res, gait

def discard_rate(tracks):
    """MORPHEUS 的 Discard Rate：物体消失(None) / 静止不动(stillness trap)。"""
    out = {}
    for side, seq in tracks.items():
        miss = sum(1 for p in seq if p is None)
        pts = np.array([p for p in seq if p is not None])
        still = 0.0
        if len(pts) > 1:
            rng = float(np.abs(pts.max(axis=0) - pts.min(axis=0)).sum())
            # 全程位移极小 = stillness trap（物体"拒绝移动"）
            still = 1.0 if rng < 1e-6 else 0.0
        out[side] = {"missing": miss, "missing_rate": round(miss / max(len(seq), 1), 4),
                     "stillness": still}
    return out
