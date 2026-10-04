# 契约: proc/scene/kit/cloud
#   一句话: 云：分层 fBm + smoothstep 阈值，coverage 控云量
#   完整契约见 scene/kit/__init__.py

import math
import numpy as np
from PIL import Image, ImageDraw
from .canvas import *

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
