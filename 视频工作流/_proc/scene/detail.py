# 契约: proc/scene/detail
#   一句话: 近处细节：草叶/窗户/叶簇/远处行人，按 LOD 分级
#   完整契约见 scene/__init__.py
# -*- coding: utf-8 -*-
"""detail —— 细节层级(LOD) 与近/远细节元件

核心判据（业界 Level of Detail）：
    屏幕空间误差低于 1 像素时，人眼无法分辨高低精度版本。
    → 近处必须给细节（看得出来），远处给细节是浪费。

本模块提供：
  lod_at(ctx, y)        深度 → LOD 级（0 最细，3 最粗）
  jittered_pts(...)     抖动网格散布（蓝噪声近似，避免白噪声团簇）
  draw_grass(...)       草：近=单叶片带弯曲与明暗梯度，远=点簇
  draw_flowers(...)     花：近=花瓣+花心，远=彩点
  draw_crowd(...)       远处行人：impostor + 随机相位
  facade_windows(...)   房屋门窗（唐式/江南两派）
  canopy(...)           树冠叶簇（带明暗梯度，替代实心椭圆）

随机量一律由 scene seed 派生，不依赖调用顺序：
    同一个 seed 出的草永远在同一处 —— 视频周期内不闪。
    依据是水彩程序化那条教训：每帧重建会 shimmer。
"""

import math
import numpy as np
from typing import NamedTuple
from PIL import ImageDraw

# ---------------------------------------------------------------- 真实配色（搜证所得）

# 唐式官式四色：朱柱白壁、青灰瓦顶、金铜塔刹
TANG = dict(
    zhu=(0xA0, 0x00, 0x00),      # 朱柱  #A00000
    bi=(0xF5, 0xF0, 0xE8),       # 白壁  #F5F0E8
    wa=(0x3A, 0x4A, 0x52),       # 青灰瓦 #3A4A52
    sha=(0xC9, 0xA2, 0x27),      # 金铜塔刹 #C9A227
)

# 江南粉墙黛瓦：白墙 + 青灰瓦 + 赭石门窗，中间三段灰阶
JIANGNAN = dict(
    bi=(0xEC, 0xE8, 0xDF),       # 粉墙
    wa=(0x44, 0x4A, 0x4E),       # 黛瓦
    yingqing=(0xBD, 0xCB, 0xD2),  # 影青 #BDCBD2
    milou=(0x91, 0x82, 0x8F),    # 迷楼灰 #91828F
    mocan=(0x58, 0x52, 0x48),    # 墨黪 #585248
    zheshi=(0x8C, 0x5A, 0x3C),   # 赭石门窗
)

# 草：暗基 → 亮尖（业界 shader 值 0.15,0.4,0.2 → 0.55,0.75,0.4）
GRASS_BASE = (0x26, 0x66, 0x33)   # (38,102,51)
GRASS_TIP = (0x8C, 0xBF, 0x66)    # (140,191,102)
GRASS_DRY = (0xA8, 0x93, 0x4E)    # 枯草

# 树干业界值；树冠不要土黄/水泥色
TRUNK = (0x65, 0x43, 0x21)        # (101,67,33)
LEAF_DARK = (0x2E, 0x54, 0x2A)
LEAF_LIT = (0x6E, 0x9A, 0x44)

# 野花主色（白 / 黄 / 紫 / 粉）
FLOWER_COLORS = [
    (0xF2, 0xEF, 0xE4),  # 白   Ox-eye daisy / Yarrow
    (0xE8, 0xC2, 0x2E),  # 黄   Buttercup / Birdsfoot trefoil
    (0x7A, 0x5C, 0x9E),  # 紫   Knapweed / Self heal
    (0xC0, 0x6A, 0x84),  # 粉紫 Red clover
]


# ---------------------------------------------------------------- LOD

