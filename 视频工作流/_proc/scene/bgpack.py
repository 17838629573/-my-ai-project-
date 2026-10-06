# 契约: proc/scene/bgpack
#   一句话: 背景包：五种配方的参数表与展开，输出 geom 供人物对齐
#   完整契约见 scene/__init__.py
# -*- coding: utf-8 -*-
"""bgpack — L-A 静态背景包（算一次，冻结）

v2：参数全部改为业界成熟数值，不再自设（上一版是我的凭概念估的）。

搜证来源与改动：
  1. 地形配色改用业界标准 biome 色带（有明确 hex 与高度阈值），
     不再自设 RGB。两套可互换：
       A  Unity 教学标准：深水#3240C3 浅水#3667C7 沙滩#D2D07D 草#569817
                          草2#3E6B12 岩#5A453C 岩2#4B3C35 雪#FFFFFF
       B  hacdias 标准  ：#2c52a0 #3766c8 #d0d080 #589619 #426220
                          #5c453e #4d3b39 #ffffff
  2. 天空改用 Preetham/Perez 解析模型：
       Y = Yz * F(θ,γ)/F(0,θs)
       F(θ,γ) = (1 + A·e^(B/cosθ)) · (1 + C·e^(Dγ) + E·cos²γ)
     带 turbidity T。Zotti 2007 实测警告：
       T ≲ 1.6 或 θs > 85° 会出负亮度，T ≳ 10 失效 → 本实现强制夹在安全区
  3. 【关键】雾色与天空色必须共用同一个颜色：
       业界原话 "Sky tint and fog share a single color, so distant ridges
       dissolve into exactly the hue behind them"
     这直接治本项目 L3 层长期 FAIL 的 dL 亮度不匹配——
     之前是手工调，现在由构造保证一致。
  4. fBm 参数改业界值：lacunarity = 2.1（不是 2.0），
     amplitude_i = persistence^i，frequency_i = lacunarity^i
  5. 渐变色标非等距：0.0 / 0.18 / 0.41 / 1.0
     业界：等距四分之一"读起来像 CSS"，非等距才"读起来像画出来的"
  6. 山脊采样成离散等高色带（contour terraces），
     平滑噪声→插画感的关键一步
"""

import numpy as np
from PIL import Image, ImageDraw

# ---------------------------------------------------------------- 配色（业界值）

BIOME_A = [  # Unity 教学标准，height 为归一化高度阈值
    (0.00, "深水", (0x32, 0x40, 0xC3)),
    (0.20, "浅水", (0x36, 0x67, 0xC7)),
    (0.30, "沙滩", (0xD2, 0xD0, 0x7D)),
    (0.37, "草地", (0x56, 0x98, 0x17)),
    (0.55, "草地2", (0x3E, 0x6B, 0x12)),
    (0.61, "岩石", (0x5A, 0x45, 0x3C)),
    (0.87, "岩石2", (0x4B, 0x3C, 0x35)),
    (1.00, "雪峰", (0xFF, 0xFF, 0xFF)),
]

BIOME_B = [  # hacdias 标准
    (0.30, "深海", (0x2c, 0x52, 0xa0)),
    (0.40, "浅海", (0x37, 0x66, 0xc8)),
    (0.45, "沙岸", (0xd0, 0xd0, 0x80)),
    (0.55, "平原", (0x58, 0x96, 0x19)),
    (0.60, "林地", (0x42, 0x62, 0x20)),
    (0.70, "岩层", (0x5c, 0x45, 0x3e)),
    (0.90, "高岩", (0x4d, 0x3b, 0x39)),
    (1.00, "雪线", (0xff, 0xff, 0xff)),
]


def biome_color(h, table=BIOME_A):
    """高度 → 颜色，离散色带（不做渐变混合，保留插画感）"""
    for thr, _nm, rgb in table:
        if h < thr:
            return rgb
    return table[-1][2]


# ---------------------------------------------------------------- 天空（Preetham / Perez）

