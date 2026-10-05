# -*- coding: utf-8 -*-
"""showreel/render.py —— 90 秒一镜到底·雨夜赛博朋克街道·渲染层。

渲染架构（业界通行做法，本轮搜索取证后落地）：
  背景层 → 远层雨 → 场景物体(深度排序) → 角色(离屏 alpha 合成)
  → 近层雨 → 后处理(辉光/暗角)

刻意**不另写渲染器**：角色仍走 motion.run.draw_actor + R.CV 画布，
只在其上按 painter's algorithm 叠加图层。之前"另起炉灶写渲染"
导致画布塌成 1×1，故此处强制复用既有管线。

分层排序依据（搜索取证：SkeletonRenderSeparator 思路）：
  场景物体可插入角色的 back / front 之间。
  本片物理为 2D 侧视，故按 Z 深度排序，远的先画。

雨效（搜索取证）：噪声掩码 → 仿射变换 → 运动模糊 → alpha 混合。
霓虹辉光（搜索取证）：提取亮部 → 高斯模糊 → gain 叠加。
"""
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

W, HH = 1920, 1080
FPS = 24.0

# 场景物体统一深度（2D 侧视平面）；角色更靠近相机
Z_PROP = 6.0
Z_ACTOR = 5.0

# 霓虹主色：品红 / 青 / 紫 / 橙
NEON = [(255, 40, 150), (0, 230, 255), (150, 60, 255), (255, 170, 40)]

# 物体配色（按 tag）
TAG_COL = {
    "table": (92, 66, 48), "crate": (120, 130, 142),
    "domino": (232, 228, 220), "stack": (150, 120, 96),
    "wall": (104, 74, 66), "ramp": (58, 62, 74),
    "pend": (170, 176, 188), "ball": (220, 210, 60),
    "cup": (238, 236, 230), "door": (76, 54, 40),
    "rung": (140, 146, 158), "target": (220, 60, 60),
    "rope": (150, 116, 74),
}


# ---------------------------------------------------------------- 背景
def build_bg(seed=7):
    """雨夜街道底板：天空渐变、建筑剪影、霓虹招牌、湿沥青与倒影。

    只建一次；逐帧只做倒影与霓虹脉动（其余图层叠在上面）。
    """
    rng = np.random.default_rng(seed)
    img = Image.new("RGB", (W, HH))
    dr = ImageDraw.Draw(img)
    vh = int(0.60 * HH)

    # ---- 天空：上深下亮，底部被霓虹染紫 ----
    for y in range(vh):
        a = y / float(vh)
        r = int(12 + 52 * a)
        g = int(9 + 14 * a)
        b = int(34 + 86 * a)
        dr.line([(0, y), (W, y)], fill=(r, g, b))

    # ---- 远景建筑剪影 + 窗灯 ----
    x = 0
    while x < W:
        bw = int(rng.integers(90, 230))
        bh = int(rng.integers(int(0.16 * HH), int(0.40 * HH)))
        top = vh - bh
        dr.rectangle([x, top, x + bw, vh], fill=(16, 14, 30))
        # 窗灯：青/橙小格
        for wy in range(top + 14, vh - 12, 26):
            for wx in range(x + 10, x + bw - 12, 22):
                if rng.random() < 0.34:
                    c = (0, 220, 255) if rng.random() < 0.5 else (255, 180, 90)
                    dr.rectangle([wx, wy, wx + 9, wy + 12], fill=c)
        x += bw + int(rng.integers(6, 26))

    # ---- 霓虹招牌（竖向灯条 + 横向灯箱）----
    signs = []
    for _ in range(9):
        sx = int(rng.integers(40, W - 140))
        sy = int(rng.integers(int(0.12 * HH), int(0.52 * HH)))
        sw = int(rng.integers(16, 34))
        sh = int(rng.integers(70, 220))
        c = NEON[int(rng.integers(0, len(NEON)))]
        dr.rectangle([sx, sy, sx + sw, sy + sh], fill=c)
        signs.append((sx, sy, sw, sh, c))
    for _ in range(6):
        sx = int(rng.integers(60, W - 260))
        sy = int(rng.integers(int(0.16 * HH), int(0.54 * HH)))
        sw = int(rng.integers(110, 240))
        sh = int(rng.integers(18, 40))
        c = NEON[int(rng.integers(0, len(NEON)))]
        dr.rectangle([sx, sy, sx + sw, sy + sh], fill=c)
        signs.append((sx, sy, sw, sh, c))

    # ---- 湿沥青地面 ----
    for y in range(vh, HH):
        d = (y - vh) / float(HH - vh)
        dr.line([(0, y), (W, y)],
                fill=(int(28 - 14 * d), int(30 - 15 * d), int(44 - 18 * d)))
    # 地面湿痕（横向反光带）
    for _ in range(40):
        yy = int(rng.integers(vh, HH))
        ww = int(rng.integers(120, 700))
        xx = int(rng.integers(0, W - ww))
        dr.line([(xx, yy), (xx + ww, yy)], fill=(46, 52, 74), width=1)

    # ---- 霓虹在湿地面的倒影：垂直翻转 + 压暗 + 模糊 ----
    refl = Image.new("RGB", (W, HH - vh), (0, 0, 0))
    rd = ImageDraw.Draw(refl)
    for (sx, sy, sw, sh, c) in signs:
        # 以地平线为轴翻转
        ry = (vh - sy) - sh
        if -sh < ry < HH - vh:
            rd.rectangle([sx, ry, sx + sw, ry + sh], fill=c)
    refl = refl.filter(ImageFilter.GaussianBlur(9))
    ra = np.asarray(refl).astype(np.float32) * 0.34
    base = np.asarray(img).astype(np.float32)
    base[vh:, :, :] = np.clip(base[vh:, :, :] + ra, 0, 255)
    img = Image.fromarray(base.astype(np.uint8))
    return img


