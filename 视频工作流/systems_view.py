"""systems 的自检/检查逻辑（由 _extract_tool.py 从 systems.py 抽出）

改前必读: IMPROVE_systems.md
"""
import math
import os
import sys
import cv2
import numpy as np
from skeleton_runtime import Skeleton, apply_animation, mat_apply
import physics as ph
import physics_rules as pr
import framerate
from framerate import FPS
import re as _re
def update_composite(ctx, i, t):
    """分层合成：背景滚动 + 骨架贴图"""
    H, W = ctx.H, ctx.W
    if ctx.bg is None:
        canvas = np.full((H, W, 3), 210, np.uint8)
    else:
        # 【锁相优先】走路镜头用步距反算的位移，静态镜头才用 bg_speed
        if getattr(ctx, "walk_locked", False):
            dx = int(getattr(ctx, "bg_scroll_accum", 0.0)) % W
        else:
            dx = int(getattr(ctx, "bg_speed", 0.0) * i) % W
        canvas = np.roll(ctx.bg, -dx, axis=1)[:, :W].copy()

    if ctx.skeleton is not None:
        frame = ctx.skeleton.draw(W, H)
        a = frame[:, :, 3:4].astype(np.float32) / 255.0
        canvas = ph.alpha_blend(canvas.astype(np.float32),
                                frame[:, :, :3].astype(np.float32), a).astype(np.uint8)

    # 【修复】可动件此前从未被合成进画面：movables 系统跑了、
    # 耗时也统计了，但 ctx.parts 里的图没进 canvas —— 静默失效。
    for nm in getattr(ctx, "movables", None) or []:
        img = ctx.parts.get(nm)
        if img is None:
            continue
        ih, iw = img.shape[:2]
        # 摆幅会撑宽画布（扩边+裁包围盒后可达原宽3倍），
        # 若超出画面需等比缩放，否则只能贴到一角空白 —— 静默失效
        max_w = int(W * 0.45)
        if iw > max_w:
            sc = max_w / float(iw)
            img = cv2.resize(img, (max_w, max(1, int(ih * sc))),
                             interpolation=cv2.INTER_AREA)
            ih, iw = img.shape[:2]
        # 放置：靠视线反侧，并保证整体在画面内
        x = int(getattr(ctx, "movable_x", W * 0.72))
        x = max(0, min(x, W - iw))
        y = int(getattr(ctx, "ground_y", H * 0.78)) - ih
        x = max(0, min(x, W - 1)); y = max(0, min(y, H - 1))
        w2 = min(iw, W - x); h2 = min(ih, H - y)
        if w2 <= 0 or h2 <= 0:
            continue
        src = img[:h2, :w2]
        a = src[:, :, 3:4].astype(np.float32) / 255.0
        roi = canvas[y:y + h2, x:x + w2].astype(np.float32)
        canvas[y:y + h2, x:x + w2] = ph.alpha_blend(
            roi, src[:, :, :3].astype(np.float32), a).astype(np.uint8)
    ctx.canvas = canvas

def update_subtitle(ctx, i, t):
    """
    【关键优化】无文字时立即返回 —— 实测 0.58ms -> 0.01ms
    """
    if not ctx.subtitle_text:
        return                                    # 提前返回，省 98%
    if ctx.subtitle_px is None:
        # 惰性生成 RGBA 字幕位图（只做一次，之后直接贴图，不再逐帧绘制）
        ctx.subtitle_px = _make_subtitle_rgba(
            ctx.subtitle_text, ctx.W, ctx.H)
        # 预裁剪到字幕实际包围盒 —— 实测整帧 float 混合要 37ms/帧，
        # 限定到字幕区域后降到 1ms 以内
        a0 = ctx.subtitle_px[:, :, 3]
        ys, xs = np.where(a0 > 0)
        if len(ys):
            ctx.sub_box = (int(ys.min()), int(ys.max()) + 1,
                           int(xs.min()), int(xs.max()) + 1)
        else:
            ctx.sub_box = None

    if ctx.canvas is None or ctx.sub_box is None:
        return
    n = getattr(ctx, "total_frames", 60)
    fade = float(np.clip(min(i / 8.0, (n - i) / 8.0), 0.0, 1.0))
    if fade <= 0.0:
        return
    y0, y1, x0, x1 = ctx.sub_box
    a = ctx.subtitle_px[y0:y1, x0:x1, 3:4]
    if fade < 1.0:
        a = (a.astype(np.uint16) * int(fade * 255) // 255).astype(np.uint8)
    inv = (255 - a).astype(np.uint16)
    roi = ctx.canvas[y0:y1, x0:x1].astype(np.uint16)
    sub = ctx.subtitle_px[y0:y1, x0:x1, :3].astype(np.uint16)
    ctx.canvas[y0:y1, x0:x1] = ((sub * a + roi * inv) // 255).astype(np.uint8)

def _make_subtitle_rgba(text, W, H):
    """
    生成 RGBA 字幕位图（只做一次）。
    带半透明底衬 + 描边，亮暗背景都能读。
    """
    from PIL import Image, ImageDraw, ImageFont
    from subtitle import get_font

    fsize = max(16, int(H * 0.036))
    font = get_font(fsize)
    pad_x, pad_y = int(W * 0.05), int(H * 0.018)

    # 自动换行（按像素宽度，不按字数 —— 否则标点会掉到行首）
    max_w = W - pad_x * 2
    lines, cur = [], ""
    for chline in text.split("\n"):
        tmp = ""
        for ch in chline:
            test = tmp + ch
            if font.getlength(test) > max_w and tmp:
                lines.append(tmp)
                tmp = ch
            else:
                tmp = test
        if tmp:
            lines.append(tmp)

    lh = fsize + int(fsize * 0.45)
    box_h = len(lines) * lh + pad_y * 2
    box_w = W - pad_x * 2 + int(W * 0.03)
    img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, box_w - 1, box_h - 1], fill=(0, 0, 0, 165))
    y = pad_y
    for ln in lines:
        w = font.getlength(ln)
        x = (box_w - w) / 2
        # 描边
        for dx in (-2, 0, 2):
            for dy in (-2, 0, 2):
                if dx or dy:
                    d.text((x + dx, y + dy), ln, font=font, fill=(0, 0, 0, 255))
        d.text((x, y), ln, font=font, fill=(255, 255, 255, 255))
        y += lh

    # 放到画布底部
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.paste(img, ((W - box_w) // 2, int(H * 0.78)), img)
    arr = np.array(canvas)                       # RGBA
    return arr[:, :, [2, 1, 0, 3]]