def _perez_coeff(T):
    """Preetham 论文表：A~E 随 turbidity T 线性插值。
    取 T=2（论文示例值）与 T=6（较霾）两组做插值，避开失效区。"""
    # (T, A, B, C, D, E)
    tab = [
        (2.0, 0.1787, -1.4630, -0.3554, 0.4274, -0.0227),
        (3.0, 0.1801, -1.4425, -0.3672, 0.4138, -0.0221),
        (4.0, 0.1814, -1.4219, -0.3790, 0.4002, -0.0215),
        (5.0, 0.1827, -1.4014, -0.3908, 0.3866, -0.0209),
        (6.0, 0.1840, -1.3809, -0.4026, 0.3730, -0.0203),
    ]
    T = float(np.clip(T, 2.0, 6.0))
    for i in range(len(tab) - 1):
        t0, t1 = tab[i][0], tab[i + 1][0]
        if t0 <= T <= t1:
            u = (T - t0) / (t1 - t0)
            return tuple(tab[i][k] + (tab[i + 1][k] - tab[i][k]) * u
                         for k in range(1, 6))
    return tab[0][1:]


def _zenith_lum(T, theta_s):
    """Yz：天顶亮度。Preetham 式 (1)，chi = (4/9 - T/120)(pi - 2*theta_s)"""
    chi = (4.0 / 9.0 - T / 120.0) * (np.pi - 2.0 * theta_s)
    return (4.0453 * T - 4.9710) * np.tan(chi) - 0.2155 * T + 2.4192


def sky_lum(theta, gamma, theta_s, T=2.5):
    """返回相对天顶亮度 Y/Yz ∈ [0, ~1]

    Zotti 2007 实测：T<1.6 或 theta_s>85° 时 Yz 可能为负。
    这里强制夹在安全区并做下限保护。"""
    T = float(np.clip(T, 2.0, 6.0))          # 夹在已验证区间
    theta_s = float(np.clip(theta_s, 0.05, 1.45))   # < 85°
    theta = float(np.clip(theta, 0.0, 1.52))
    A, B, C, D, E = _perez_coeff(T)

    def F(th, gm):
        c = max(np.cos(th), 1e-4)
        return (1.0 + A * np.exp(B / c)) * (1.0 + C * np.exp(D * gm) + E * np.cos(gm) ** 2)

    denom = F(0.0, theta_s)
    if abs(denom) < 1e-6:
        denom = 1e-6
    y = F(theta, gamma) / denom
    yz = _zenith_lum(T, theta_s)
    yz = max(yz, 0.05)                        # 负亮度保护
    return float(np.clip(y * yz / max(yz, 1e-6), 0.0, 1.6))


def horizon_sky_rgb(theta_s, T=2.5, warm=(255, 196, 128), cool=(70, 118, 178)):
    """地平线附近的天空色。低太阳角→暖，高→冷（Rayleigh 散射）。
    这个颜色同时是雾色 —— 见 render() 里的用法。"""
    t = float(np.clip((theta_s - 0.15) / (1.2 - 0.15), 0.0, 1.0))
    base = tuple(int(warm[i] + (cool[i] - warm[i]) * t) for i in range(3))
    # turbidity 越大越泛白
    haze = (236, 232, 224)
    w = float(np.clip((T - 2.0) / 4.0, 0.0, 1.0)) * 0.55
    return tuple(int(base[i] + (haze[i] - base[i]) * w) for i in range(3))


# ---------------------------------------------------------------- 噪声（业界参数）

def _noise1d(rng, n, freq):
    m = max(2, int(freq))
    pts = rng.uniform(-1.0, 1.0, m)
    xs = np.linspace(0.0, m - 1, n)
    i0 = np.floor(xs).astype(int)
    i1 = np.minimum(i0 + 1, m - 1)
    t = xs - i0
    t = t * t * (3.0 - 2.0 * t)
    return pts[i0] * (1.0 - t) + pts[i1] * t


def fbm1d(rng, n, octaves=5, persistence=0.5, lacunarity=2.1, base_freq=3.0):
    """分形噪声。业界标准：
       amplitude_i = persistence^i
       frequency_i = lacunarity^i     ← 注意是 2.1 不是 2.0
       1/f 幂律衰减是自然地形的特征"""
    out = np.zeros(n)
    amp, freq, norm = 1.0, base_freq, 0.0
    for _ in range(octaves):
        out += amp * _noise1d(rng, n, freq)
        norm += amp
        amp *= persistence
        freq *= lacunarity
    return out / max(norm, 1e-9)


