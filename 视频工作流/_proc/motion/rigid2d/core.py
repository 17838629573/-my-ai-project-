# 契约: proc/motion/rigid2d_core
#   一句话: 2D 刚体常量（Box2D 原文值）与几何基元（Body2/旋转/叉积）
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""2D 刚体常量（Box2D 原文值）与几何基元（Body2/旋转/叉积）

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

# 以下四个常量全部取自 Box2D b2_common.h / core.h 原文，不自造：
SLOP = 0.005           # b2_linearSlop = 0.005 * lengthUnitsPerMeter（0.5cm）
BETA = 0.2             # b2_baumgarte = 0.2f
SLEEP_LIN = 0.01       # b2_linearSleepTolerance (m/s)
SLEEP_ANG = 0.0175     # b2_angularSleepTolerance ≈ 1° in rad (Box2D 用 2°)
SLEEP_TIME = 0.5       # b2_timeToSleep (s)
WAKE_VN = 0.05         # 唤醒阈值：法向接近速度 (m/s)
POS_PERCENT = 0.2      # 位置 pass 同样用 b2_baumgarte（原文：取 1 会过冲）
_ZERO = np.zeros(2)
MAX_LIN_CORR = 0.2     # b2_maxLinearCorrection = 0.2 * lengthUnitsPerMeter
ITER = 12              # 顺序冲量迭代次数（Box2D Lite 默认 10~20）


def rot(th):
    c, s = np.cos(th), np.sin(th)
    return np.array([[c, -s], [s, c]])


def cross(a, b):
    return float(a[0] * b[1] - a[1] * b[0])


def cross_w(w, r):
    """角速度叉乘半径 → 线速度增量"""
    return np.array([-w * r[1], w * r[0]])


class Body2:
    """2D 刚体。shape: 'box'(半宽hw/半高hh) 或 'circle'(半径 r)"""
    __slots__ = ("p", "v", "th", "w", "m", "inv_m", "I", "inv_I",
                 "shape", "hw", "hh", "r", "e", "mu", "fixed", "tag",
                 "sleep_t", "sleeping")

    def __init__(self, p=(0.0, 0.0), shape="box", hw=0.25, hh=0.25, r=0.11,
                 m=1.0, th=0.0, e=0.0, mu=0.6, fixed=False, tag=""):
        self.p = np.asarray(p, float)
        self.v = np.zeros(2)
        self.th = float(th)
        self.w = 0.0
        self.shape = shape
        self.hw, self.hh, self.r = float(hw), float(hh), float(r)
        self.e, self.mu = float(e), float(mu)
        self.fixed = bool(fixed)
        self.tag = tag
        # 休眠（出处[4] Box2D b2Body）：低速持续 0.5s 后冻结，消除
        # 顺序冲量固有的残余微抖（Baumgarte 偏置与重力反复拉锯）
        self.sleep_t = 0.0
        self.sleeping = False
        if fixed:
            self.m = 0.0
            self.inv_m = 0.0
            self.I = 0.0
            self.inv_I = 0.0
        else:
            self.m = float(m)
            self.inv_m = 1.0 / self.m
            if shape == "box":
                w2, h2 = 2 * self.hw, 2 * self.hh
                self.I = self.m * (w2 * w2 + h2 * h2) / 12.0
            else:
                self.I = 0.5 * self.m * self.r * self.r
            self.inv_I = 1.0 / self.I

    def verts(self):
        """世界坐标四顶点（逆时针）"""
        R = rot(self.th)
        loc = [np.array([-self.hw, -self.hh]), np.array([self.hw, -self.hh]),
               np.array([self.hw, self.hh]), np.array([-self.hw, self.hh])]
        return [self.p + R @ q for q in loc]
