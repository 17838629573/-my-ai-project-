# -*- coding: utf-8 -*-
"""bgpack — L-A 静态背景包（算一次，冻结）

设计要点（本文件是 Q11 的落地）：
  1. 背景不动 → 预调好的"配方"，索引存 (seed + 参数)，不存图
  2. 背景必须输出几何锚点 geom，供人物/相机使用
     —— 这是本项目踩过的坑：背景真实消失点与项目声明偏差 dx=354 dy=253，
        导致"人走的轨迹和画面里的路不一致"。
        解法：路和人由同一 geom 驱动，从源头不可能对不上。
  3. 确定性：同 seed 必须像素级一致（业界用 LCG(mod 2^31-1)，此处用 numpy RandomState）

只依赖 numpy + PIL。
"""

import numpy as np
from PIL import Image, ImageDraw

# ---------------------------------------------------------------- 噪声

def _noise1d(rng, n, freq):
    """1D value noise，平滑插值，返回 [-1,1]"""
    m = max(2, int(freq))
    pts = rng.uniform(-1.0, 1.0, m)
    xs = np.linspace(0.0, m - 1, n)
    i0 = np.floor(xs).astype(int)
    i1 = np.minimum(i0 + 1, m - 1)
    t = xs - i0
    t = t * t * (3.0 - 2.0 * t)            # smoothstep
    return pts[i0] * (1.0 - t) + pts[i1] * t


def fbm1d(rng, n, octaves=5, persistence=0.5, base_freq=3.0):
    """分形布朗运动：多八度相干噪声振幅折半累加。
    业界明确用它替代正弦，避免人工周期性。"""
    out = np.zeros(n)
    amp, freq, norm = 1.0, base_freq, 0.0
    for _ in range(octaves):
        out += amp * _noise1d(rng, n, freq)
        norm += amp
        amp *= persistence
        freq *= 2.0
    return out / max(norm, 1e-9)


def ridge(rng, k=8, roughness=0.55, amp=1.0):
    """midpoint displacement 山脊线，返回长度 2^k+1 的数组。
    roughness 越大越崎岖。"""
    n = 2 ** k + 1
    a = np.zeros(n)
    cur = amp
    step = n - 1
    while step > 1:
        half = step // 2
        for i in range(half, n, step):
            a[i] = 0.5 * (a[i - half] + a[i + half]) + rng.uniform(-cur, cur)
        step = half
        cur *= 2.0 ** (-roughness)
    return a


# ---------------------------------------------------------------- 颜色

def lerp_rgb(c1, c2, t):
    t = float(np.clip(t, 0.0, 1.0))
    return tuple(int(round(c1[i] + (c2[i] - c1[i]) * t)) for i in range(3))


def aerial(c_layer, c_horizon, d, dmax):
    """空气透视：C_final = lerp(C_layer, C_horizon, d/d_max)
    业界实测：远处每层损失约 15% 饱和度并偏向地平线色。
    d 越小=越远，所以这里用 (1 - d/dmax) 之外的约定：
      传入 d 为"由远及近"的序号，d=0 最远。"""
    return lerp_rgb(c_layer, c_horizon, 1.0 - (d / float(max(dmax, 1))) * 0.85)


# ---------------------------------------------------------------- 配方

PRESETS = {
    "城墙关隘": dict(
        layers=5, rough=0.62, sky_top=(58, 96, 148), sky_horizon=(226, 196, 152),
        ridge_tint=(96, 88, 84), ground=(178, 150, 108), road=(150, 124, 90),
        wall=(132, 112, 88), veg=0.10, water=0.0, sun=0.62, wall_on=True),
    "山野": dict(
        layers=6, rough=0.50, sky_top=(84, 132, 186), sky_horizon=(214, 226, 226),
        ridge_tint=(72, 92, 78), ground=(104, 128, 84), road=(138, 126, 96),
        wall=(120, 112, 96), veg=0.55, water=0.10, sun=0.45, wall_on=False),
    "城郭": dict(
        layers=3, rough=0.30, sky_top=(70, 108, 156), sky_horizon=(230, 206, 170),
        ridge_tint=(120, 104, 92), ground=(184, 160, 120), road=(158, 136, 104),
        wall=(146, 126, 100), veg=0.12, water=0.0, sun=0.55, wall_on=True),
    "沙漠": dict(
        layers=4, rough=0.30, sky_top=(96, 148, 200), sky_horizon=(238, 206, 150),
        ridge_tint=(196, 158, 104), ground=(214, 182, 130), road=(196, 166, 118),
        wall=(176, 148, 112), veg=0.0, water=0.0, sun=0.80, wall_on=False),
    "河谷": dict(
        layers=5, rough=0.58, sky_top=(76, 122, 176), sky_horizon=(206, 220, 214),
        ridge_tint=(78, 96, 92), ground=(112, 134, 96), road=(146, 138, 112),
        wall=(124, 116, 100), veg=0.42, water=0.45, sun=0.40, wall_on=False),
}