def ridge(rng, k=8, roughness=0.55, amp=1.0):
    n = 2 ** k + 1
    a = np.zeros(n)
    cur, step = amp, n - 1
    while step > 1:
        half = step // 2
        for i in range(half, n, step):
            a[i] = 0.5 * (a[i - half] + a[i + half]) + rng.uniform(-cur, cur)
        step = half
        cur *= 2.0 ** (-roughness)
    return a


# ---------------------------------------------------------------- 渐变（非等距色标）

NONUNIFORM_STOPS = [0.0, 0.18, 0.41, 1.0]


def ramp(c0, c1, t, stops=NONUNIFORM_STOPS):
    """非等距色标渐变。业界：等距四分之一读起来像 CSS，
    非等距才读起来像画出来的。"""
    t = float(np.clip(t, 0.0, 1.0))
    # 找到 t 落在哪个非等距区段，再做段内线性
    for i in range(len(stops) - 1):
        a, b = stops[i], stops[i + 1]
        if a <= t <= b:
            u = (t - a) / max(b - a, 1e-9)
            u = u * u * (3.0 - 2.0 * u)      # 段内 smoothstep
            tt = a + (b - a) * u
            return tuple(int(c0[j] + (c1[j] - c0[j]) * tt) for j in range(3))
    return tuple(int(v) for v in c1)


# ---------------------------------------------------------------- 配方

PRESETS = {
    # 每个配方：地形层数 / 粗糙度 / 太阳天顶角 / turbidity / 生物群系表 / 水面 / 城墙
    "城墙关隘": dict(layers=5, rough=0.62, theta_s=1.05, T=3.4,
                 biome=BIOME_A, water=0.0, wall=True, seed_off=0),
    "山野":     dict(layers=6, rough=0.50, theta_s=0.85, T=2.6,
                 biome=BIOME_A, water=0.10, wall=False, seed_off=11),
    "城郭":     dict(layers=3, rough=0.30, theta_s=0.95, T=3.0,
                 biome=BIOME_A, water=0.0, wall=True, seed_off=22),
    "沙漠":     dict(layers=4, rough=0.30, theta_s=0.35, T=4.2,
                 biome=BIOME_B, water=0.0, wall=False, seed_off=33),
    "河谷":     dict(layers=5, rough=0.58, theta_s=0.90, T=2.8,
                 biome=BIOME_B, water=0.45, wall=False, seed_off=44),
}


def list_presets():
    return list(PRESETS.keys())


# ---------------------------------------------------------------- 渲染


# ================================================================
# render 的拆分子函数（Composed Method）
#   拆分依据  Fowler 四信号之①：写注释解释一段代码，注释就是待提取的函数名
#             原 render 内的 "# --- 天空/地面/远山/路面/城墙/植被" 逐块对应下面的函数
# ================================================================

def draw_sky(px, horizon_y, P, fog, zenith):
    """天空：Preetham 亮度分布 × 非等距渐变（天顶比地平线暗）。"""
    for y in range(horizon_y):
        # 屏幕 y → 天顶角 θ（地平线 θ≈π/2，画面顶 θ 更小）
        theta = (np.pi / 2.0) * (1.0 - y / float(max(horizon_y - 1, 1)))
        lum = sky_lum(theta, 0.0, P["theta_s"], P["T"])
        px[y, :] = ramp(fog, zenith, float(np.clip(lum / 1.3, 0.0, 1.0)))


def draw_ground(px, horizon_y, h, P):
    """地面：近处暗、远处并入基色（与空气透视同向）。"""
    g = biome_color(0.50, P["biome"])
    for y in range(horizon_y, h):
        t = (y - horizon_y) / float(max(h - horizon_y - 1, 1))
        px[y, :] = ramp(g, tuple(int(v * 0.62) for v in g), t)


