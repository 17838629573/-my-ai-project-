# 契约: proc/scene/kit/tree
#   一句话: 树：Honda 1971 三参数分形（分叉角/长度比/深度）
#   完整契约见 scene/kit/__init__.py

import math
import numpy as np
from PIL import Image, ImageDraw
from .canvas import *
from .road import *

# ---------------------------------------------------------------- 元件 5：树（分形，Honda 三参数）

TREE_KINDS = {
    "松":  dict(angle=15.0, ratio=0.68, depth=7),   # 窄、挺拔
    "槐":  dict(angle=25.0, ratio=0.70, depth=7),   # 默认
    "橡":  dict(angle=42.0, ratio=0.74, depth=7),   # 宽、开展
    "柳":  dict(angle=55.0, ratio=0.62, depth=6),   # 陡起始角
}


def _branch(d, x, y, length, ang_deg, depth, ba, ratio, width,
            rng, col, jitter_a=5.0, jitter_l=0.2, curve=0.0):
    """分形枝干。每级递归都加扰动 —— 纯 Honda 模型高度对称、精确自相似，
    看起来不自然；加了 Δθ=±5°、ΔS=±0.2 才偏离完美自相似、接近自然树。
    curve：枝干弯曲（沿长度做二次侧偏），手/枝不总是直的。"""
    if depth <= 0 or length < 1.5:
        return
    a = np.radians(ang_deg + rng.uniform(-jitter_a, jitter_a))
    ex = x + length * np.sin(a)
    ey = y - length * np.cos(a)          # y 向下为正
    if abs(curve) > 1e-6:
        # 中点侧偏再连两段：得到弯扭的枝，不是死板直线
        mx = (x + ex) / 2 + curve * length
        my = (y + ey) / 2 + curve * length * 0.35
        d.line([(x, y), (mx, my), (ex, ey)], fill=col, width=max(1, int(width)))
    else:
        d.line([(x, y), (ex, ey)], fill=col, width=max(1, int(width)))
    nl = length * ratio * (1 + rng.uniform(-jitter_l, jitter_l))
    nw = max(1, int(width) - 1)
    _branch(d, ex, ey, nl, ang_deg - ba, depth - 1, ba, ratio, nw, rng, col,
            jitter_a, jitter_l, curve + rng.uniform(-0.10, 0.10))
    _branch(d, ex, ey, nl, ang_deg + ba, depth - 1, ba, ratio, nw, rng, col,
            jitter_a, jitter_l, curve + rng.uniform(-0.10, 0.10))


def draw_tree(cv, ctx, x=None, ybase=None, height=90, kind="槐",
              jitter=0.25, seed=0, **kw):
    """单棵树。分形递归，三参数决定整棵剪影（Honda 1971）。
    jitter：真实树是"分形程序的随机扰动"，不是完美对称。"""
    K = TREE_KINDS.get(kind, TREE_KINDS["槐"])
    rng = np.random.RandomState(seed)
    w, h, hy = cv.w, cv.h, ctx["horizon_y"]
    if x is None:
        x = rng.uniform(0.08, 0.92) * w
    if ybase is None:
        ybase = hy + (h - hy) * rng.uniform(0.12, 0.9)
    # 树种在路面上会挡路：落到路面就往路边挪，挪不开就不种
    ban = road_ban(ctx, ybase, margin=8)
    if ban is not None and ban[0] < x < ban[1]:
        left, right = ban[0] - 10, ban[1] + 10
        x = left if abs(x - left) < abs(x - right) else right
        if not (4 < x < w - 4):
            return

    # 远处并入雾色：越靠近地平线越淡（空气透视）
    fog = np.array(ctx["fog_rgb"], dtype=np.float32)
    depth_t = float(np.clip((ybase - hy) / max(h - hy, 1), 0.0, 1.0))
    fog_t = (1.0 - depth_t) ** 1.1
    # 树干用业界棕 (101,67,33)，不是水泥灰；(60,44,30) 偏黑且是旧的硬编码
    trunk = tuple(int(detail.TRUNK[k] + (fog[k] - detail.TRUNK[k]) * fog_t * 0.85)
                  for k in range(3))
    lod = detail.lod_at(ctx, ybase)

    ba = K["angle"] * (1 + rng.uniform(-jitter, jitter))
    ratio = float(np.clip(K["ratio"] * (1 + rng.uniform(-jitter, jitter) * 0.3), 0.45, 0.85))
    if lod >= 2:
        # 远树：只保留最粗两级，画成剪影（细节低于 1px，画了也看不见）
        _branch(cv.d, x, ybase, height * 0.30, 0.0, min(K["depth"], 3), ba, ratio,
                max(2, int(3 * (0.4 + 0.6 * depth_t))), rng, trunk, jitter_a=8.0)
    else:
        _branch(cv.d, x, ybase, height * 0.30, 0.0, K["depth"], ba, ratio,
                max(2, int(K["depth"] // 2 * (0.5 + 0.5 * depth_t))),
                rng, trunk, jitter_a=5.0, jitter_l=0.2,
                curve=rng.uniform(-0.16, 0.16))
    # 树冠：多团叶簇带受光面，替代"一个实心椭圆"
    detail.canopy(cv.d, x, ybase - height, ybase - height * 0.45,
                  height * 0.24, height * 0.30, rng, lod, fog_t, fog)


def draw_trees(cv, ctx, n=6, kind="槐", seed=3, band=(0.15, 0.85), **kw):
    rng = np.random.RandomState(seed)
    for i in range(n):
        draw_tree(cv, ctx, x=None, ybase=None,
                  height=rng.uniform(50, 120), kind=kind, seed=seed * 100 + i)

__all__ = [n for n in dir() if not n.startswith("__")]
