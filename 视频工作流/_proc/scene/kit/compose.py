# 契约: proc/scene/kit/compose
#   一句话: 场景组合：元件注册表、配方表、compose 总入口
#   完整契约见 scene/kit/__init__.py

import math
import numpy as np
from PIL import Image, ImageDraw
from .canvas import *
from .sky import *
from .terrain import *
from .tree import *
from .city import *
from .road import *


def draw_grass(cv, ctx, **kw):
    detail.draw_grass(cv, ctx, **kw)


def draw_flowers(cv, ctx, **kw):
    detail.draw_flowers(cv, ctx, **kw)


def draw_crowd(cv, ctx, **kw):
    detail.draw_crowd(cv, ctx, **kw)


ELEMENTS = {
    "sky": draw_sky,
    "cloud": draw_cloud,
    "mountain": draw_mountain,
    "ground": draw_ground,
    "grass": draw_grass,
    "flower": draw_flowers,
    "tree": draw_trees,
    "city": draw_city,
    "crowd": draw_crowd,
    "road": draw_road,
}


def list_elements():
    return sorted(ELEMENTS.keys())


# ---------------------------------------------------------------- 组合器

def compose(scene, w=540, h=960, horizon_ratio=0.52, biome=BIOME_A):
    """scene: {"name":..., "layers":[{"t":"sky",...}, ...]}  从远到近"""
    cv = Canvas(w, h)
    horizon_y = int(h * horizon_ratio)
    ctx = dict(w=w, h=h, horizon_y=horizon_y, vanish_x=int(w * 0.5),
               fog_rgb=(150, 160, 170), depth_t=1.0, biome=biome,
               rng=np.random.RandomState(0))
    # road_ban 需要 ctx，这里包一层让元件直接 ban(y) 就能用
    ctx["road_ban"] = (lambda c: (lambda y, margin=0.0: road_ban(c, y, margin)))(ctx)
    # 先把路的参数登记进 ctx：这样即使 road 层写在最后，
    # 先画的城市/树/草也能知道路面在哪、该避让哪。
    for L in scene["layers"]:
        if L.get("t") == "road":
            ctx["road_p"] = dict(half_near=L.get("half_near", 0.26),
                                 expo=L.get("expo", 1.15))
            break
    used = []
    for L in scene["layers"]:
        t = L.get("t")
        if t not in ELEMENTS:
            raise KeyError("未知元件 %r，可用：%s" % (t, list_elements()))
        kw = {k: v for k, v in L.items() if k != "t"}
        ELEMENTS[t](cv, ctx, **kw)
        used.append(t)
    rp = ctx.get("road_p", ROAD_DEFAULTS)
    geom = dict(scene=scene.get("name", "?"), w=w, h=h,
                horizon_y=horizon_y, vanish_x=ctx["vanish_x"],
                fog_rgb=ctx["fog_rgb"], elements=used,
                # 路的几何必须交出去：人物要靠它反解相机，否则人对不上路
                road_half_near=rp["half_near"], road_expo=rp["expo"])
    return cv.img, geom


# ---------------------------------------------------------------- 场景样例

SCENES = {
    "山区里的城市": dict(name="山区里的城市", layers=[
        {"t": "sky", "theta_s": 0.9, "T": 2.6},
        {"t": "cloud", "coverage": 0.4, "scale": 5.0},
        {"t": "mountain", "layers": 4, "rough": 0.68, "seed": 2.0},
        {"t": "ground"},
        {"t": "grass", "density": 1.0, "dry": 0.3, "seed": 11},
        {"t": "city", "n": 16, "rows": 2, "seed": 5, "style": "唐式"},
        {"t": "tree", "n": 5, "kind": "槐", "seed": 3},
        {"t": "crowd", "n": 7, "seed": 17},
        {"t": "flower", "density": 0.8, "seed": 13},
        {"t": "road"},
    ]),
    "城墙关隘": dict(name="城墙关隘", layers=[
        {"t": "sky", "theta_s": 1.05, "T": 3.4},
        {"t": "cloud", "coverage": 0.25, "scale": 4.0},
        {"t": "mountain", "layers": 3, "rough": 0.55, "seed": 7.0},
        {"t": "ground"},
        {"t": "grass", "density": 0.7, "dry": 0.55, "seed": 21},
        {"t": "crowd", "n": 5, "seed": 19},
        {"t": "flower", "density": 0.4, "seed": 23},
        {"t": "road"},
    ]),
    "山野": dict(name="山野", layers=[
        {"t": "sky", "theta_s": 0.85, "T": 2.4},
        {"t": "cloud", "coverage": 0.45, "scale": 6.0},
        {"t": "mountain", "layers": 5, "rough": 0.5, "seed": 3.0},
        {"t": "ground"},
        {"t": "grass", "density": 1.3, "dry": 0.2, "seed": 31},
        {"t": "tree", "n": 7, "kind": "槐", "seed": 3},
        {"t": "flower", "density": 1.2, "seed": 33},
        {"t": "road"},
    ]),
}


# ---------------------------------------------------------------- 自检

__all__ = [n for n in dir() if not n.startswith("__")]