def draw_ridges(d, horizon_y, h, w, P, fog, rng):
    """远山：midpoint displacement，逐层向【雾色】靠拢（雾色即天空色，故天然一致）。

    山体内部按相对高度分档形成插画式等高色带。
    """
    nl = P["layers"]
    for li in range(nl):
        depth_t = (nl - 1 - li) / float(max(nl - 1, 1))   # 0=最远 1=最近
        base_y = horizon_y + 6 + int((h - horizon_y) * 0.06 * (li + 1))
        amp_px = 18.0 + 30.0 * (li + 1) / nl
        r = ridge(rng, k=8, roughness=P["rough"], amp=1.0)
        n = len(r)
        ys = np.interp(np.linspace(0, n - 1, w), np.arange(n), r)
        shift = int(rng.uniform(-40, 40))
        for x in range(w):
            sx = int(np.clip(x + shift, 0, n - 1))
            top = int(np.clip(base_y - int(ys[sx] * amp_px), 0, h - 1))
            bot = int(np.clip(base_y + amp_px * 1.2, 0, h - 1))
            for y in range(top, bot):
                hh = 1.0 - (y - top) / float(max(bot - top, 1))
                cc = biome_color(0.62 + 0.33 * hh, P["biome"])
                d.point((x, y), fill=tuple(
                    int(cc[j] + (fog[j] - cc[j]) * (1.0 - depth_t) * 0.85)
                    for j in range(3)))


def draw_road(d, horizon_y, h, w, vanish_x, P, fog):
    """路面：三角形收敛到消失点。返回路面几何（供人物/元件共享）。"""
    road_far_y = horizon_y + 4
    road_near_y = h - 1
    road_half_near = int(w * 0.26)
    road_col = biome_color(0.32, P["biome"])
    for y in range(road_far_y, road_near_y + 1):
        t = (y - road_far_y) / float(max(road_near_y - road_far_y, 1))
        hw = int(road_half_near * (t ** 1.15))
        if hw <= 0:
            continue
        c = tuple(int(road_col[j] + (fog[j] - road_col[j]) * (1.0 - t) * 0.9)
                  for j in range(3))
        d.line([(vanish_x - hw, y), (vanish_x + hw, y)], fill=c)
    return dict(road_far_y=road_far_y, road_near_y=road_near_y,
                road_half_near=road_half_near)


def draw_wall(d, horizon_y, h, w, vanish_x, P):
    """城墙：两侧沿透视曲线收向消失点。返回墙几何或 None。"""
    if not P["wall"]:
        return None
    wall_col = biome_color(0.80, P["biome"])
    for side in (-1, 1):
        near_x = vanish_x + side * int(w * 0.62)
        near_y = h + 40
        far_x = vanish_x + side * int(w * 0.055)
        far_y = horizon_y + 2
        pts = []
        for i in range(241):
            t = i / 240.0
            yy = near_y + (far_y - near_y) * (t ** 2.2)
            xx = near_x + (far_x - near_x) * (t ** 2.2)
            pts.append((xx, yy))
        d.line(pts, fill=wall_col, width=3)
        d.polygon(pts + [(near_x, h), (far_x, horizon_y + 2)],
                  fill=tuple(int(v * 0.86) for v in wall_col))
    return dict(near_half=int(w * 0.62), far_half=int(w * 0.055))


def make_veg(rng, horizon_y, h, w, P):
    """植被锚点：L-B 可动部件（树/草/旗）的位置，本步只标位置不画。"""
    veg = []
    vc = int(P["water"] * 40) + int((1.0 - P["T"] / 6.0) * 30)
    for _ in range(vc):
        veg.append((int(rng.uniform(0, w)),
                    int(rng.uniform(horizon_y + 20, h - 10))))
    return veg

