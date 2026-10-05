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


def _probe_grid(path, fallback=(4, 2)):
    """自动探测图集网格，禁止硬编码 grid。

    背景（实测逼出，2026-10-03）：
      生图模型【不会严格遵守】提示词里写的行列数。
      玄奘图集要求 4x2 → 得到 4x2 ✓；旗图集要求 4x2 → 得到 2x4 ✗。
      所以必须【从图里反推】，硬编码必然错位或取空。
    """
    try:
        from _tools.qcheck.sheet_probe import probe
        r = probe(path)
        if r.get("ok") and r.get("cols") and r.get("rows"):
            return (r["cols"], r["rows"])
    except Exception as e:
        print("[探测] %s 失败: %s" % (path, str(e)[:60]))
    return fallback


def load_flag_sheet(px_per_m, path="_生成/旗_图集.png", grid=None, take=None):
    from build_util import load_sheet as _ls
    g = grid or _probe_grid(path, fallback=(2, 4))
    n = take if take is not None else g[0] * g[1]
    return [resize_h(f, to_px(2.50, px_per_m)) for f in _ls(path, g, n)]


def load_man_sheet(px_per_m, path="_生成/玄奘_图集.png", grid=None, take=None):
    from build_util import load_sheet as _ls
    g = grid or _probe_grid(path, fallback=(4, 2))
    n = take if take is not None else g[0] * g[1]
    return [resize_h(f, to_px(1.70, px_per_m)) for f in _ls(path, g, n)]


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
