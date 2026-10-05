# 契约: proc/scene/kit/canvas
#   一句话: Canvas 画布 + 噪声基元（value noise / fBm / smoothstep）
#   完整契约见 scene/kit/__init__.py

import math
import numpy as np
from PIL import Image, ImageDraw

from scene import detail

# ---------------------------------------------------------------- 画布

class Canvas:
    def __init__(self, w, h, bg=(0, 0, 0)):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w, h), bg)
        self.d = ImageDraw.Draw(self.img)

    def arr(self):
        return np.asarray(self.img).astype(np.float32)

    def set_arr(self, a):
        self.img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        self.d = ImageDraw.Draw(self.img)

    def blend_arr(self, a, alpha):
        """alpha: (h,w) 或 (h,w,1)，把 a 按 alpha 混到现有画面"""
        al = np.asarray(alpha, dtype=np.float32)
        if al.ndim == 2:
            al = al[:, :, None]
        cur = self.arr()
        cur = cur * (1 - al) + a * al
        self.set_arr(cur)


# ---------------------------------------------------------------- 噪声

def _hash2(x, y, seed=0.0):
    p = np.array([123.34, 345.45])
    xx = (np.asarray(x, dtype=np.float32) * p[0]) % 1.0
    yy = (np.asarray(y, dtype=np.float32) * p[1]) % 1.0
    dotv = xx * (xx + 34.345) + yy * (yy + 34.345) + seed
    return (np.sin(dotv) * 43758.5453123) % 1.0


def value_noise2(w, h, freq, seed=0.0):
    """2D value noise，返回 (h,w) ∈ [0,1]"""
    gx = np.arange(w, dtype=np.float32) / max(w, 1) * freq
    gy = np.arange(h, dtype=np.float32) / max(h, 1) * freq
    X, Y = np.meshgrid(gx, gy)
    ix, iy = np.floor(X), np.floor(Y)
    fx, fy = X - ix, Y - iy
    ux = fx * fx * (3 - 2 * fx)
    uy = fy * fy * (3 - 2 * fy)
    a = _hash2(ix, iy, seed)
    b = _hash2(ix + 1, iy, seed)
    c = _hash2(ix, iy + 1, seed)
    d = _hash2(ix + 1, iy + 1, seed)
    return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy


def fbm2(w, h, octaves=4, freq=5.0, seed=0.0, lacunarity=2.0, persistence=0.5):
    v = np.zeros((h, w), dtype=np.float32)
    amp, f, norm = 1.0, freq, 0.0
    for _ in range(octaves):
        v += amp * value_noise2(w, h, f, seed)
        norm += amp
        amp *= persistence
        f *= lacunarity
    return v / max(norm, 1e-9)


def smoothstep(a, b, x):
    t = np.clip((x - a) / max(b - a, 1e-9), 0.0, 1.0)
    return t * t * (3 - 2 * t)

__all__ = [n for n in dir() if not n.startswith("__")]
