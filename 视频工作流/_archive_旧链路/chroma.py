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
import composite as cp


def chroma_key(bgr, ref=None, softness=0.25, shrink=2, despill=0.75, clean_bg=None):
    """
    色度键 -> (BGRA 图像, alpha 浮点图)

    softness: alpha 过渡带宽度（相对色差尺度）
    despill:  去溢色强度 0-1
    clean_bg: 真实背景图（无主体）。给了就走 difference_matte，最优路径。
    """
    h, w = bgr.shape[:2]
    if ref is None:
        # B1+A3：统一走 dispatch。优先级按"手上有什么先验"，不按对象猜。
        #   1) 有真实 clean plate -> difference_matte（最优，业界 VFX 标准）
        #   2) 无 -> flood_key（不依赖单一参考色，能吃掉渐变背景）
        # 四角均值（单参考色）已废弃：实测在 mcu/cu/hands 上品红占比 0.0%，
        # 结果 100% 不透明 = 人物被整块抠成方框。
        a, method = cp.matte_auto(bgr, clean_bg=clean_bg)
        if a is not None:
            f = bgr.astype(np.float64)
            out = np.dstack([f, a * 255.0]).astype(np.uint8)
            return (out, a)
        return flood_key(bgr, tol=10, despill=despill, feather=0.5)
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


def _extrude(bgra, a, n):
    """B6：把边缘像素复制 n 圈到透明 gutter。
    与 padding 是两件事：padding 只是留白，框外仍透明，
    滤波时会与透明混合产生淡色毛边；extrude 是把边缘颜色复制出去。
    """
    if n <= 0:
        return bgra
    m = (a > 12).astype(np.uint8)
    src = bgra.astype(np.float32)
    # 只复制颜色，绝不复制 alpha —— gutter 必须保持透明，
    # 否则 extrude 会把主体"变胖"（实测 alpha 被一起膨胀）。
    rgb = src[:, :, :3]
    alpha0 = src[:, :, 3:4]
    cur = rgb.copy()
    curm = m.astype(np.float32)
    acc = np.zeros_like(rgb)
    accm = np.zeros_like(curm)
    for _ in range(int(n)):
        nxt = cv2.dilate(cur, np.ones((3, 3), np.uint8))
        nxtm = cv2.dilate(curm, np.ones((3, 3), np.uint8))
        ring = np.clip(nxtm - curm, 0.0, 1.0)
        acc += nxt * ring[..., None]
        accm += ring
        cur, curm = nxt, nxtm
    den = np.maximum(accm, 1e-6)[..., None]
    fill = np.where(accm[..., None] > 1e-6, acc / den, 0.0)
    keep = (m == 0)[..., None]
    out_rgb = np.where(np.repeat(keep, 3, axis=2), fill, rgb)
    return np.concatenate([out_rgb, alpha0], axis=2).astype(bgra.dtype)


def trim_alpha(bgra, pad=2, extrude=2):
    """
    裁掉全透明外框 + 外扩 pad 像素。
    返回 (裁剪后的 BGRA, 在原图中的 bbox)

    B6：pad 与 extrude 是两件不同的事，必须成对使用：
      extrude = 把边缘像素颜色复制进外圈（防滤波时边缘发白毛）
      pad     = 再留透明边（防相邻格内容渗入）
    业界做法：extrude 1-2px 再 pad 1-2px。
    旧实现只做了 pad（扩大 bbox），框外仍是透明 —— 注释声称防渗色，
    但扩大 bbox 反而更容易吃到相邻格内容，是方向性错误。
    """
    a = bgra[:, :, 3]
    ys, xs = np.where(a > 12)
    if len(xs) == 0:
        return bgra, (0, 0, bgra.shape[1], bgra.shape[0])
    bgra = _extrude(bgra, a, extrude)
    x0, x1 = max(0, xs.min() - pad), min(bgra.shape[1], xs.max() + 1 + pad)
    y0, y1 = max(0, ys.min() - pad), min(bgra.shape[0], ys.max() + 1 + pad)
    return bgra[y0:y1, x0:x1], (x0, y0, x1 - x0, y1 - y0)


def clean_mask(bgra, thresh=128, feather=0.5, erode=1, cutoff=0.02):
    """
    【实测 bug】高斯羽化后角落 alpha 仍有 70/38/58/16，导致
    trim_alpha 的 bbox 覆盖整张图（1152x2048），裁不掉。

    根因：背景非纯色（有渐变/暗角），角点与参考色的距离
    超过硬阈值 scale*0.35，于是留下残片。

    修法：二值化 -> 取最大连通域 -> erode -> 羽化 -> cutoff。
    最大连通域这一步是必须的，否则零碎残片会让包围盒失控。

    B4 顺序铁律：先 erode 后 feather。
      颠倒会让羽化产生的半透明像素在收缩时被裁掉，边缘反而更硬。
      cutoff 清极低值噪点（业界 0.01-0.05），并拉伸补偿防整体变暗。
    """
    a = bgra[:, :, 3]
    _, bw = cv2.threshold(a, thresh, 255, cv2.THRESH_BINARY)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(bw, 8)
    if n > 1:
        # 0 是背景，从 1 起找面积最大
        idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        bw = (lab == idx).astype(np.uint8) * 255

    # B4：顺序铁律 —— 先 erode 收缩（去掉边缘残留的背景色污染），再羽化。
    # 顺序颠倒会让羽化产生的半透明像素在收缩时被裁掉，边缘反而更硬。
    if erode > 0:
        bw = cv2.erode(bw, np.ones((3, 3), np.uint8), iterations=int(erode))

    a2 = cv2.GaussianBlur(bw.astype(np.float64), (0, 0), feather)
    a2 = np.clip(a2 / 255.0, 0.0, 1.0)

    # B4：清除极低值噪点（实测角落残留 70/38/58/16），并拉伸补偿防止整体变暗
    a2 = np.where(a2 < cutoff, 0.0, a2)
    if cutoff > 0:
        a2 = np.clip(a2 / (1.0 - cutoff), 0.0, 1.0)

    out = bgra.copy()
    out[:, :, 3] = (np.clip(a2, 0.0, 1.0) * 255).astype(np.uint8)
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

from _despill import flood_key  # noqa: F401  (由 chroma.py 拆出，见 _despill.py)

def self_check(*a, **k):
    from chroma_selfcheck import self_check as _f
    return _f(*a, **k)


if __name__ == "__main__":
    import sys
    _ok, _ = self_check()
    sys.exit(0 if _ok else 1)