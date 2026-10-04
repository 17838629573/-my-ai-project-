# 契约: proc/scene/kit
#   一句话: 元件库：天空/云/山/树/草/花/城/路；路把几何写进 ctx 供房子避让
#   完整契约见 scene/__init__.py
# -*- coding: utf-8 -*-
"""kit —— 可组合场景元件库（L-A 静态层）

架构（与 bgpack 那种"五张整包"相对）：
    元件(elements) 各自独立建模：天空/云/山/草/树/房屋/路
    场景(scene) = 层列表（从远到近），用时拉出需要的元件拼装
    → "近处城市 + 远处山区" 这种组合不需要新增包，写层序即可

业界依据（modular kit）：
  - 一个设计良好的 30 件套能搭出一整个关卡；糟糕的 100 件套仍有缝隙
  - 所有元件共用同一套网格单位（此处 = 透视深度 t），才能无缝拼接
  - 命名带类型与尺寸

元件统一签名：
    draw(cv, ctx, **kw) -> None     # 直接画到 cv 上
    ctx 提供：w h horizon_y vanish_x fog_rgb depth_t rng biome

雾色即天空色：所有元件在远处都并入 ctx["fog_rgb"]，
这从构造上保证远景与天空同色（本项目 L3 层 dL 长期 FAIL 的根因）。
"""

import numpy as np
from PIL import Image, ImageDraw

from scene import detail

# ---------------------------------------------------------------- 画布

class Canvas:
    def __init__(self, w, h, bg=(0, 0, 0)):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w, h), bg)
        self.d = ImageDraw.Draw(self.img)

    def arr(self):
        return np.asarray(self.img).astype(np.float32)

    def set_arr(self, a):
        self.img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        self.d = ImageDraw.Draw(self.img)

    def blend_arr(self, a, alpha):
        """alpha: (h,w) 或 (h,w,1)，把 a 按 alpha 混到现有画面"""
        al = np.asarray(alpha, dtype=np.float32)
        if al.ndim == 2:
            al = al[:, :, None]
        cur = self.arr()
        cur = cur * (1 - al) + a * al
        self.set_arr(cur)


# ---------------------------------------------------------------- 噪声

def _hash2(x, y, seed=0.0):
    p = np.array([123.34, 345.45])
    xx = (np.asarray(x, dtype=np.float32) * p[0]) % 1.0
    yy = (np.asarray(y, dtype=np.float32) * p[1]) % 1.0
    dotv = xx * (xx + 34.345) + yy * (yy + 34.345) + seed
    return (np.sin(dotv) * 43758.5453123) % 1.0


def value_noise2(w, h, freq, seed=0.0):
    """2D value noise，返回 (h,w) ∈ [0,1]"""
    gx = np.arange(w, dtype=np.float32) / max(w, 1) * freq
    gy = np.arange(h, dtype=np.float32) / max(h, 1) * freq
    X, Y = np.meshgrid(gx, gy)
    ix, iy = np.floor(X), np.floor(Y)
    fx, fy = X - ix, Y - iy
    ux = fx * fx * (3 - 2 * fx)
    uy = fy * fy * (3 - 2 * fy)
    a = _hash2(ix, iy, seed)
    b = _hash2(ix + 1, iy, seed)
    c = _hash2(ix, iy + 1, seed)
    d = _hash2(ix + 1, iy + 1, seed)
    return (a * (1 - ux) + b * ux) * (1 - uy) + (c * (1 - ux) + d * ux) * uy


def fbm2(w, h, octaves=4, freq=5.0, seed=0.0, lacunarity=2.0, persistence=0.5):
    v = np.zeros((h, w), dtype=np.float32)
    amp, f, norm = 1.0, freq, 0.0
    for _ in range(octaves):
        v += amp * value_noise2(w, h, f, seed)
        norm += amp
        amp *= persistence
        f *= lacunarity
    return v / max(norm, 1e-9)


