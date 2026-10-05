# 契约: proc/scene/kit/biome
#   一句话: 生物群区配色：BIOME_A 参数表与 biome_color 查色
#   完整契约见 scene/kit/__init__.py

import math
import numpy as np
from PIL import Image, ImageDraw


# ---------------------------------------------------------------- 配色（业界值）

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


# ---------------------------------------------------------------- 元件注册表

__all__ = [n for n in dir() if not n.startswith("__")]
