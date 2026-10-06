# 契约: proc/scene/kit/city
#   一句话: 城：多排矩形坡顶房屋，越近越大越暗
#   完整契约见 scene/kit/__init__.py

import math
import numpy as np
from PIL import Image, ImageDraw
from .canvas import *
from .road import *

# ---------------------------------------------------------------- 元件 6：房屋 / 城市

def draw_city(cv, ctx, n=14, rows=2, seed=5, style="唐式", **kw):
    """房屋。多排：越近越大越暗（透视）。

    配色按真实中式建筑，不用 biome 岩石色：
      唐式 = 朱柱白壁 + 青灰瓦 + 金铜塔刹
      江南 = 粉墙黛瓦 + 影青/迷楼灰/墨黪
    LOD：近排画门窗，远排只留剪影。"""
    rng = np.random.RandomState(seed)
    w, h, hy = cv.w, cv.h, ctx["horizon_y"]
    fog = np.array(ctx["fog_rgb"], dtype=np.float32)
    P = detail.TANG if style == "唐式" else detail.JIANGNAN

    for r in range(rows):
        # r=0 最远排，r=rows-1 最近排
        # far_t: 1=最远 0=最近（与全模块口径一致：空气透视越远越淡）
        far_t = (rows - 1 - r) / float(max(rows - 1, 1))
        y0 = hy + int((h - hy) * (0.05 + 0.16 * r))
        scale = 0.35 + 0.65 * (r / max(rows - 1, 1))
        fog_t = far_t ** 1.1
        lod = detail.lod_at(ctx, y0)

        def mix(c):
            return tuple(int(c[k] + (fog[k] - c[k]) * fog_t * 0.72) for k in range(3))

        wall = mix(P["bi"])
        roof = mix(P["wa"])
        x = -20
        ban = road_ban(ctx, y0, margin=6)      # 人行道余量：房子不压路面
        cnt = int(n * (1.0 / (r + 1.2)))
        for _ in range(max(cnt, 3)):
            bw = int(rng.uniform(24, 62) * scale + 10)
            bh = int(rng.uniform(34, 140) * scale + 14)
            if x > w + 20:
                break
            for (sx0, sx1) in _outside((x, x + bw), ban):
                if sx1 - sx0 < 6:
                    continue
                cv.d.rectangle([sx0, y0 - bh, sx1, y0], fill=wall)
                # 屋顶（中式坡顶）
                eave = int(10 * scale) + 4
                cv.d.polygon([(sx0 - 4, y0 - bh), ((sx0 + sx1) // 2, y0 - bh - eave),
                              (sx1 + 4, y0 - bh)], fill=roof)
                # 屋脊压一道深色，坡顶才立得住
                cv.d.line([(sx0 - 4, y0 - bh), (sx1 + 4, y0 - bh)],
                          fill=mix(P["wa"]), width=max(1, int(2 * scale)))
                # 门窗（Split Shape Grammar 的最小形态，按 LOD 决定画不画）
                detail.facade_windows(cv.d, sx0 + 3, sx1 - 3, y0 - bh + 4, y0 - 2,
                                      rng, style, P, lod, fog_t, fog)
            x += bw + int(rng.uniform(2, 14))

__all__ = [n for n in dir() if not n.startswith("__")]