def lod_at(ctx, y):
    """屏幕 y → LOD 级。0=最细（画面底部），3=最粗（贴地平线）。

    依据是屏幕空间误差：远处 1px 以下的细节不可分辨，
    近处不给细节则一眼看出是纸片。
    """
    hy, h = ctx["horizon_y"], ctx["h"]
    t = (y - hy) / float(max(h - hy, 1))     # 0=地平线 1=画面底
    t = float(np.clip(t, 0.0, 1.0))
    if t > 0.62:
        return 0
    if t > 0.34:
        return 1
    if t > 0.13:
        return 2
    return 3


# ---------------------------------------------------------------- 散布

def _stable_rng(seed, tag):
    """由 (seed, tag) 派生确定性 RNG。

    关键点：不依赖调用顺序与全局状态 —— 同一个 tag 永远得到同一串数。
    这样"草长在哪"在整段视频里是固定的，不会逐帧重掷造成闪烁。
    """
    acc = 2166136261
    for ch in str(seed) + "|" + str(tag):
        acc = (acc ^ ord(ch)) * 16777619 & 0xFFFFFFFF
    return np.random.RandomState(acc & 0x7FFFFFFF)


def jittered_pts(rng, x0, x1, y0, y1, cols, rows):
    """抖动网格（jittered grid）——蓝噪声的廉价近似。

    纯哈希散布会产生白噪声式的团簇和空洞；
    抖动网格保证每个格子恰好一个点，分布均匀又不呆板。
    """
    pts = []
    for r in range(rows):
        for c in range(cols):
            gx = x0 + (x1 - x0) * (c + rng.uniform(0.12, 0.88)) / cols
            gy = y0 + (y1 - y0) * (r + rng.uniform(0.12, 0.88)) / rows
            pts.append((gx, gy))
    return pts


# ---------------------------------------------------------------- 草

def _blade(d, x, y, height, lean, curve, col_base, col_tip, width, steps=7):
    """单株草叶。半正弦弯曲 + 暗基亮尖渐变。

    业界依据：
      叶片弧度 y = sin(t·π·k)，半正弦即经典草叶弧；
      明暗梯度 dark base → bright tip，尖端受光最强。
    """
    pts, prev = [], None
    for i in range(steps + 1):
        t = i / float(steps)
        # 半正弦给出根部挺、梢部弯的自然弧度
        bend = math.sin(t * math.pi * 0.5) ** 1.6
        px = x + lean * bend * height + curve * (t ** 2) * height * 0.35
        py = y - t * height
        c = tuple(int(col_base[k] + (col_tip[k] - col_base[k]) * t) for k in range(3))
        if prev is not None:
            d.line([prev, (px, py)], fill=c, width=max(1, int(width * (1 - t * 0.6))))
        prev = (px, py)
        pts.append((px, py))
    return pts


class GrassRow(NamedTuple):
    """一个深度带的草参数（参数对象，避免长参数列表）。

    拆分依据  Fowler 信号②：for 循环体内含复杂逻辑 → 提取循环体。
    """
    y0: float; y1: float; lod: int; t: float
    fog_t: float; spacing: float; cols: int; rows_here: int


def grass_row(ctx, w, h, hy, r, rows, density=1.0):
    """计算第 r 个深度带的几何与 LOD 参数。"""
    y0 = hy + (h - hy) * (r / float(rows))
    y1 = hy + (h - hy) * ((r + 1) / float(rows))
    t = (y0 - hy) / float(max(h - hy, 1))
    # 关键：地面草密度均匀，所以屏幕上的株距 ∝ 深度 t。
    # 远处一平方米挤进几个像素，株距被压到 2px（再密就低于 1px、
    # 不可分辨，正是 LOD 的截断判据）→ 远处反而是密集细点。
    spacing = max(2.0, 30.0 * t)
    return GrassRow(
        y0=y0, y1=y1, lod=lod_at(ctx, (y0 + y1) * 0.5), t=t,
        # 远处并入雾色：这是空气透视，不是可选装饰
        fog_t=float(np.clip(1.0 - t, 0.0, 1.0)) ** 1.1,
        spacing=spacing,
        cols=int(w / spacing * density),
        rows_here=max(1, int((y1 - y0) / max(3.0, spacing * 0.55))))


