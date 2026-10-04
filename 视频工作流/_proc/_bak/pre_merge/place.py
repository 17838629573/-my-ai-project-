# 契约: proc/scene/kit/place
#   一句话: 散布占位：草/花/行人（真实实现在 scene.detail）
#   完整契约见 scene/kit/__init__.py

import math
import numpy as np
from PIL import Image, ImageDraw
from scene import detail

def draw_grass(cv, ctx, **kw):
    detail.draw_grass(cv, ctx, **kw)


def draw_flowers(cv, ctx, **kw):
    detail.draw_flowers(cv, ctx, **kw)


def draw_crowd(cv, ctx, **kw):
    detail.draw_crowd(cv, ctx, **kw)

__all__ = [n for n in dir() if not n.startswith("__")]
