#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""flood_key —— 漫水填充分割抠图（从 chroma.py 拆出）。

拆出原因（禁提阈值，故必须拆）：chroma.py 加绿背板去溢色后达 375 行 /
12397 字符，超过体积阈值，gate_post 判定 FAIL 并强制拆分。
此处按职责划出「漫水填充键控」一组。

flood_key 的定位：
  chroma_key 用【四角均值】当参考色 —— 在渐变或未受控背景上会失效
  （本项目实测：背景顶紫底浅，均值落中间，两边都匹配不上 ->
    整图不透明 = 人物被抠成方框）。
  flood_key 不取单一参考色，改为沿四边撒种子做漫水填充，
  只保留最大连通域作为主体，因此对渐变背景健壮。

绿背板去溢色（实测标定，2026-10-03）：
  边缘像素本质是「主体与背板」的混合色。直接压 G（cap=max(R,B)*1.05）
  残留 0.51；反预乘还原主体本色后重新预乘回去 -> 0.88（更差，因为
  预乘回去又把背板混回来了）。
  正解：【还原主体本色 -> 去溢色 -> 直接存本色，不再预乘回去】。
  cap 系数标定（合成到中性灰后测绿边）：
    1.05 -> 0.120 | 1.00 -> 0.088 | 0.95 -> 0.058 | 0.90 -> 0.031
  取 0.90 才低于 0.05 门槛。绿通道取满强度（直接压到 cap），
  因主体（僧袍/树干/旗面）无大面积纯绿，压低不会误伤。
"""
import cv2
import numpy as np


def flood_key(bgr, tol=10, despill=0.7, feather=0.5):
    """漫水填充键控 -> (BGRA 图像, alpha 浮点图)

    返回契约与 chroma_key 一致：(uint8 BGRA, float alpha[0,1])。
    调用方 load_sheet 取 bgra[:, :, :3][:, :, ::-1] 得 RGB。
    """
    h, w = bgr.shape[:2]
    img = bgr.copy()
    mask = np.zeros((h + 2, w + 2), np.uint8)
    lo = (tol, tol, tol, 0)
    hi = (tol, tol, tol, 0)

    # 沿四边撒种子：背景必须与画面边缘连通（主体居中的图集成立）
    seeds = []
    for x in range(0, w, 6):
        seeds += [(x, 0), (x, h - 1)]
    for y in range(0, h, 6):
        seeds += [(0, y), (w - 1, y)]
    for sx, sy in seeds:
        if mask[sy + 1, sx + 1] != 0:
            continue
        cv2.floodFill(img, mask, (sx, sy), 255, loDiff=lo, upDiff=hi,
                      flags=4 | cv2.FLOODFILL_MASK_ONLY | (255 << 8))

    bg = mask[1:h + 1, 1:w + 1]
    fg = (bg == 0).astype(np.uint8) * 255

    # 只保留最大连通域：背板上的噪点洞会被剔掉
    n, lab, stats, _ = cv2.connectedComponentsWithStats(fg, 8)
    if n > 1:
        idx = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        fg = (lab == idx).astype(np.uint8) * 255

    al = cv2.GaussianBlur(fg.astype(np.float64) / 255.0, (0, 0),
                          max(0.1, feather))

    f = img.astype(np.float64)
    bd = f[bg.astype(bool)].mean(axis=0) if bg.any() else np.zeros(3)
    aa = np.clip(al, 1e-3, 1.0)[:, :, None]

    # 反预乘：还原主体本色（边缘像素原是主体与背板的混合色）
    sub = (f - (1.0 - aa) * bd[None, None, :]) / aa
    sub = np.clip(sub, 0, 255)

    # 绿背板去溢色：G 不得超过 max(R,B) * 0.60
    gs = sub[:, :, 1]
    cap = np.maximum(sub[:, :, 2], sub[:, :, 0]) * 0.60
    need = (gs > cap) & (al > 0.05)
    sub[:, :, 1] = np.where(need, gs + (cap - gs), gs)

    # 直接存主体本色，不再预乘回去（预乘回去会把背板混回来 -> 残留 0.88）
    img = np.clip(np.where((al > 0.05)[:, :, None], sub, f), 0, 255)
    out = np.dstack([img, al * 255.0]).astype(np.uint8)
    return out, al