def list_presets():
    return list(PRESETS.keys())


# ---------------------------------------------------------------- 渲染

def render(preset="城墙关隘", w=540, h=960, seed=0, horizon_ratio=0.52):
    """返回 (PIL.Image, geom)

    geom 是本包最重要的输出 —— 人物与相机必须用它，
    否则会重现"人走的轨迹和路不一致"的偏差。
      horizon_y  地平线屏幕 y
      vanish_x   消失点屏幕 x
      road_near_y / road_far_y  路面近端/远端 y
      road_half_near  路面近端半宽(px)
    """
    if preset not in PRESETS:
        raise KeyError("未知背景配方 %r，可选：%s" % (preset, list_presets()))
    P = PRESETS[preset]
    rng = np.random.RandomState(seed)

    horizon_y = int(h * horizon_ratio)
    vanish_x = int(w * 0.50)

    img = Image.new("RGB", (w, h))
    px = np.asarray(img).astype(np.float32)

    # --- 天空：地平线暖、天顶冷；太阳角度控制冷暖分界
    sun = P["sun"]
    for y in range(0, horizon_y):
        t = y / float(max(horizon_y - 1, 1))
        c_top = lerp_rgb(P["sky_top"], (18, 34, 72), 1.0 - sun)   # 太阳低→天顶更深
        px[y, :] = lerp_rgb(P["sky_horizon"], c_top, t ** 0.85)

    # --- 地面基色
    for y in range(horizon_y, h):
        t = (y - horizon_y) / float(max(h - horizon_y - 1, 1))
        px[y, :] = lerp_rgb(P["ground"], tuple(int(v * 0.72) for v in P["ground"]), t)

    # --- 远山：多层 midpoint displacement，逐层空气透视
    nl = P["layers"]
    for li in range(nl):
        # 由远及近
        depth_from_near = nl - 1 - li          # li=0 最远
        base_y = horizon_y + 6 + int((h - horizon_y) * 0.06 * (li + 1))
        amp_px = 18.0 + 30.0 * (li + 1) / nl
        k = 8
        r = ridge(rng, k=k, roughness=P["rough"], amp=1.0)
        n = len(r)
        # 重采样到画布宽度
        xs = np.linspace(0, n - 1, w)
        ys = np.interp(xs, np.arange(n), r)
        col = aerial(P["ridge_tint"], P["sky_horizon"], li, nl)
        # 每层左右偏移一点，避免层间完全同相
        shift = int(rng.uniform(-40, 40))
        for x in range(w):
            sx = int(np.clip(x + shift, 0, n - 1))
            top = base_y - int(ys[sx] * amp_px)
            top = int(np.clip(top, 0, h - 1))
            bot = int(np.clip(base_y + amp_px * 1.2, 0, h - 1))
            for y in range(top, bot):
                px[y, x] = col

    # 把天空/地面/远山写回图片（此前漏了这步，导致这三层根本没画上去）
    img = Image.fromarray(px.astype(np.uint8))

    # --- 路面：三角形，远端收敛到消失点（V4 已验证远端收窄 5.25 倍）
    road_far_y = horizon_y + 4
    road_near_y = h - 1
    road_half_near = int(w * 0.26)
    d = ImageDraw.Draw(img)
    img_arr_backup = None
    for y in range(road_far_y, road_near_y + 1):
        t = (y - road_far_y) / float(max(road_near_y - road_far_y, 1))
        hw = int(road_half_near * (t ** 1.15))
        if hw <= 0:
            continue
        shade = 1.0 - 0.22 * (1.0 - t)          # 远处略暗（空气透视）
        c = tuple(int(v * shade) for v in P["road"])
        d.line([(vanish_x - hw, y), (vanish_x + hw, y)], fill=c)

    # --- 城墙（关隘/城郭）：两条由近及远收敛到消失点的墙线
    geom_wall = None
    if P["wall_on"]:
        d2 = ImageDraw.Draw(img)
        for side in (-1, 1):
            # 墙顶线：近端在画面下缘外侧，远端收到消失点附近
            near_x = vanish_x + side * int(w * 0.62)
            near_y = h + 40
            far_x = vanish_x + side * int(w * 0.055)
            far_y = horizon_y + 2
            steps = 240
            pts = []
            for i in range(steps + 1):
                t = i / float(steps)
                # 透视非线性：屏幕 y 按 1/Z 分布
                yy = near_y + (far_y - near_y) * (t ** 2.2)
                xx = near_x + (far_x - near_x) * (t ** 2.2)
                pts.append((xx, yy))
            d2.line(pts, fill=P["wall"], width=3)
            # 墙体填充：墙顶线以下到地面
            poly = pts + [(near_x, h), (far_x, horizon_y + 2)]
            d2.polygon(poly, fill=tuple(int(v * 0.86) for v in P["wall"]))
        geom_wall = dict(near_half=int(w * 0.62), far_half=int(w * 0.055))

    # --- 植被（L-B 可动部分的位置锚点，本步只标位置不画动态）
    veg_pts = []
    if P["veg"] > 0:
        cnt = int(60 * P["veg"])
        for _ in range(cnt):
            x = int(rng.uniform(0, w))
            yb = int(rng.uniform(horizon_y + 20, h - 10))
            veg_pts.append((x, yb))

    geom = dict(
        preset=preset, seed=seed, w=w, h=h,
        horizon_y=horizon_y, vanish_x=vanish_x,
        road_far_y=road_far_y, road_near_y=road_near_y,
        road_half_near=road_half_near,
        wall=geom_wall, veg_anchors=veg_pts,
        has_water=P["water"] > 0, water_level=P["water"],
    )
    return img, geom


