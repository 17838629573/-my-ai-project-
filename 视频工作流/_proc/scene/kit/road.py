# 契约: proc/scene/kit/road
#   一句话: 路面半宽、禁用区间、路面绘制与避让裁剪
#   完整契约见 scene/kit/__init__.py

import math
import numpy as np
from PIL import Image, ImageDraw
from .canvas import *
from .terrain import biome_color, BIOME_A

# ---------------------------------------------------------------- 元件 7：路

ROAD_DEFAULTS = dict(half_near=0.26, expo=1.15)


def road_hw(ctx, y, margin=0.0):
    """路面在屏幕 y 处的半宽。所有元件共用同一条路的几何。
    ctx 里必须有 road 参数（由 compose 预置，与 road 层是否先画无关）。"""
    w, hy = ctx["w"], ctx["horizon_y"]
    p = ctx.get("road_p", ROAD_DEFAULTS)
    far_y, near_y = hy + 4, ctx["h"] - 1
    if y < far_y or near_y <= far_y:
        return 0.0
    t = (y - far_y) / float(near_y - far_y)
    return int(w * p["half_near"] * (t ** p["expo"])) + margin




def road_ban(ctx, y, margin=0.0):
    """路面在 y 处的禁用区间 [x0,x1]。返回 None 表示此处无路。"""
    hw = road_hw(ctx, y, margin)
    if hw <= 0:
        return None
    vx = ctx["vanish_x"]
    return (vx - hw, vx + hw)


def _outside(seg, ban):
    """把区间 seg 挖掉禁用区 ban，返回剩余段列表。"""
    x0, x1 = seg
    if ban is None or x1 <= ban[0] or x0 >= ban[1]:
        return [(x0, x1)]
    out = []
    if x0 < ban[0]:
        out.append((x0, ban[0]))
    if ban[1] < x1:
        out.append((ban[1], x1))
    return out


def draw_road(cv, ctx, half_near=0.26, expo=1.0, **kw):
    """路。先写 ctx['road_p'] 让后续元件能避让——哪怕路这层后画也行。

    expo 必须 = 1.0：平地面 + 针孔相机下，路的屏幕半宽与 (y − 地平线)
    是**严格线性**关系（hw = (W/hc)·(sy − v_h)）。
    expo≠1 相当于把路画成了"鼓起来的"非平面，人物沿路走远时就会和路
    的宽度对不上。原为 1.15（中段窄约 10%），已按透视恒等式改正。
    """
    ctx["road_p"] = dict(half_near=half_near, expo=expo)
    w, h, hy, vx = cv.w, cv.h, ctx["horizon_y"], ctx["vanish_x"]
    fog = np.array(ctx["fog_rgb"], dtype=np.float32)
    rc = np.array(biome_color(0.32, ctx.get("biome", BIOME_A)), dtype=np.float32)
    far_y, near_y = hy + 4, h - 1
    hn = int(w * half_near)
    arr = cv.arr()
    for y in range(far_y, near_y + 1):
        t = (y - far_y) / float(max(near_y - far_y, 1))
        hw = int(hn * (t ** expo))
        if hw <= 0:
            continue
        c = rc + (fog - rc) * (1 - t) * 0.9
        arr[y, max(0, vx - hw):min(w, vx + hw), :] = c
    cv.set_arr(arr)

__all__ = [n for n in dir() if not n.startswith("__")]