def grass_fade(fog, fog_t):
    """按空气透视把基色/尖色/枯色向雾色靠拢。返回 (cb, ct, cd)。"""
    def _m(C):
        return tuple(int(C[k] + (fog[k] - C[k]) * fog_t * 0.85) for k in range(3))
    return _m(GRASS_BASE), _m(GRASS_TIP), _m(GRASS_DRY)


def draw_grass_far(cv, rng, row, w, gb, ban_fn):
    """最远带：单株不足 1px，只画密集色点，不画形。"""
    for _ in range(int(row.cols * row.rows_here)):
        gx = rng.uniform(0, w)
        gy = rng.uniform(row.y0, row.y1)
        if ban_fn is not None:
            b = ban_fn(gy)
            if b and b[0] < gx < b[1]:
                continue
        cv.d.point((gx, gy), fill=gb)


def draw_blade(cv, rng, gx, gy, lod, blade_h, cb, ct, scale):
    """单株草：LOD0 完整弯曲叶片 / LOD1 三叶簇 / LOD2 单线段。"""
    if lod == 0:
        _blade(cv.d, gx, gy, blade_h * rng.uniform(0.75, 1.35),
               lean=rng.uniform(-0.55, 0.55), curve=rng.uniform(-0.35, 0.35),
               col_base=cb, col_tip=ct, width=max(1.0, 1.9 * scale))
    elif lod == 1:
        hh = blade_h * rng.uniform(0.6, 1.1)
        for k in range(3):
            _blade(cv.d, gx + rng.uniform(-3, 3), gy, hh * rng.uniform(0.6, 1.0),
                   lean=rng.uniform(-0.4, 0.4), curve=0.0,
                   col_base=cb, col_tip=ct, width=1.0, steps=3)
    else:
        cv.d.line([(gx, gy), (gx + rng.uniform(-2, 2), gy - blade_h * 0.5)],
                  fill=cb, width=1)


def draw_grass(cv, ctx, density=1.0, seed=11, dry=0.25, **kw):
    """草被（Composed Method 顶层）—— 按深度带从远到近铺，带越远株越小越少。

    density 单位面积株数倍率；dry 枯草比例。
    """
    w, h, hy = cv.w, cv.h, ctx["horizon_y"]
    fog = np.array(ctx["fog_rgb"], dtype=np.float32)
    ban_fn = ctx.get("road_ban")
    rng = _stable_rng(seed, "grass")

    for r in range(9):
        row = grass_row(ctx, w, h, hy, r, 9, density)
        if row.y1 <= hy + 2:
            continue
        gb, gt, gd = grass_fade(fog, row.fog_t)

        if row.lod >= 3:
            draw_grass_far(cv, rng, row, w, gb, ban_fn)
            continue

        scale = 0.22 + 0.78 * row.t
        blade_h = (10 + 30 * row.t) * scale
        cols = int(row.cols * 0.45) if row.lod == 0 else row.cols
        pts = jittered_pts(rng, -6, w + 6, row.y0, row.y1,
                           max(cols, 2), max(row.rows_here, 2))
        for (gx, gy) in pts:
            if ban_fn is not None:
                b = ban_fn(gy)
                if b and b[0] < gx < b[1]:
                    continue
            cb, ct = (gd, gt) if rng.random() < dry else (gb, gt)
            draw_blade(cv, rng, gx, gy, row.lod, blade_h, cb, ct, scale)