# ---------------------------------------------------------------- 雨
def _rain(dr, t, n, seed, speed, length, color, alpha, slant):
    """一层雨。slant=水平倾斜(px/帧累积)。固定种子 → 不闪烁。"""
    rng = np.random.default_rng(seed)
    xs = rng.uniform(-240, W + 240, n)
    ys = rng.uniform(0, HH, n)
    ln = rng.uniform(length * 0.6, length * 1.4, n)
    y = (ys + speed * t) % (HH + 400) - 200
    x = xs + slant * t
    for i in range(n):
        x0 = float(x[i])
        y0 = float(y[i])
        dr.line([(x0, y0), (x0 + slant * 0.9, y0 + float(ln[i]))],
                fill=color, width=1)


def add_rain(img, t, wind=0.0):
    """三层雨：远(细暗慢) / 中 / 近(粗亮快)。雨丝随风向倾斜。"""
    slant = -1.4 * wind
    lay = Image.new("RGBA", (W, HH), (0, 0, 0, 0))
    dr = ImageDraw.Draw(lay)
    _rain(dr, t, 260, 11, 900, 26, (150, 170, 210), 0.30, slant * 0.6)
    _rain(dr, t, 200, 22, 1500, 40, (185, 200, 235), 0.45, slant)
    _rain(dr, t, 130, 33, 2350, 62, (225, 235, 255), 0.62, slant * 1.5)
    img.paste(Image.alpha_composite(img.convert("RGBA"), lay).convert("RGB"),
              (0, 0))
    return img


# ---------------------------------------------------------------- 物体
def draw_props(dr, cam, props, Z=Z_PROP):
    """按深度排序画场景物体。props: 每项 (x, y, th, hw, hh, kind, col)。

    painter's algorithm：Z 大的（远）先画。
    """
    for (x, y, th, hw, hh, kind, col) in props:
        if kind == "ball":
            sx, sy, s = cam.proj(x, Z, y)
            r = max(hw * s, 1.0)
            dr.ellipse([sx - r, sy - r, sx + r, sy + r], fill=col,
                       outline=(24, 24, 30))
        else:
            cs, sn = math.cos(th), math.sin(th)
            pts = []
            for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh)):
                wx = x + dx * cs - dy * sn
                wy = y + dx * sn + dy * cs
                sx, sy, _s = cam.proj(wx, Z, wy)
                pts.append((sx, sy))
            dr.polygon(pts, fill=col, outline=(22, 22, 28))


def props_from_world(bodies, snap=None, i=0):
    """由物理 world.bodies（或回放快照）→ props 列表。"""
    out = []
    for k, b in enumerate(bodies):
        if snap is not None and k < len(snap):
            x, y, th = float(snap[k, 0]), float(snap[k, 1]), float(snap[k, 2])
        else:
            x, y = float(b.p[0]), float(b.p[1])
            th = float(getattr(b, "th", 0.0))
        if getattr(b, "shape", "box") == "ball":
            out.append((x, y, th, float(getattr(b, "r", 0.11)), 0.0,
                        "ball", TAG_COL.get(getattr(b, "tag", ""), (220, 210, 60))))
        else:
            out.append((x, y, th, float(getattr(b, "hw", 0.1)),
                        float(getattr(b, "hh", 0.1)), "box",
                        TAG_COL.get(getattr(b, "tag", ""), (130, 130, 140))))
    return out


# ---------------------------------------------------------------- 后处理
def post(img, t):
    """霓虹辉光（亮部提取→模糊→叠加）+ 暗角。"""
    a = np.asarray(img).astype(np.float32)
    lum = a.mean(2)
    bright = np.clip(lum - 150.0, 0.0, None)
    bl = Image.fromarray(bright.astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(14))
    a += (np.asarray(bl).astype(np.float32)[:, :, None] * 0.30)
    gy = np.arange(HH, dtype=np.float32)[:, None]
    gx = np.arange(W, dtype=np.float32)[None, :]
    vig = 1.0 - 0.34 * (((gx - W / 2) / (W / 2)) ** 2 +
                        ((gy - HH / 2) / (HH / 2)) ** 2)
    a *= np.clip(vig, 0.55, 1.0)[:, :, None]
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# ---------------------------------------------------------------- 合成
def compose(t, cam, bg, props=None, actors=None, wind=0.0, rain=True):
    """合成一帧。actors: [(Xc, Zc, yaw, J, palette, body_h)]。"""
    img = bg.copy()
    dr = ImageDraw.Draw(img)
    if rain:
        add_rain(img, t, wind)          # 远层雨（物体之后）
        dr = ImageDraw.Draw(img)
    if props:
        draw_props(dr, cam, props)
    if actors:
        from motion import run as R
        arr = np.asarray(img).astype(np.float32)
        cv = R.CV(W, HH)
        cv.set_arr(arr)
        for (Xc, Zc, yaw, J, pal, bh) in actors:
            R.draw_actor(cv, cam, J, Xc=Xc, Zc=Zc, yaw=yaw, body_h=bh,
                         template="humanoid", hand_lod=1, palette=pal)
        img = cv.img.copy()
    if rain:
        img = add_rain(img, t, wind)    # 近层雨（角色之前）
    return post(img, t)
