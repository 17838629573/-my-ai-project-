# 契约: proc/scene/kit/indoor
#   一句话: 室内一点透视：房间壳几何、投影 proj()、水磨石地面
#   完整契约见 scene/kit/__init__.py

import math
import numpy as np
from PIL import Image, ImageDraw
from .canvas import *
from color.paint import hex2rgb as _hx


def _mix(a, b, t):
    t = float(max(0.0, min(1.0, t)))
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


# ------------------------------------------------------------ 房间配方
# 一点透视：地平线=视高(1.5~1.7m 站立 / 1.0m 坐姿)，VP 向画框四角连线成壳
ROOMS = {
    "咖啡馆": dict(W=6.0, H=3.20, D=6.0, eye=1.60, fov_h=55.0,
                   vp_off=0.50, wall="#6b5c50", floor="#b9b3aa",
                   ceil="#8a7f72", back="#7c6d5e"),
}


def make_geom(w, h, preset="咖啡馆", seed=7):
    """房间几何。与 camera.fit 契约一致（horizon_y/vanish_x/road_half_near）"""
    R = dict(ROOMS[preset])
    eye, fov = R["eye"], R["fov_h"]
    f = (w * 0.5) / math.tan(math.radians(fov) * 0.5)
    v_h = int(h * (0.46 if eye > 1.3 else 0.58))
    cx = w * R["vp_off"]
    Z_near = f * eye / float(h - 1 - v_h)          # 画框底边对应深度
    hw_near = f * (R["W"] * 0.5) / Z_near          # 地板近端半宽(px)
    return dict(preset=preset, seed=seed, w=w, h=h,
                horizon_y=v_h, vanish_x=cx, f=f, eye=eye,
                road_half_near=hw_near / float(w),
                W=R["W"], H=R["H"], D=R["D"],
                Z_near=Z_near, **{k: v for k, v in R.items()
                                  if k not in ("W", "H", "D", "eye", "fov_h", "vp_off")})


def proj(g, X, Y, Z):
    """世界坐标 → 屏幕。地面 Y=0：y = v_h + f*eye/Z（与 Cam.ground_y 同式）"""
    s = g["f"] / max(Z, 1e-3)
    return g["vanish_x"] + X * s, g["horizon_y"] + (g["eye"] - Y) * s


def _poly(d, pts, fill):
    p = [(int(round(x)), int(round(y))) for x, y in pts]
    d.polygon(p, fill=fill)


# ------------------------------------------------------------ 元件：房间壳
def draw_shell(cv, g):
    """地板/天花/左右侧墙/后墙。一点透视：VP 向画框四角连线"""
    w, h, f, vp = cv.w, cv.h, g["f"], g["vanish_x"]
    D, W, H = g["D"], g["W"], g["H"]
    d = cv.d
    # 后墙矩形（正对，Z=D）
    bx0, by0 = proj(g, -W / 2, H, D)
    bx1, by1 = proj(g, +W / 2, 0, D)
    g["back_wall"] = (bx0, by0, bx1, by1)
    # 近端（画框边，Z=Z_near）四角，会出画，由 polygon 自然裁剪
    nx0, ny0 = proj(g, -W / 2, H, g["Z_near"])
    nx1, ny1 = proj(g, +W / 2, 0, g["Z_near"])
    # 天花板 / 地板 / 左墙 / 右墙
    _poly(d, [(bx0, by0), (bx1, by0), (nx1, ny0), (nx0, ny0)], g["ceil"])
    _poly(d, [(bx0, by1), (bx1, by1), (nx1, ny1), (nx0, ny1)], g["floor"])
    _poly(d, [(bx0, by0), (bx0, by1), (nx0, ny1), (nx0, ny0)], g["wall"])
    _poly(d, [(bx1, by0), (bx1, by1), (nx1, ny1), (nx1, ny0)], g["wall"])
    # 后墙本身（略暗，作为视觉纵深底）
    d.rectangle([int(bx0), int(by0), int(bx1), int(by1)], fill=g["back"])
    return g


def draw_floor(cv, g, seed=7):
    """水磨石地面：彩点散布 r=r_min*(1+noise)，越远越小越淡（空气透视）"""
    d, rng = cv.d, np.random.default_rng(seed)
    D, W = g["D"], g["W"]
    base = _hx(g["floor"])
    chips = [(214, 198, 176), (168, 152, 138), (196, 176, 152), (150, 142, 132)]
    n = 1400
    Zs = g["Z_near"] + (D - g["Z_near"]) * rng.random(n) ** 0.55
    Xs = (rng.random(n) - 0.5) * W * 1.05
    for X, Z in zip(Xs, Zs):
        x, y = proj(g, X, 0.0, Z)
        if not (0 <= x < cv.w and 0 <= y < cv.h):
            continue
        r = max(0.6, 3.4 * (g["Z_near"] / Z) * (0.7 + 0.6 * rng.random()))
        t = 1.0 - min(1.0, (Z - g["Z_near"]) / max(D - g["Z_near"], 1e-3))
        c = _mix(base, chips[int(rng.random() * len(chips))], 0.35 + 0.45 * t)
        d.ellipse([x - r, y - r * 0.55, x + r, y + r * 0.55], fill=c)
    return g


def render(w, h, preset="咖啡馆", seed=7):
    cv = Canvas(w, h)
    g = make_geom(w, h, preset, seed)
    draw_shell(cv, g)
    draw_floor(cv, g, seed)
    return cv.img, g


if __name__ == "__main__":
    img, g = render(540, 960)
    img.save("室内_房间壳.png")
    print("后墙矩形 x[%.0f,%.0f] y[%.0f,%.0f]" % g["back_wall"])
    print("Z=3 地面 y=%.1f  Z=6 地面 y=%.1f" % (proj(g, 0, 0, 3)[1], proj(g, 0, 0, 6)[1]))
    print("saved 室内_房间壳.png")