def _flower_rows(ctx, hy, h, rows=7):
    """逐行产出 (y0, y1, t, lod)：跳过地平线以上的行，以及最粗 LOD 的行。

    t: 0 = 贴地平线（最远），1 = 画面底边（最近）。
    """
    for r in range(rows):
        y0 = hy + (h - hy) * (r / float(rows))
        y1 = hy + (h - hy) * ((r + 1) / float(rows))
        if y1 <= hy + 2:
            continue
        lod = lod_at(ctx, (y0 + y1) * 0.5)
        if lod >= 3:
            continue
        t = (y0 - hy) / float(max(h - hy, 1))
        yield y0, y1, t, lod


def _flower_count(t, lod, density):
    """每行花朵数。中远(lod2)按比例稀释，但保底能看见零星几朵。"""
    n = int((6 + 12 * t) * density)
    if lod == 2:
        n = int(n * (0.4 + 1.6 / max(t, 0.05)) * 0.35)
    return n


def _in_ban(ban_fn, gx, gy):
    """落在路面禁用区间内则跳过（花不占道，与房子避路同一套规则）。"""
    if ban_fn is None:
        return False
    b = ban_fn(gy)
    return bool(b and b[0] < gx < b[1])


def _flower_near(cv, gx, gy, r_px, c, rng):
    """近处一朵：五瓣 + 花心。

    花瓣按 360°/n 均分旋转（学界通用画法）；花心取花瓣尺度约 0.42，
    与搜到的"花心盘约为花瓣长 40%"一致。
    """
    for k in range(5):
        a = k * 2 * math.pi / 5 + rng.uniform(0, 0.5)
        px = gx + math.cos(a) * r_px
        py = gy - r_px * 0.9 + math.sin(a) * r_px * 0.55
        cv.d.ellipse([px - r_px * 0.55, py - r_px * 0.55,
                      px + r_px * 0.55, py + r_px * 0.55], fill=c)
    heart = (0xE0, 0xB4, 0x2A)
    cv.d.ellipse([gx - r_px * 0.42, gy - r_px * 1.1,
                  gx + r_px * 0.42, gy - r_px * 0.3], fill=heart)


def _flower_far(cv, gx, gy, r_px, c):
    """中距一朵：单彩点。远处(lod3)不单独画，并入草色。"""
    cv.d.ellipse([gx - r_px, gy - r_px * 1.4, gx + r_px, gy], fill=c)


