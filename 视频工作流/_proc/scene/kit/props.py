# 契约: proc/scene/kit/props
#   一句话: 室内陈设：落地窗/书架墙/挂画/家具，输出世界坐标锚点供人物就位
#   完整契约见 scene/kit/__init__.py

import numpy as np
from .canvas import *
from .indoor import proj, _mix


# ------------------------------------------------------------ 元件：落地窗（左墙）
def draw_window(cv, g, z0=1.2, z1=5.4, y0=0.35, y1=2.85, seed=7):
    """左墙落地窗：竖梃沿 Z 均分，透视上间距递减"""
    d = cv.d
    X = -g["W"] / 2 + 0.02
    tl, bl = proj(g, X, y1, z0), proj(g, X, y0, z0)
    tr, br = proj(g, X, y1, z1), proj(g, X, y0, z1)
    d.polygon([tl, tr, br, bl], fill=(178, 196, 208))      # 窗外街道光
    n = 5
    for i in range(1, n):
        z = z0 + (z1 - z0) * i / n
        d.line([proj(g, X, y0, z), proj(g, X, y1, z)], fill=(92, 84, 76), width=2)
    for yy in (y0, (y0 + y1) / 2, y1):
        d.line([proj(g, X, yy, z0), proj(g, X, yy, z1)], fill=(92, 84, 76), width=2)
    return g


# ------------------------------------------------------------ 元件：书架墙（右墙）
def draw_bookshelf(cv, g, z0=1.2, z1=5.6, y0=0.30, y1=2.80, rows=4, seed=7):
    """右墙书架：层板 + 书籍，越远越暗（空气透视）"""
    d, rng = cv.d, np.random.default_rng(seed)
    X = +g["W"] / 2 - 0.02
    d.polygon([proj(g, X, y1, z0), proj(g, X, y1, z1),
               proj(g, X, y0, z1), proj(g, X, y0, z0)], fill=(58, 42, 30))
    for r in range(rows + 1):
        yy = y0 + (y1 - y0) * r / rows
        d.line([proj(g, X, yy, z0), proj(g, X, yy, z1)], fill=(86, 62, 42), width=3)
    for r in range(rows):
        yb = y0 + (y1 - y0) * r / rows
        z = z0 + 0.08
        while z < z1 - 0.08:
            bw = 0.04 + 0.05 * rng.random()
            bh = (y1 - y0) / rows * (0.62 + 0.28 * rng.random())
            c = tuple(int(v) for v in rng.choice(
                [(150, 62, 54), (58, 78, 104), (96, 108, 66), (140, 118, 74),
                 (78, 66, 92), (166, 146, 110)], 1)[0])
            t = 1.0 - min(1.0, (z - z0) / max(z1 - z0, 1e-3))
            c = _mix((58, 42, 30), c, 0.35 + 0.5 * t)
            a, b = proj(g, X, yb + 0.02, z), proj(g, X, yb + 0.02 + bh, z + bw)
            if b[0] - a[0] >= 0.7:
                d.rectangle([a[0], b[1], b[0], a[1]], fill=c)
            z += bw + 0.006
    return g


# ------------------------------------------------------------ 元件：后墙挂画
def draw_photos(cv, g, n=3):
    """后墙三幅黑白摄影（提示词明确要求）"""
    bx0, by0, bx1, by1 = g["back_wall"]
    d = cv.d
    ww = (bx1 - bx0) / (n + 1.2)
    for i in range(n):
        cx0 = bx0 + ww * (0.6 + i)
        hh = ww * 0.72
        cy0 = by0 + (by1 - by0) * 0.22
        d.rectangle([cx0, cy0, cx0 + ww * 0.8, cy0 + hh],
                    fill=(28, 28, 28), outline=(212, 206, 196), width=2)
        d.rectangle([cx0 + 4, cy0 + 4, cx0 + ww * 0.8 - 4, cy0 + hh - 4],
                    fill=(178, 176, 172))
    return g


# ------------------------------------------------------------ 家具与锚点
def _box(cv, g, X, Z, wm, hm, dm, c, edge=None):
    """世界包围盒 → 屏幕多边形（前后两组角点，取外包）"""
    a = proj(g, X - wm / 2, hm, Z - dm / 2)
    b = proj(g, X + wm / 2, hm, Z - dm / 2)
    c2 = proj(g, X + wm / 2, 0.0, Z + dm / 2)
    e = proj(g, X - wm / 2, 0.0, Z + dm / 2)
    cv.d.polygon([(a[0], a[1]), (b[0], b[1]), (c2[0], c2[1]), (e[0], e[1])],
                    fill=c, outline=edge)
    return (a[0], a[1], c2[0], c2[1])


def draw_props(cv, g):
    """高脚椅 / 矮桌 / 沙发，并把世界锚点写进 geom 供人物就位"""
    st = _box(cv, g, -2.15, 2.60, 0.42, 0.78, 0.42, (150, 118, 84), (96, 72, 48))
    tb = _box(cv, g, -2.05, 4.30, 0.90, 1.05, 0.60, (126, 100, 70), (88, 66, 44))
    sf = _box(cv, g, -2.10, 5.10, 1.60, 0.72, 0.70, (104, 92, 96), (70, 60, 62))
    # 吧台桌 1.05m 配高脚椅 0.78m：桌面须高于椅面，否则站姿抓握目标超臂展
    g["anchors"] = dict(stool=(-1.60, 0.78, 4.20), table=(-1.50, 1.05, 4.60),
                        sofa=(-1.70, 0.72, 5.40), stool_seat_px=st)
    return g


if __name__ == "__main__":
    from .indoor import make_geom, draw_shell, draw_floor
    from .canvas import Canvas
    cv = Canvas(540, 960)
    g = make_geom(540, 960)
    draw_shell(cv, g)
    draw_floor(cv, g)
    draw_window(cv, g)
    draw_bookshelf(cv, g)
    draw_photos(cv, g)
    draw_props(cv, g)
    cv.img.save("室内_咖啡馆.png")
    print("anchors:", {k: (round(v[0], 2), round(v[1], 2), round(v[2], 2))
                       for k, v in g["anchors"].items() if k != "stool_seat_px"})
    print("saved 室内_咖啡馆.png")