def smoothstep(a, b, x):
    t = np.clip((x - a) / max(b - a, 1e-9), 0.0, 1.0)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- 元件 1：天空

def draw_sky(cv, ctx, theta_s=0.9, T=2.8, **kw):
    """Preetham/Perez 解析亮度 × 非等距色标渐变"""
    w, h, hy = cv.w, cv.h, ctx["horizon_y"]
    fog = horizon_rgb(theta_s, T)
    ctx["fog_rgb"] = fog                      # ← 后续所有元件共用
    zenith = tuple(int(v * 0.40) for v in fog)

    arr = np.zeros((h, w, 3), dtype=np.float32)
    for y in range(hy):
        theta = (np.pi / 2.0) * (1.0 - y / float(max(hy - 1, 1)))
        lum = _perez(theta, theta_s, T)
        t = float(np.clip(lum, 0.0, 1.0))
        arr[y, :] = _ramp(fog, zenith, t)
    arr[hy:, :] = zenith
    cv.set_arr(arr)


def _perez_coeff(T):
    tab = [(2.0, 0.1787, -1.4630, -0.3554, 0.4274, -0.0227),
           (3.0, 0.1801, -1.4425, -0.3672, 0.4138, -0.0221),
           (4.0, 0.1814, -1.4219, -0.3790, 0.4002, -0.0215),
           (5.0, 0.1827, -1.4014, -0.3908, 0.3866, -0.0209),
           (6.0, 0.1840, -1.3809, -0.4026, 0.3730, -0.0203)]
    T = float(np.clip(T, 2.0, 6.0))
    for i in range(len(tab) - 1):
        t0, t1 = tab[i][0], tab[i + 1][0]
        if t0 <= T <= t1:
            u = (T - t0) / (t1 - t0)
            return tuple(tab[i][k] + (tab[i + 1][k] - tab[i][k]) * u
                         for k in range(1, 6))
    return tab[0][1:]


def _zenith_lum(T, theta_s):
    chi = (4.0 / 9.0 - T / 120.0) * (np.pi - 2.0 * theta_s)
    yz = (4.0453 * T - 4.9710) * np.tan(chi) - 0.2155 * T + 2.4192
    return max(yz, 0.05)          # Zotti 2007：负亮度保护


def _perez(theta, theta_s, T=2.5):
    T = float(np.clip(T, 2.0, 6.0))
    theta_s = float(np.clip(theta_s, 0.05, 1.45))
    theta = float(np.clip(theta, 0.0, 1.52))
    A, B, C, D, E = _perez_coeff(T)

    def F(th, gm=0.0):
        c = max(np.cos(th), 1e-4)
        return (1 + A * np.exp(B / c)) * (1 + C * np.exp(D * gm) + E * np.cos(gm) ** 2)

    return float(np.clip(F(theta) / max(abs(F(0.0, theta_s)), 1e-6), 0.0, 1.0))


def horizon_rgb(theta_s, T=2.5, warm=(255, 198, 132), cool=(72, 120, 180)):
    t = float(np.clip((theta_s - 0.15) / 1.05, 0.0, 1.0))
    base = [warm[i] + (cool[i] - warm[i]) * t for i in range(3)]
    haze = (238, 234, 226)
    wt = float(np.clip((T - 2.0) / 4.0, 0.0, 1.0)) * 0.55
    return tuple(int(base[i] + (haze[i] - base[i]) * wt) for i in range(3))


def _ramp(c0, c1, t, stops=(0.0, 0.18, 0.41, 1.0)):
    """非等距色标：等距四分之一读起来像 CSS，非等距才像画出来的"""
    t = float(np.clip(t, 0.0, 1.0))
    for i in range(len(stops) - 1):
        a, b = stops[i], stops[i + 1]
        if a <= t <= b:
            u = (t - a) / max(b - a, 1e-9)
            u = u * u * (3 - 2 * u)
            tt = a + (b - a) * u
            return np.array([c0[j] + (c1[j] - c0[j]) * tt for j in range(3)])
    return np.array(c1, dtype=np.float32)


