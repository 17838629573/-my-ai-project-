#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
角色层素材处理：色度键抠像 + 去溢色 + 边缘处理
==================================================
【为什么不用抠像模型】
  HuggingFace / GitHub 权重全 403，拿不到 U2Net / MODNet / RMBG。
  改用色度键：生成时指定纯色背景，代码按【已知色】做键控。
  零权重依赖、纯确定性、可审计。

【实测背景色】
  指定 #FF00FF，模型实际产出 BGR(154,42,203) —— 紫色，不是纯品红。
  判定条件必须按实测值写，不能按理论值写：
    R>150 且 B>150 且 G<100   → 命中 65.0%
  前景平均 RGB(125,104,65) = 赭黄僧袍，与背景色分离度足够。

【三个必须处理的坑】
  1. 边缘溢色：紫色背景会在人物轮廓染上紫边 -> despill
  2. 硬边锯齿：alpha 硬切会在合成时出现白边 -> 羽化 + 收缩
  3. 半透明发丝/布料：硬阈值会吃掉 -> 用软 alpha（距离加权）
"""
import os

import cv2
import numpy as np


def chroma_key(bgr, ref=None, softness=0.25, shrink=2, despill=0.75):
    """
    色度键 -> (BGRA 图像, alpha 浮点图)

    softness: alpha 过渡带宽度（相对色差尺度）
    despill:  去溢色强度 0-1
    """
    h, w = bgr.shape[:2]
    if ref is None:
        # 自动取四角均值作参考色（实测背景均匀）
        pts = [bgr[8, 8], bgr[8, w - 8], bgr[h - 8, 8], bgr[h - 8, w - 8]]
        ref = np.median(np.array(pts, dtype=np.float64), axis=0)
    ref = np.asarray(ref, dtype=np.float64)

    f = bgr.astype(np.float64)

    # ---- 软 alpha：与参考色的归一化距离 ----
    dist = np.linalg.norm(f - ref, axis=2)                # 0 = 完全同背景色
    scale = max(30.0, np.percentile(dist, 90) * softness)
    alpha = np.clip(dist / scale, 0.0, 1.0)

    # 极端背景（角落）强制 0，避免噪点
    hard = (dist < scale * 0.35)
    alpha[hard] = 0.0

    # ---- 去溢色 ----
    # 紫色背景会让轮廓像素的 R/B 抬高、G 压低。
    # 修法：把 G 抬到不低于 min(R,B) 的一定比例。
    if despill > 0:
        r, g, bl = f[:, :, 2], f[:, :, 1], f[:, :, 0]
        mn = np.minimum(r, bl)
        # 只修"疑似被染色"的像素：R、B 都高而 G 明显低
        spill = (mn > 90) & (g < mn * 0.85)
        target = mn * 0.92
        g_new = g + (target - g) * despill
        f[:, :, 1] = np.where(spill, np.maximum(g, g_new), g)

    # ---- alpha 收缩：削掉一圈边缘，避免背景残边 ----
    if shrink > 1.0:
        k = int(shrink)
        ker = np.ones((max(1, k * 2 - 1), max(1, k * 2 - 1)), np.uint8)
        a8 = (alpha * 255).astype(np.uint8)
        a8 = cv2.erode(a8, ker, iterations=1)
        alpha = a8.astype(np.float64) / 255.0

    # ---- 边缘羽化 ----
    alpha = cv2.GaussianBlur(alpha, (0, 0), 1.2)
    alpha = np.clip(alpha, 0.0, 1.0)

    out = np.dstack([f, alpha * 255.0]).astype(np.uint8)
    return out, alpha


def trim_alpha(bgra, pad=2):
    """
    裁掉全透明外框 + 外扩 pad 像素。
    外扩是必须的：不做的的话缩放采样时相邻内容会渗色，
    画面上表现为细线闪烁。
    返回 (裁剪后的 BGRA, 在原图中的 bbox)
    """
    a = bgra[:, :, 3]
    ys, xs = np.where(a > 12)
    if len(xs) == 0:
        return bgra, (0, 0, bgra.shape[1], bgra.shape[0])
    x0, x1 = max(0, xs.min() - pad), min(bgra.shape[1], xs.max() + 1 + pad)
    y0, y1 = max(0, ys.min() - pad), min(bgra.shape[0], ys.max() + 1 + pad)
    return bgra[y0:y1, x0:x1], (x0, y0, x1 - x0, y1 - y0)


def clean_mask(bgra, thresh=128, feather=0.5):
    """
    【实测 bug】高斯羽化后角落 alpha 仍有 70/38/58/16，导致
    trim_alpha 的 bbox 覆盖整张图（1152x2048），裁不掉。

    根因：背景非纯色（有渐变/暗角），角点与参考色的距离
    超过硬阈值 scale*0.35，于是留下残片。

    修法：二值化 -> 取最大连通域 -> 重新羽化。
    最大连通域这一步是必须的，否则零碎残片会让包围盒失控。
    """
    a = bgra[:, :, 3]
    _, bw = cv2.threshold(a, thresh, 255, cv2.THRESH_BINARY)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(bw, 8)
    if n > 1:
        # 0 是背景，从 1 起找面积最大
        idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        bw = (lab == idx).astype(np.uint8) * 255
    a2 = cv2.GaussianBlur(bw.astype(np.float64), (0, 0), feather)
    a2 = np.clip(a2 / 255.0, 0.0, 1.0)
    out = bgra.copy()
    out[:, :, 3] = (a2 * 255).astype(np.uint8)
    return out


def all_components(mask, thresh=128, min_area=10):
    """
    全量连通域（8 向），按面积降序。铁律44：图集切分要"网格定序 +
    连通域定界"，故需【全部】组件，不能只取最大（clean_mask 只取最大）。

    mask: 2D uint8（非 0 为前景）或 BGRA 图（自动取 alpha 通道）
    返回 [{"area":int, "bbox":(x0,y0,x1,y1), "touches_edge":bool}, ...]
    bbox 为半开区间 (min_x, min_y, max_x+1, max_y+1) —— 与 OpenCV stats 一致

    touches_edge 是溢出判据（besthub 原文：姿态溢出格子，硬切会切掉脚）。
    """
    if mask.ndim == 3:
        mask = mask[:, :, 3]
    _, bw = cv2.threshold(mask.astype(np.uint8), thresh, 255, cv2.THRESH_BINARY)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(bw, 8)
    h, w = bw.shape[:2]
    out = []
    for i in range(1, n):                      # 0 是背景
        a = int(stats[i, cv2.CC_STAT_AREA])
        if a < min_area:
            continue                           # 噪点（codestudy: min_area=10）
        x0 = int(stats[i, cv2.CC_STAT_LEFT])
        y0 = int(stats[i, cv2.CC_STAT_TOP])
        x1 = x0 + int(stats[i, cv2.CC_STAT_WIDTH])
        y1 = y0 + int(stats[i, cv2.CC_STAT_HEIGHT])
        out.append({"area": a, "bbox": (x0, y0, x1, y1),
                    "touches_edge": bool(x0 <= 0 or y0 <= 0 or x1 >= w or y1 >= h)})
    out.sort(key=lambda d: -d["area"])
    return out


def load_character(path, target_h=None, method="flood", **kw):
    """读角色图 -> 抠像 -> 清掩膜 -> 裁剪 -> 可选缩放。返回 BGRA
    method: flood(默认,实测对全部5素材有效) | chroma(仅纯色背景)
    实测: xz_cu/hands/mcu 为双色背景(上紫蓝+下浅灰), chroma_key 返回全图bbox"""
    bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    if method == "flood":
        bgra, _ = flood_key(bgr, **kw)
    else:
        bgra, _ = chroma_key(bgr, **kw)
        bgra = clean_mask(bgra)      # 必须先清掩膜，否则 bbox 覆盖全图
    bgra, bbox = trim_alpha(bgra)
    if target_h:
        h, w = bgra.shape[:2]
        nw = max(1, int(w * target_h / h))
        bgra = cv2.resize(bgra, (nw, target_h), interpolation=cv2.INTER_AREA)
    return bgra


def overlay(dst, bgra, x, y, scale=1.0):
    """
    把 BGRA 角色贴到 BGR 画布上（uint16 整数混合，实测比全画布 float 快 4.7x）。
    只在包围盒内运算。
    """
    if scale != 1.0:
        h, w = bgra.shape[:2]
        bgra = cv2.resize(bgra, (max(1, int(w * scale)), max(1, int(h * scale))),
                          interpolation=cv2.INTER_AREA)
    h, w = bgra.shape[:2]
    H, W = dst.shape[:2]

    x0, y0 = int(x), int(y)
    x1, y1 = x0 + w, y0 + h
    # 裁剪到画布内
    cx0, cy0 = max(0, x0), max(0, y0)
    cx1, cy1 = min(W, x1), min(H, y1)
    if cx1 <= cx0 or cy1 <= cy0:
        return dst
    sx0, sy0 = cx0 - x0, cy0 - y0
    sx1, sy1 = sx0 + (cx1 - cx0), sy0 + (cy1 - cy0)

    src = bgra[sy0:sy1, sx0:sx1]
    a = src[:, :, 3:4].astype(np.uint16)
    inv = (255 - a).astype(np.uint16)
    roi = dst[cy0:cy1, cx0:cx1].astype(np.uint16)
    fg = src[:, :, :3].astype(np.uint16)
    dst[cy0:cy1, cx0:cx1] = ((fg * a + roi * inv) // 255).astype(np.uint8)
    return dst


def contact_shadow(w, h, cx=None, strength=0.45):
    """接触阴影：人物脚下没有阴影会'浮空'。返回浮点 alpha 图"""
    cx = cx if cx is not None else w / 2.0
    yy, xx = np.mgrid[0:h, 0:w]
    rx = w * 0.42
    ry = max(2.0, h * 0.10)
    d = (((xx - cx) / rx) ** 2 + ((yy - h * 0.5) / ry) ** 2)
    m = np.clip(1.0 - d, 0.0, 1.0) ** 1.5
    return m * strength

def flood_key(bgr, tol=10, despill=0.7, feather=0.5):
    """
    边缘泛洪抠像（Photoshop 魔棒的思路）。

    【为什么需要】chroma_key 用四角均值作参考色，
    但实测各张生成图的背景色并不一致：
      walk_a  四角 BGR(156,43,201) 紫
      mcu     顶部(89,69,175) 蓝紫，底部(207,225,228) 浅色
      cu      顶部(90,64,156)，底部(214,226,225)
      hands   顶部(78,57,197)，底部(195,221,229)
    四角均值在 mcu/cu/hands 上完全失效 —— 品红占比 0.0%，
    抠像结果 100% 不透明（等于没抠）。

    泛洪不依赖单一参考色：从【边缘种子】出发，
    按颜色容差连通扩散，能同时吃掉紫色顶部和浅色底部。
    """
    h, w = bgr.shape[:2]
    img = bgr.copy()

    # 掩码：(h+2, w+2)，floodFill 要求
    mask = np.zeros((h + 2, w + 2), np.uint8)
    lo = (tol, tol, tol, 0)
    hi = (tol, tol, tol, 0)

    # 沿四条边撒种子（每隔 step 像素一个）
    step = 6
    seeds = []
    for x in range(0, w, step):
        seeds.append((x, 0)); seeds.append((x, h - 1))
    for y in range(0, h, step):
        seeds.append((0, y)); seeds.append((w - 1, y))

    filled = 0
    for sx, sy in seeds:
        # 已被填过的跳过，省时间
        if mask[sy + 1, sx + 1] != 0:
            continue
        n, _, _, _ = cv2.floodFill(
            img, mask, (sx, sy), 255,
            loDiff=lo, upDiff=hi,
            flags=4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8))
        filled += n

    bg = mask[1:h + 1, 1:w + 1]                 # 255 = 背景
    fg = (bg == 0).astype(np.uint8) * 255      # 前景候选
    # 只保留最大连通域：泛洪会产生零散"漏网"噪点
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg, 8)
    if n > 1:
        idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        fg = (lab == idx).astype(np.uint8) * 255
    a = fg.astype(np.float64) / 255.0
    a = cv2.GaussianBlur(a, (0, 0), feather)
    a = np.clip(a, 0.0, 1.0)

    # 去溢色：把背景色倾向压掉
    if despill > 0:
        f = img.astype(np.float64)
        r, g, bl = f[:, :, 2], f[:, :, 1], f[:, :, 0]
        mn = np.minimum(r, bl)
        spill = (mn > 90) & (g < mn * 0.85) & (a > 0.05)
        f[:, :, 1] = np.where(spill, np.maximum(g, mn * 0.92), g)
        img = f.astype(np.uint8)

    out = np.dstack([img, (a * 255).astype(np.uint8)])
    return out, a

# --------------------------------------------------------------- 自检
# 铁律26：无自检 = 不通过。契约见 contracts/chroma.md
def self_check(*a, **k):
    from chroma_selfcheck import self_check as _f
    return _f(*a, **k)


if __name__ == "__main__":
    import sys
    _ok, _ = self_check()
    sys.exit(0 if _ok else 1)