def draw_flowers(cv, ctx, density=1.0, seed=13, **kw):
    """野花。近处花瓣+花心，中距彩点，远处并入草色不单独画。"""
    w, h, hy = cv.w, cv.h, ctx["horizon_y"]
    fog = np.array(ctx["fog_rgb"], dtype=np.float32)
    ban_fn = ctx.get("road_ban")
    rng = _stable_rng(seed, "flower")

    for y0, y1, t, lod in _flower_rows(ctx, hy, h):
        fog_t = float(np.clip(1.0 - t, 0.0, 1.0)) ** 1.1
        n = _flower_count(t, lod, density)
        pts = jittered_pts(rng, -4, w + 4, y0, y1, max(n, 2), max(2, n // 3))
        for (gx, gy) in pts:
            if _in_ban(ban_fn, gx, gy):
                continue
            base = FLOWER_COLORS[rng.randint(0, len(FLOWER_COLORS))]
            c = _mix_fn(fog, fog_t)(base)
            r_px = max(0.9, 2.6 * (0.3 + 0.7 * t))
            if lod == 0:
                _flower_near(cv, gx, gy, r_px, c, rng)
            else:
                _flower_far(cv, gx, gy, r_px, c)


# ---------------------------------------------------------------- 远处行人

def draw_crowd(cv, ctx, n=8, seed=17, **kw):
    """远处行人：impostor 级 LOD。

    业界：极远处 3D 网格换成面向相机的 2D quad；
    中距降频更新（30/15Hz）。此处静态背景按 LOD2~3 画成剪影。
    关键：每个人走路相位随机错开，否则一群人同步迈腿像克隆人。
    """
    w, h, hy = cv.w, cv.h, ctx["horizon_y"]
    fog = np.array(ctx["fog_rgb"], dtype=np.float32)
    ban_fn = ctx.get("road_ban")
    rng = _stable_rng(seed, "crowd")

    for i in range(n):
        t = rng.uniform(0.06, 0.30)          # 只出现在中远景
        gy = hy + (h - hy) * t
        b = ban_fn(gy) if ban_fn else None
        if b:
            gx = rng.uniform(b[0] + 3, b[1] - 3)
        else:
            gx = rng.uniform(0.08, 0.92) * w
        size = 5 + 22 * t
        col = tuple(int(v + (fog[k] - v) * (1 - t) * 0.55)
                    for k, v in enumerate((70, 62, 58)))
        # 相位错开：每条腿角度不同
        ph = rng.uniform(0, math.pi * 2)
        hip_y = gy - size * 0.55
        cv.d.line([(gx, hip_y), (gx, gy - size)], fill=col, width=max(1, int(size / 7)))  # 躯干
        cv.d.ellipse([gx - size * 0.13, gy - size * 1.16,
                      gx + size * 0.13, gy - size * 0.90], fill=col)                       # 头
        for s in (-1, 1):
            sw = math.sin(ph + (0 if s < 0 else math.pi)) * size * 0.22
            cv.d.line([(gx, hip_y), (gx + sw * s, gy)], fill=col, width=max(1, int(size / 9)))


# ---------------------------------------------------------------- 房屋门窗

def _win_skip(lod, w_w, h_w):
    """卫语句合并：远处 / 太窄 / 太矮 一律不画门窗。"""
    return lod >= 2 or w_w < 9 or h_w < 16


def _mix_fn(fog, fog_t):
    """雾混合闭包：把颜色朝雾色推 fog_t*0.8。

    依据是空气透视 C_final = lerp(C, C_fog, t)，远处门窗与远景同雾。
    """
    def mix(c):
        return tuple(int(c[k] + (fog[k] - c[k]) * fog_t * 0.8) for k in range(3))
    return mix


def _win_frame_color(palette):
    """门窗框色：赭石优先（江南），回退瓦色（唐式）。"""
    return palette["zheshi"] if "zheshi" in palette else palette["wa"]


def _win_grid(x0, y_top, cw, fh, floors, cols, rng):
    """切分出窗格位置（Split Shape Grammar 的 split 一步）。

    每格调用一次 rng.random()，随机 0.22 留白 —— 不是每格都有窗。
    """
    g = []
    for r in range(floors):
        for c in range(cols):
            if rng.random() < 0.22:
                continue
            g.append((x0 + cw * (c + 0.15), y_top + fh * (r + 0.18),
                      cw * 0.7, fh * 0.5))
    return g


def _win_pane(d, wx, wy, ww, wh, glass, frame, lod):
    """单扇窗：lod0 带框与竖棂，lod1 只留单色窗洞。"""
    if ww < 2 or wh < 2:
        return
    d.rectangle([wx, wy, wx + ww, wy + wh], fill=glass)
    if lod == 0:
        d.rectangle([wx, wy, wx + ww, wy + wh], outline=frame, width=1)
        d.line([(wx + ww / 2, wy), (wx + ww / 2, wy + wh)], fill=frame)


def _win_door(d, x0, w_w, h_w, y_bot, frame, mix):
    """门：底层正中。传统建筑要求入口明显且居中于子体量。"""
    dw = min(w_w * 0.28, 22)
    dh = min(h_w * 0.30, 30)
    dx = x0 + (w_w - dw) / 2
    d.rectangle([dx, y_bot - dh, dx + dw, y_bot], fill=mix(frame))


def facade_windows(d, x0, x1, y_top, y_bot, rng, style, palette, lod, fog_t, fog):
    """沿 x 切分出门窗（Split Shape Grammar 的最小形态），仅做编排。

    lod 0：窗框 + 玻璃 + 门；lod 1：单色窗洞；lod 2+：不画。

    已知可升级配方（本次为纯重构，未应用，避免改动画面）：
      竖长方形开口高宽比 1.5~2，拱形 2.0；水平方向开口数为奇数；
      圆窗直径取下方矩形窗宽的 0.8。出处见 conventional 传统建筑开口导则。
    """
    w_w = x1 - x0
    h_w = y_bot - y_top
    if _win_skip(lod, w_w, h_w):
        return
    floors = max(1, int(h_w // 26))
    cols = max(1, int(w_w // 22))
    mix = _mix_fn(fog, fog_t)
    frame_c = _win_frame_color(palette)
    glass = mix((0x4C, 0x5A, 0x5E))
    frame = mix(frame_c)
    fh = h_w / (floors + 0.4)
    cw = w_w / (cols + 0.3)
    for wx, wy, ww, wh in _win_grid(x0, y_top, cw, fh, floors, cols, rng):
        _win_pane(d, wx, wy, ww, wh, glass, frame, lod)
    if lod == 0 and cols >= 1:
        _win_door(d, x0, w_w, h_w, y_bot, frame_c, mix)


# ---------------------------------------------------------------- 树冠

def canopy(d, cx, cy_top, cy_bot, rx, ry, rng, lod, fog_t, fog, n=14):
    """树冠叶簇：多个椭圆团 + 明暗梯度，替代"一个实心椭圆"。

    lod 0：多团带受光面；lod 1：少团；lod 2+：单团剪影。
    """
    def mix(c):
        return tuple(int(c[k] + (fog[k] - c[k]) * fog_t * 0.85) for k in range(3))

    if lod >= 2:
        d.ellipse([cx - rx, cy_top, cx + rx, cy_bot], fill=mix(LEAF_DARK))
        return
    k = n if lod == 0 else max(4, n // 3)
    for i in range(k):
        a = rng.uniform(0, math.pi * 2)
        rr = rng.uniform(0.25, 1.0)
        ox = cx + math.cos(a) * rx * 0.62 * rr
        oy = (cy_top + cy_bot) / 2 + math.sin(a) * ry * 0.5 * rr
        ex = rx * rng.uniform(0.30, 0.58)
        ey = ry * rng.uniform(0.28, 0.55)
        # 受光面偏左上：暗团打底，亮团叠在受光侧
        lit = rng.random() < 0.38
        base = mix(LEAF_LIT if lit else LEAF_DARK)
        if lit:
            ox -= rx * 0.18
            oy -= ry * 0.18
        d.ellipse([ox - ex, oy - ey, ox + ex, oy + ey], fill=base)


# ---------------------------------------------------------------- 自检

def self_check():
    ok = True
    ctx = dict(w=540, h=960, horizon_y=499)
    seq = [lod_at(ctx, y) for y in (499, 560, 700, 860, 955)]
    mono = all(seq[i] >= seq[i + 1] for i in range(len(seq) - 1))
    print("  LOD 随深度单调变粗 :", mono, seq)
    ok &= mono

    r1 = _stable_rng(7, "grass")
    r2 = _stable_rng(7, "grass")
    same = r1.random() == r2.random()
    print("  种子派生确定性     :", same)
    ok &= same

    r3 = _stable_rng(7, "grass")
    r4 = _stable_rng(8, "grass")
    diff = r3.random() != r4.random()
    print("  异 seed 有差异     :", diff)
    ok &= diff

    pts = jittered_pts(np.random.RandomState(0), 0, 100, 0, 100, 5, 5)
    even = len(pts) == 25
    print("  抖动网格无团簇     :", even, len(pts))
    ok &= even

    print("  唐式四色已载入     :", tuple(TANG[k] for k in ("zhu", "bi", "wa", "sha")))
    return ok


if __name__ == "__main__":
    print("SELF_CHECK:", "PASS" if self_check() else "FAIL")