# ---------------------------------------------------------------- 元件 2：云

def draw_cloud(cv, ctx, coverage=0.35, scale=5.0, seed=1.0, **kw):
    """stacked Perlin fBm + smoothstep 阈值
       业界：c = smoothstep(lo, hi, fbm(uv*scale))；out = mix(sky, white, c)"""
    w, h, hy = cv.w, cv.h, ctx["horizon_y"]
    n = fbm2(w, max(hy, 1), octaves=4, freq=scale, seed=seed)
    lo = 0.62 - coverage * 0.35
    hi = lo + 0.18
    c = smoothstep(lo, hi, n)

    # 云在天空带上：越靠地平线越薄（透视）
    vfade = np.linspace(0.15, 1.0, max(hy, 1))[:, None]
    c = c * vfade

    fog = np.array(ctx["fog_rgb"], dtype=np.float32)
    white = np.array([252, 250, 246], dtype=np.float32)
    cloudcol = white * 0.55 + fog * 0.45          # 云受雾色影响
    layer = fog[None, None, :] * (1 - c[:, :, None]) + cloudcol[None, None, :] * c[:, :, None]

    full = np.zeros((h, w, 3), dtype=np.float32)
    full[:hy] = layer
    cv.blend_arr(full, np.zeros((h, w), dtype=np.float32) + (np.arange(h)[:, None] < hy))


# ---------------------------------------------------------------- 元件 3：山

def draw_mountain(cv, ctx, layers=4, rough=0.62, amp=1.0, seed=2.0, **kw):
    """多层 midpoint displacement 山脊 + 等高色带，逐层并入雾色。

    注意：cv.arr() 返回副本，必须"读一次 → 整块写 → set_arr 一次"。
    逐列 arr()/set_arr() 不仅慢，而且赋值落在临时副本上，等于没画。
    """
    w, h, hy = cv.w, cv.h, ctx["horizon_y"]
    rng = np.random.RandomState(int(seed * 1000) % (2 ** 31))
    fog = np.array(ctx["fog_rgb"], dtype=np.float32)
    arr = cv.arr()                      # ← 只读一次

    for li in range(layers):
        depth_t = (layers - 1 - li) / float(max(layers - 1, 1))   # 0=最远
        base_y = hy + 4 + int((h - hy) * 0.055 * (li + 1))
        amp_px = 16.0 + 26.0 * (li + 1) / layers
        r = _ridge(rng, k=8, roughness=rough, amp=amp)
        ys = np.interp(np.linspace(0, len(r) - 1, w), np.arange(len(r)), r)
        ys = np.roll(ys, int(rng.uniform(-40, 40)))

        fade = (1.0 - depth_t) * 0.85      # 越远越并入雾色
        for x in range(w):
            top = int(np.clip(base_y - int(ys[x] * amp_px), 0, h - 1))
            bot = int(np.clip(base_y + amp_px * 1.15, 0, h - 1))
            if bot <= top:
                continue
            n = bot - top
            hh = np.linspace(1.0, 0.0, n)
            cols = np.stack([biome_color(0.62 + 0.33 * t, ctx.get("biome", BIOME_A))
                             for t in hh]).astype(np.float32)
            arr[top:bot, x, :] = cols + (fog[None, :] - cols) * fade
    cv.set_arr(arr)


def _ridge(rng, k=8, roughness=0.55, amp=1.0):
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


# ---------------------------------------------------------------- 元件 4：草/地

def draw_ground(cv, ctx, **kw):
    w, h, hy = cv.w, cv.h, ctx["horizon_y"]
    fog = np.array(ctx["fog_rgb"], dtype=np.float32)
    g = np.array(biome_color(0.50, ctx.get("biome", BIOME_A)), dtype=np.float32)
    dark = g * 0.60
    arr = cv.arr()
    for y in range(hy, h):
        t = (y - hy) / float(max(h - hy - 1, 1))
        c = g + (dark - g) * t
        arr[y, :] = c + (fog - c) * (1 - t) * 0.25
    cv.set_arr(arr)


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


