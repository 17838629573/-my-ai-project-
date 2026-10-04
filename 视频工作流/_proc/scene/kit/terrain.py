# 契约: proc/scene/kit/terrain
#   一句话: 地形：山脊 midpoint displacement、地面、色带
#   完整契约见 scene/kit/__init__.py

import math
import numpy as np
from PIL import Image, ImageDraw
from .canvas import *

# ---------------------------------------------------------------- 元件 3：山

def draw_mountain(cv, ctx, layers=4, rough=0.62, amp=1.0, seed=2.0, **kw):
    """多层 midpoint displacement 山脊 + 等高色带，逐层并入雾色。

    注意：cv.arr() 返回副本，必须"读一次 → 整块写 → set_arr 一次"。
    逐列 arr()/set_arr() 不仅慢，而且赋值落在临时副本上，等于没画。
    """
    w, h, hy = cv.w, cv.h, ctx["horizon_y"]
    rng = np.random.RandomState(int(seed * 1000) % (2 ** 31))
    fog = np.array(ctx["fog_rgb"], dtype=np.float32)
    arr = cv.arr()                      # ← 只读一次

    for li in range(layers):
        depth_t = (layers - 1 - li) / float(max(layers - 1, 1))   # 0=最远
        base_y = hy + 4 + int((h - hy) * 0.055 * (li + 1))
        amp_px = 16.0 + 26.0 * (li + 1) / layers
        r = _ridge(rng, k=8, roughness=rough, amp=amp)
        ys = np.interp(np.linspace(0, len(r) - 1, w), np.arange(len(r)), r)
        ys = np.roll(ys, int(rng.uniform(-40, 40)))

        fade = (1.0 - depth_t) * 0.85      # 越远越并入雾色
        for x in range(w):
            top = int(np.clip(base_y - int(ys[x] * amp_px), 0, h - 1))
            bot = int(np.clip(base_y + amp_px * 1.15, 0, h - 1))
            if bot <= top:
                continue
            n = bot - top
            hh = np.linspace(1.0, 0.0, n)
            cols = np.stack([biome_color(0.62 + 0.33 * t, ctx.get("biome", BIOME_A))
                             for t in hh]).astype(np.float32)
            arr[top:bot, x, :] = cols + (fog[None, :] - cols) * fade
    cv.set_arr(arr)


def _ridge(rng, k=8, roughness=0.55, amp=1.0):
    n = 2 ** k + 1
    a = np.zeros(n)
    cur, step = amp, n - 1
    while step > 1:
        half = step // 2
        for i in range(half, n, step):
            a[i] = 0.5 * (a[i - half] + a[i + half]) + rng.uniform(-cur, cur)
        step = half
        cur *= 2.0 ** (-roughness)
    return a


# ---------------------------------------------------------------- 元件 4：草/地

def draw_ground(cv, ctx, **kw):
    w, h, hy = cv.w, cv.h, ctx["horizon_y"]
    fog = np.array(ctx["fog_rgb"], dtype=np.float32)
    g = np.array(biome_color(0.50, ctx.get("biome", BIOME_A)), dtype=np.float32)
    dark = g * 0.60
    arr = cv.arr()
    for y in range(hy, h):
        t = (y - hy) / float(max(h - hy - 1, 1))
        c = g + (dark - g) * t
        arr[y, :] = c + (fog - c) * (1 - t) * 0.25
    cv.set_arr(arr)

BIOME_A = [
    (0.00, "深水", (0x32, 0x40, 0xC3)), (0.20, "浅水", (0x36, 0x67, 0xC7)),
    (0.30, "沙滩", (0xD2, 0xD0, 0x7D)), (0.37, "草地", (0x56, 0x98, 0x17)),
    (0.55, "草地2", (0x3E, 0x6B, 0x12)), (0.61, "岩石", (0x5A, 0x45, 0x3C)),
    (0.87, "岩石2", (0x4B, 0x3C, 0x35)), (1.00, "雪峰", (0xFF, 0xFF, 0xFF)),
]


def biome_color(hv, table=BIOME_A):
    for thr, _n, rgb in table:
        if hv < thr:
            return rgb
    return table[-1][2]




__all__ = [n for n in dir() if not n.startswith("__")]
