# 契约: proc/scene/kit/sky
#   一句话: 天空：Perez 天光模型、地平线色、色带 ramp
#   完整契约见 scene/kit/__init__.py

import math
import numpy as np
from PIL import Image, ImageDraw
from .canvas import *


# ---------------------------------------------------------------- 元件 1：天空

def draw_sky(cv, ctx, theta_s=0.9, T=2.8, **kw):
    """Preetham/Perez 解析亮度 × 非等距色标渐变"""
    w, h, hy = cv.w, cv.h, ctx["horizon_y"]
    fog = horizon_rgb(theta_s, T)
    ctx["fog_rgb"] = fog                      # ← 后续所有元件共用
    zenith = tuple(int(v * 0.40) for v in fog)

    arr = np.zeros((h, w, 3), dtype=np.float32)
    for y in range(hy):
        theta = (np.pi / 2.0) * (1.0 - y / float(max(hy - 1, 1)))
        lum = _perez(theta, theta_s, T)
        t = float(np.clip(lum, 0.0, 1.0))
        arr[y, :] = _ramp(fog, zenith, t)
    arr[hy:, :] = zenith
    cv.set_arr(arr)


def _perez_coeff(T):
    tab = [(2.0, 0.1787, -1.4630, -0.3554, 0.4274, -0.0227),
           (3.0, 0.1801, -1.4425, -0.3672, 0.4138, -0.0221),
           (4.0, 0.1814, -1.4219, -0.3790, 0.4002, -0.0215),
           (5.0, 0.1827, -1.4014, -0.3908, 0.3866, -0.0209),
           (6.0, 0.1840, -1.3809, -0.4026, 0.3730, -0.0203)]
    T = float(np.clip(T, 2.0, 6.0))
    for i in range(len(tab) - 1):
        t0, t1 = tab[i][0], tab[i + 1][0]
        if t0 <= T <= t1:
            u = (T - t0) / (t1 - t0)
            return tuple(tab[i][k] + (tab[i + 1][k] - tab[i][k]) * u
                         for k in range(1, 6))
    return tab[0][1:]


def _zenith_lum(T, theta_s):
    chi = (4.0 / 9.0 - T / 120.0) * (np.pi - 2.0 * theta_s)
    yz = (4.0453 * T - 4.9710) * np.tan(chi) - 0.2155 * T + 2.4192
    return max(yz, 0.05)          # Zotti 2007：负亮度保护


def _perez(theta, theta_s, T=2.5):
    T = float(np.clip(T, 2.0, 6.0))
    theta_s = float(np.clip(theta_s, 0.05, 1.45))
    theta = float(np.clip(theta, 0.0, 1.52))
    A, B, C, D, E = _perez_coeff(T)

    def F(th, gm=0.0):
        c = max(np.cos(th), 1e-4)
        return (1 + A * np.exp(B / c)) * (1 + C * np.exp(D * gm) + E * np.cos(gm) ** 2)

    return float(np.clip(F(theta) / max(abs(F(0.0, theta_s)), 1e-6), 0.0, 1.0))


def horizon_rgb(theta_s, T=2.5, warm=(255, 198, 132), cool=(72, 120, 180)):
    t = float(np.clip((theta_s - 0.15) / 1.05, 0.0, 1.0))
    base = [warm[i] + (cool[i] - warm[i]) * t for i in range(3)]
    haze = (238, 234, 226)
    wt = float(np.clip((T - 2.0) / 4.0, 0.0, 1.0)) * 0.55
    return tuple(int(base[i] + (haze[i] - base[i]) * wt) for i in range(3))


def _ramp(c0, c1, t, stops=(0.0, 0.18, 0.41, 1.0)):
    """非等距色标：等距四分之一读起来像 CSS，非等距才像画出来的"""
    t = float(np.clip(t, 0.0, 1.0))
    for i in range(len(stops) - 1):
        a, b = stops[i], stops[i + 1]
        if a <= t <= b:
            u = (t - a) / max(b - a, 1e-9)
            u = u * u * (3 - 2 * u)
            tt = a + (b - a) * u
            return np.array([c0[j] + (c1[j] - c0[j]) * tt for j in range(3)])
    return np.array(c1, dtype=np.float32)


# ---------------------------------------------------------------- 元件 2：云

def draw_cloud(cv, ctx, coverage=0.35, scale=5.0, seed=1.0, **kw):
    """stacked Perlin fBm + smoothstep 阈值
       业界：c = smoothstep(lo, hi, fbm(uv*scale))；out = mix(sky, white, c)"""
    w, h, hy = cv.w, cv.h, ctx["horizon_y"]
    n = fbm2(w, max(hy, 1), octaves=4, freq=scale, seed=seed)
    lo = 0.62 - coverage * 0.35
    hi = lo + 0.18
    c = smoothstep(lo, hi, n)

    # 云在天空带上：越靠地平线越薄（透视）
    vfade = np.linspace(0.15, 1.0, max(hy, 1))[:, None]
    c = c * vfade

    fog = np.array(ctx["fog_rgb"], dtype=np.float32)
    white = np.array([252, 250, 246], dtype=np.float32)
    cloudcol = white * 0.55 + fog * 0.45          # 云受雾色影响
    layer = fog[None, None, :] * (1 - c[:, :, None]) + cloudcol[None, None, :] * c[:, :, None]

    full = np.zeros((h, w, 3), dtype=np.float32)
    full[:hy] = layer
    cv.blend_arr(full, np.zeros((h, w), dtype=np.float32) + (np.arange(h)[:, None] < hy))


__all__ = [n for n in dir() if not n.startswith("__")]