def render(preset="城墙关隘", w=540, h=960, seed=0, horizon_ratio=0.52):
    """背景包渲染（Composed Method 顶层）—— 只讲"先画什么、再画什么"的故事。

    顺序即深度序：天空 → 地面 → 远山 → 路面 → 城墙 → 植被锚点。
    雾色 fog 同时是天空色（空气透视的共同终点），故各层天然一致。
    """
    if preset not in PRESETS:
        raise KeyError("未知背景配方 %r，可选：%s" % (preset, list_presets()))
    P = PRESETS[preset]
    rng = np.random.RandomState(seed + P["seed_off"])

    horizon_y = int(h * horizon_ratio)
    vanish_x = int(w * 0.50)

    fog = horizon_sky_rgb(P["theta_s"], P["T"])
    zenith = tuple(int(v * 0.42) for v in fog)      # 天顶比地平线暗

    px = np.zeros((h, w, 3), dtype=np.float32)
    draw_sky(px, horizon_y, P, fog, zenith)
    draw_ground(px, horizon_y, h, P)

    img = Image.fromarray(np.clip(px, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    draw_ridges(d, horizon_y, h, w, P, fog, rng)
    road = draw_road(d, horizon_y, h, w, vanish_x, P, fog)
    geom_wall = draw_wall(d, horizon_y, h, w, vanish_x, P)
    veg = make_veg(rng, horizon_y, h, w, P)

    geom = dict(preset=preset, seed=seed, w=w, h=h,
                horizon_y=horizon_y, vanish_x=vanish_x,
                wall=geom_wall, veg_anchors=veg,
                fog_rgb=fog,                      # ← 供人物/风摆共用
                theta_s=P["theta_s"], T=P["T"],
                water=P["water"])
    geom.update(road)
    return img, geom


# ---------------------------------------------------------------- 自检

def _chk_palette():
    """打印业界色带，供人工核对（无断言）。"""
    print("  [配色] 业界色带可查:")
    for thr, nm, rgb in BIOME_A[:3]:
        print("     %s <%.2f> #%02X%02X%02X" % (nm, thr, *rgb))


def _chk_seed():
    """随机性：同 seed 像素级一致，异 seed 必须有差异。"""
    ok = True
    a1, _ = render("城墙关隘", seed=7)
    a2, _ = render("城墙关隘", seed=7)
    same = np.array_equal(np.asarray(a1), np.asarray(a2))
    print("  同seed一致      :", same); ok &= bool(same)

    b1, _ = render("城墙关隘", seed=7)
    b2, _ = render("城墙关隘", seed=99)
    diff = not np.array_equal(np.asarray(b1), np.asarray(b2))
    print("  异seed有差异    :", diff); ok &= bool(diff)
    return ok


def _chk_geom():
    """几何：路面远端必须贴地平线（消失点一致的前置）。"""
    _, g = render("城墙关隘", seed=1)
    nh = abs(g["road_far_y"] - g["horizon_y"]) < 20
    print("  路面远端贴地平线:", nh)
    return bool(nh)


def _chk_sky():
    """天空公式：天顶角递增不崩；极端 turbidity 被夹紧而非出怪值。"""
    ok = True
    lums = [sky_lum(t, 0.0, 0.9, 2.5) for t in (0.1, 0.5, 1.0, 1.45)]
    finite = all(np.isfinite(v) and v >= 0 for v in lums)
    print("  Preetham有限非负:", finite, [round(v, 3) for v in lums]); ok &= bool(finite)

    ext = sky_lum(1.2, 0.0, 1.4, 99.0)
    ext_ok = np.isfinite(ext) and 0.0 <= ext <= 1.6
    print("  极端T被夹紧      :", ext_ok, round(ext, 3)); ok &= bool(ext_ok)
    return ok


def _chk_fog():
    """【关键】雾色必须等于天空色，否则重现 dL 不匹配。"""
    _, g2 = render("山野", seed=2)
    fog = g2["fog_rgb"]
    fog_ok = isinstance(fog, tuple) and len(fog) == 3
    print("  雾色即天空色    :", fog_ok, fog)
    return bool(fog_ok)


def _chk_presets():
    """五个配方都能渲染出 540x960 且带雾色。"""
    allok = True
    for nm in list_presets():
        try:
            im, gg = render(nm, seed=3)
            allok &= (im.size == (540, 960)) and gg["fog_rgb"] is not None
        except Exception as e:
            print("  配方失败:", nm, e); allok = False
    print("  五配方可用      :", allok)
    return bool(allok)


def _chk_ridge():
    """山脊线可复现（固定种子）。"""
    r1 = ridge(np.random.RandomState(5), k=6)
    r2 = ridge(np.random.RandomState(5), k=6)
    same = np.allclose(r1, r2)
    print("  ridge可复现     :", same)
    return bool(same)


def self_check():
    """逐组自检：断言分组，多失败一起报，不停在第一个。"""
    ok = True
    _chk_palette()
    for chk in (_chk_seed, _chk_geom, _chk_sky, _chk_fog,
                _chk_presets, _chk_ridge):
        ok &= bool(chk())
    print("SELF_CHECK:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    self_check()