def draw_grass(cv, ctx, **kw):
    detail.draw_grass(cv, ctx, **kw)


def draw_flowers(cv, ctx, **kw):
    detail.draw_flowers(cv, ctx, **kw)


def draw_crowd(cv, ctx, **kw):
    detail.draw_crowd(cv, ctx, **kw)


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


# ---------------------------------------------------------------- 配色（业界值）

BIOME_A = [
    (0.00, "深水", (0x32, 0x40, 0xC3)), (0.20, "浅水", (0x36, 0x67, 0xC7)),
    (0.30, "沙滩", (0xD2, 0xD0, 0x7D)), (0.37, "草地", (0x56, 0x98, 0x17)),
    (0.55, "草地2", (0x3E, 0x6B, 0x12)), (0.61, "岩石", (0x5A, 0x45, 0x3C)),
    (0.87, "岩石2", (0x4B, 0x3C, 0x35)), (1.00, "雪峰", (0xFF, 0xFF, 0xFF)),
]


def biome_color(hv, table=BIOME_A):
    for thr, _n, rgb in table:
        if hv < thr:
            return rgb
    return table[-1][2]


# ---------------------------------------------------------------- 元件注册表

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

def self_check():
    ok = True
    print("  元件清单:", list_elements())

    # 1. 组合场景可跑
    im, g = compose(SCENES["山区里的城市"], w=270, h=480)
    ok &= (im.size == (270, 480))
    print("  山区里的城市  :", im.size, "层序", g["elements"])

    # 2. 层序正确：mountain 在 city 之前（远→近）
    e = g["elements"]
    order_ok = e.index("mountain") < e.index("city")
    print("  远山先于近城  :", order_ok); ok &= order_ok

    # 3. 雾色被天空设定（所有元件共用）
    fog_ok = g["fog_rgb"] != (150, 160, 170)
    print("  雾色由sky设定 :", fog_ok, g["fog_rgb"]); ok &= fog_ok

    # 4. 确定性
    a1, _ = compose(SCENES["山野"], w=180, h=320)
    a2, _ = compose(SCENES["山野"], w=180, h=320)
    det = np.array_equal(np.asarray(a1), np.asarray(a2))
    print("  同场景确定性  :", det); ok &= det

    # 5. 云公式：coverage 越大云越多
    def cloud_frac(cov):
        n = fbm2(120, 80, octaves=4, freq=5.0, seed=1.0)
        lo = 0.62 - cov * 0.35
        return float((smoothstep(lo, lo + 0.18, n) > 0.5).mean())
    f1, f2 = cloud_frac(0.2), cloud_frac(0.6)
    mono = f2 > f1
    print("  云量随coverage:", mono, round(f1, 3), "→", round(f2, 3)); ok &= mono

    # 6. 树：三种参数给出不同剪影（分叉角生效）
    shapes = {}
    for k in ("松", "槐", "橡"):
        cv = Canvas(120, 200, (255, 255, 255))
        ctx = dict(w=120, h=200, horizon_y=100, vanish_x=60,
                   fog_rgb=(150, 160, 170), depth_t=1.0, biome=BIOME_A,
                   rng=np.random.RandomState(0))
        draw_tree(cv, ctx, x=60, ybase=180, height=90, kind=k, jitter=0.0, seed=1)
        a = np.asarray(cv.img.convert("L"))
        shapes[k] = int((a < 200).sum())
    diff_ok = len(set(shapes.values())) >= 2
    print("  树种剪影有别  :", diff_ok, shapes); ok &= diff_ok

    # 7. 未知元件必须报错（STUB 原则的前置）
    try:
        compose({"layers": [{"t": "火山"}]}, w=60, h=100)
        print("  未知元件报错  : False"); ok = False
    except KeyError as ex:
        print("  未知元件报错  : True"); ok &= True

    print("SELF_CHECK:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    self_check()
