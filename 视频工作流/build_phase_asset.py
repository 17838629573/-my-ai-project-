#!/usr/bin/env python3
"""出片前置：素材加载与预处理。
依赖: chroma build_util _px
被依赖: build_video
改前必读: IMPROVE_build_video.md
铁律: T99 缺素材必须报错，禁静默降级、禁出空片
"""
import os
import numpy as np
from PIL import Image
import chroma as CH
from _px import to_px
from build_util import load_sheet, resize_h


def load_flag_sheet(px_per_m, path="_生成/旗_图集.png", grid=(6, 6), take=35):
    return [resize_h(f, to_px(2.50, px_per_m))
            for f in load_sheet(path, grid, take)]


def load_man_sheet(px_per_m, path="_生成/玄奘_图集.png", grid=(5, 6), take=30):
    return [resize_h(f, to_px(1.70, px_per_m))
            for f in load_sheet(path, grid, take)]


def load_tree(px_per_m, path="_生成/树_单体.png"):
    """树：缺素材非致命但必须明示（铁律31/99 禁静默）。"""
    has_tree = os.path.exists(path)
    if not has_tree:
        print("[素材] 缺 %s —— 本片不含树（非致命，已明示，禁静默）" % path)
        return None
    ti = np.array(Image.open(path).convert("RGB"))[:, :, ::-1]
    tbgra, tam = CH.chroma_key(ti)
    ys, xs = np.nonzero(tam > 0.5)
    tam2 = tam[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    trgb2 = tbgra[:, :, :3][ys.min():ys.max() + 1, xs.min():xs.max() + 1][:, :, ::-1]
    return resize_h((trgb2, (tam2 > 0.5).astype(float)), to_px(3.0, px_per_m)), True
