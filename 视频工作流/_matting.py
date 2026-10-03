"""抠图/matting：从 sprite 单格提取软 alpha 前景。

业界依据（已搜证）：
- GrabCut（Rother-Kolmogorov-Blake 2004）是 OpenCV 内置的 canonical interactive
  method：给定矩形/trimap，用 GMM 学习前景/背景颜色模型 + 图割求解。
  我们不是通用抠图场景——sprite sheet 的每格位置已知，人物居中，
  结构先验可替代用户交互，自动给出 trimap。
- 色度键（chroma key）仅适用于均匀打光的纯色背景；对渐变背景、
  半透明/毛发边缘会失败，业界建议不规则形状改用 alpha mask。
- closed-form matting（Levin 2008）需 trimap + 解稀疏线性系统，
  本模块先用 GrabCut 求硬分割，再羽化成软 alpha（羽毛半径可配）。

铁律111：禁止用精确 RGB 判定背景色（模型会"艺术化"背景）。
铁律112：抠图结果只保留含格中心的连通域，禁保留四方形整格。
"""
import numpy as np
import cv2

__all__ = [
    "auto_trimap",
    "grabcut_alpha",
    "keep_center_component",
    "feather_alpha",
    "matte_cell",
    "split_sheet",
]


def _border_ring(h, w, ratio):
    """边缘环 mask：True 表示属于确定背景带。"""
    m = np.zeros((h, w), bool)
    br = max(2, int(round(min(h, w) * ratio)))
    m[:br, :] = True
    m[-br:, :] = True
    m[:, :br] = True
    m[:, -br:] = True
    return m


def auto_trimap(bgr, border_ratio=0.10, fg_ratio=0.35, unknown_band=0.06):
    """自动 trimap：边缘环=确定背景，中心矩形=确定前景，中间=未知。

    返回 uint8：0=背景 128=未知 255=前景
    """
    if bgr.ndim != 3 or bgr.shape[2] != 3:
        raise ValueError("auto_trimap 需要 3 通道 BGR 图")
    h, w = bgr.shape[:2]
    ring = _border_ring(h, w, border_ratio)

    # 背景颜色模型：用边缘环像素的均值/标准差（不假设具体色值，铁律111）
    ring_px = bgr[ring].astype(np.float32)
    if ring_px.size == 0:
        raise ValueError("边缘环为空，无法估计背景色")
    mu = ring_px.mean(axis=0)
    sd = ring_px.std(axis=0)
    sd = np.maximum(sd, 1e-3)
    # 马氏距离（对角近似）
    d = np.sqrt((((bgr.astype(np.float32) - mu) / sd) ** 2).sum(axis=2))

    ub = max(2, int(round(min(h, w) * unknown_band)))
    fg = np.zeros((h, w), bool)
    cy, cx = h // 2, w // 2
    fh = max(2, int(h * fg_ratio))
    fw = max(2, int(w * fg_ratio))
    fg[cy - fh // 2:cy + fh // 2, cx - fw // 2:cx + fw // 2] = True
    fg &= ~ring

    # 未知带：确定前景向外膨胀 ub 像素
    k = np.ones((2 * ub + 1, 2 * ub + 1), np.uint8)
    fg_dil = cv2.dilate(fg.astype(np.uint8), k) > 0
    unknown = fg_dil & ~fg
    # 未知带内按颜色距离再切一层：离背景近的归背景候选
    unk_far = unknown & (d > 2.0)

    tri = np.full((h, w), 128, np.uint8)
    tri[ring] = 0
    tri[fg] = 255
    tri[unknown & ~unk_far] = 0
    tri[unk_far] = 128
    return tri


def grabcut_alpha(bgr, trimap, iters=6):
    """GrabCut：以 trimap 初始化，返回软 alpha（0-255 uint8）。"""
    h, w = bgr.shape[:2]
    if trimap.shape != (h, w):
        raise ValueError("trimap 尺寸与图不一致")
    mask = np.full((h, w), cv2.GC_PR_FGD, np.uint8)
    mask[trimap == 0] = cv2.GC_BGD
    mask[trimap == 255] = cv2.GC_FGD
    mask[trimap == 128] = cv2.GC_PR_FGD
    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)
    cv2.grabCut(bgr, mask, None, bgd, fgd, int(iters), cv2.GC_INIT_WITH_MASK)
    alpha = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0)
    return alpha.astype(np.uint8)


def keep_center_component(alpha):
    """只保留包含图像中心的连通域（铁律112：禁保留整格四方形）。"""
    a = (alpha > 127).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(a, 8)
    if n <= 1:
        return alpha
    h, w = a.shape
    cy, cx = h // 2, w // 2
    best, best_area = 0, -1
    for i in range(1, n):
        x, y, ww, hh, area = stats[i]
        if x <= cx <= x + ww and y <= cy <= y + hh and area > best_area:
            best, best_area = i, area
    if best == 0:
        # 中心不在任何连通域内：退化为面积最大者
        areas = stats[1:, cv2.CC_STAT_AREA]
        if areas.size == 0:
            return np.zeros_like(alpha)
        best = int(np.argmax(areas)) + 1
    return np.where(lab == best, alpha, 0).astype(np.uint8)


def feather_alpha(alpha, radius=2):
    """硬 alpha → 软 alpha：边缘羽化 radius 像素。"""
    if radius <= 0:
        return alpha
    a = alpha.astype(np.float32) / 255.0
    k = max(1, int(round(radius)))
    kern = np.ones((2 * k + 1, 2 * k + 1), np.float32) / float((2 * k + 1) ** 2)
    blur = cv2.filter2D(a, -1, kern)
    # 仅在原边界附近混合，避免整体变淡
    edge = cv2.morphologyEx(
        (alpha > 127).astype(np.uint8), cv2.MORPH_GRADIENT,
        np.ones((2 * k + 1, 2 * k + 1), np.uint8))
    out = np.where(edge > 0, blur, a)
    return np.clip(out * 255.0, 0, 255).astype(np.uint8)


def matte_cell(bgr, border_ratio=0.10, feather=2, iters=6):
    """单格完整抠图：trimap → GrabCut → 中心连通域 → 羽化。"""
    tri = auto_trimap(bgr, border_ratio=border_ratio)
    al = grabcut_alpha(bgr, tri, iters=iters)
    al = keep_center_component(al)
    al = feather_alpha(al, radius=feather)
    return al, tri


def split_sheet(sheet, cols, rows):
    """按网格切分图集，返回 list[ndarray]，行优先。"""
    if sheet.ndim != 3:
        raise ValueError("图集需为 3 通道")
    h, w = sheet.shape[:2]
    cw, ch = w // cols, h // rows
    cells = []
    for r in range(rows):
        for c in range(cols):
            cells.append(sheet[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw].copy())
    return cells
