# 契约: proc/motion/rigid2d_solve
#   一句话: 接触求解：Contact 预处理、冲量施加、顺序冲量迭代、距离约束
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""接触求解：Contact 预处理、冲量施加、顺序冲量迭代、距离约束

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

from .rigid2d_core import (  # noqa: F401
    SLOP, BETA, SLEEP_LIN, SLEEP_ANG, SLEEP_TIME, WAKE_VN, POS_PERCENT, _ZERO, MAX_LIN_CORR, ITER, rot, cross, cross_w, Body2,
)

class Contact:
    __slots__ = ("a", "b", "p", "n", "pen", "Pn", "Pt", "kn", "kt",
                 "bias", "fid")

    def __init__(self, a, b, p, n, pen, fid=None):
        self.a, self.b = a, b
        self.p = np.asarray(p, float)
        self.n = np.asarray(n, float)
        self.pen = float(pen)
        self.Pn = 0.0
        self.Pt = 0.0
        # 接触特征 ID：跨帧识别"同一个接触点"，用于持久流形暖启动
        self.fid = fid


def _prepare(c, dt):
    a, b = c.a, c.b
    ra, rb = c.p - a.p, c.p - b.p
    rn_a, rn_b = cross(ra, c.n), cross(rb, c.n)
    kn = a.inv_m + b.inv_m + a.inv_I * rn_a * rn_a + b.inv_I * rn_b * rn_b
    c.kn = 1.0 / kn if kn > 0 else 0.0
    t = np.array([-c.n[1], c.n[0]])
    rt_a, rt_b = cross(ra, t), cross(rb, t)
    kt = a.inv_m + b.inv_m + a.inv_I * rt_a * rt_a + b.inv_I * rt_b * rt_b
    c.kt = 1.0 / kt if kt > 0 else 0.0
    c.bias = (BETA / dt) * max(0.0, c.pen - SLOP)     # 出处[2]
    return ra, rb, t


def _apply(c, ra, rb, t, pn, pt):
    p = c.n * pn + t * pt
    if not c.a.fixed:
        c.a.v -= p * c.a.inv_m
        c.a.w -= c.a.inv_I * cross(ra, p)
    if not c.b.fixed:
        c.b.v += p * c.b.inv_m
        c.b.w += c.b.inv_I * cross(rb, p)


def solve(contacts, dt, iterations=ITER):
    """顺序冲量求解（出处[1]）：warm start → 迭代法向+摩擦"""
    cache = [(c, *_prepare(c, dt)) for c in contacts]
    for c, ra, rb, t in cache:                        # warm starting
        _apply(c, ra, rb, t, c.Pn, c.Pt)
    for _ in range(iterations):
        for c, ra, rb, t in cache:
            a, b = c.a, c.b
            dv = (b.v + cross_w(b.w, rb)) - (a.v + cross_w(a.w, ra))
            vn = float(np.dot(dv, c.n))
            dpn = (-vn + c.bias) * c.kn
            pn0 = c.Pn
            c.Pn = max(pn0 + dpn, 0.0)
            _apply(c, ra, rb, t, c.Pn - pn0, 0.0)
            dv = (b.v + cross_w(b.w, rb)) - (a.v + cross_w(a.w, ra))
            vt = float(np.dot(dv, t))
            dpt = -vt * c.kt
            # 摩擦系数合成：Box2D b2MixFriction = sqrt(f1*f2)（出处[1]）。
            # 原用 max()：摆锤用例给球设 mu=0 仍被地面的 0.6 接管，水平动量被地面摩擦偷走 28%。
            mx = float(np.sqrt(max(c.a.mu, 0.0) * max(c.b.mu, 0.0))) * c.Pn
            pt0 = c.Pt
            c.Pt = float(np.clip(pt0 + dpt, -mx, mx))
            _apply(c, ra, rb, t, 0.0, c.Pt - pt0)



class DistanceConstraint:
    """摆绳：|p - anchor| = L（出处[5]，冲量法，非弹簧）"""

    def __init__(self, body, anchor, L, local=(0.0, 0.0)):
        self.b = body
        self.a = anchor
        self.L = float(L)
        self.loc = np.asarray(local, float)

    def __call__(self, dt):
        b = self.b
        if b.fixed:
            return
        R = rot(b.th)
        r = R @ self.loc
        p = b.p + r
        d = p - self.a
        dist = float(np.linalg.norm(d))
        if dist < 1e-9:
            return
        n = d / dist
        C = dist - self.L
        rn = cross(r, n)
        k = b.inv_m + b.inv_I * rn * rn
        if k <= 0:
            return
        v = b.v + cross_w(b.w, r)
        vn = float(np.dot(v, n))
        bias = (BETA / dt) * C
        j = -(vn + bias) / k
        b.v += n * (j * b.inv_m)
        b.w += b.inv_I * cross(r, n * j)