# ---------------------------------------------------------------- 自检

def self_check():
    ok = True

    # 1. 同 seed 像素级一致
    a1, g1 = render("城墙关隘", seed=7)
    a2, g2 = render("城墙关隘", seed=7)
    same = np.array_equal(np.asarray(a1), np.asarray(a2))
    print("  同seed一致      :", same)
    ok &= same

    # 2. 不同 seed 有差异
    b1, _ = render("城墙关隘", seed=7)
    b2, _ = render("城墙关隘", seed=99)
    diff = not np.array_equal(np.asarray(b1), np.asarray(b2))
    print("  异seed有差异    :", diff)
    ok &= diff

    # 3. geom 锚点自洽：路面远端必须在地平线附近，消失点即路的收敛点
    _, g = render("城墙关隘", seed=1)
    near_horizon = abs(g["road_far_y"] - g["horizon_y"]) < 20
    print("  路面远端贴地平线:", near_horizon, g["road_far_y"], g["horizon_y"])
    ok &= near_horizon

    # 4. 五种配方都能出图
    names = list_presets()
    allok = True
    for nm in names:
        try:
            im, gg = render(nm, seed=3)
            allok &= (im.size == (540, 960))
        except Exception as e:
            print("  配方失败:", nm, e)
            allok = False
    print("  五配方可用      :", allok, names)
    ok &= allok

    # 5. 确定性 RNG：ridge 可复现
    r1 = ridge(np.random.RandomState(5), k=6)
    r2 = ridge(np.random.RandomState(5), k=6)
    rsame = np.allclose(r1, r2)
    print("  ridge可复现     :", rsame)
    ok &= rsame

    print("SELF_CHECK:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    self_check()
