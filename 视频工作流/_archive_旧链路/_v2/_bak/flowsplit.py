# -*- coding: utf-8 -*-
"""flowsplit —— global/local 光流分离 + 运动掩码。

为什么必须分离（业界依据）：
  整图生成时，即使背景「没动」，两张关键帧的背景也存在几像素差异
  （亮度闪烁 / 纹理爬行 / 几何扭曲）。若直接全图用光流移动，
  这些伪差异会被当成真运动，导致背景蠕动、墙面弯曲。

正确顺序：
  全图光流 --> 估 global flow（背景整体运动）--> 减掉
           --> local flow（主体真运动）--> 只对这块做插帧

方法：
  1) 稀疏特征点 + RANSAC 估单应矩阵（背景平面运动）--> global flow
  2) 全图稠密光流 - global flow = local flow（主体真运动）
  3) local flow 幅值超阈值 --> 运动掩码

业界：
  GlobalSIP2017：homography 估 global，相减得 local
  MDPI(2025)：KMeans 把光流聚成前景/背景两类再剔除
  Wisconsin video retargeting：dominant motion estimation + EM 迭代
"""
from __future__ import annotations

import cv2
import numpy as np


# ---------- 1. 稠密光流 ----------
def dense_flow(prev_gray: np.ndarray,
               next_gray: np.ndarray,
               preset: str = "fast") -> np.ndarray:
    """DIS 稠密光流。返回 (H,W,2) float32，flow[...,0]=dx, [...,1]=dy。"""
    if prev_gray.ndim != 2 or next_gray.ndim != 2:
        raise ValueError("输入必须是灰度图")
    if prev_gray.shape != next_gray.shape:
        raise ValueError("两帧尺寸必须一致")
    p = {
        "fast": cv2.DISOPTICAL_FLOW_PRESET_FAST,
        "medium": cv2.DISOPTICAL_FLOW_PRESET_MEDIUM,
        "ultrafast": cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST,
    }[preset]
    dis = cv2.DISOpticalFlow_create(p)
    return dis.calc(prev_gray, next_gray, None)


def to_gray(img: np.ndarray) -> np.ndarray:
    """转灰度并做轻度高斯模糊，抑制闪烁噪声（业界建议）。"""
    if img.ndim == 3:
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        g = img
    return cv2.GaussianBlur(g, (5, 5), 0)


# ---------- 2. global flow（背景整体运动）----------
def global_homography(prev_gray: np.ndarray,
                      next_gray: np.ndarray,
                      max_corners: int = 300) -> np.ndarray | None:
    """用稀疏特征点 + RANSAC 估背景单应矩阵 H (3x3)。

    返回 None 表示特征点不足（纯色区域过多）。
    """
    feat = cv2.goodFeaturesToTrack(
        prev_gray, maxCorners=max_corners, qualityLevel=0.01, minDistance=8)
    if feat is None or len(feat) < 8:
        return None
    nxt, st, _ = cv2.calcOpticalFlowPyrLK(prev_gray, next_gray, feat, None)
    if nxt is None or st is None:
        return None
    ok = st.reshape(-1) == 1
    if ok.sum() < 8:
        return None
    src = feat.reshape(-1, 2)[ok]
    dst = nxt.reshape(-1, 2)[ok]
    H, mask = cv2.findHomography(src, dst, cv2.RANSAC, 3.0)
    if H is None:
        return None
    # 判定：内点比例过低说明不是平面背景运动，退化处理
    if mask is not None and mask.reshape(-1).mean() < 0.4:
        return None
    return H


def global_flow_field(H: np.ndarray, shape: tuple) -> np.ndarray:
    """由单应矩阵生成逐像素 global flow 场 (H,W,2)。

    对每个像素 x，global = H·x - x
    """
    h, w = shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    ones = np.ones_like(xs)
    denom = H[2, 0] * xs + H[2, 1] * ys + H[2, 2]
    denom = np.where(np.abs(denom) < 1e-6, 1e-6, denom)
    px = (H[0, 0] * xs + H[0, 1] * ys + H[0, 2]) / denom
    py = (H[1, 0] * xs + H[1, 1] * ys + H[1, 2]) / denom
    out = np.empty((h, w, 2), np.float32)
    out[..., 0] = px - xs
    out[..., 1] = py - ys
    return out


# ---------- 3. local flow + 运动掩码 ----------
def split(prev_gray: np.ndarray,
          next_gray: np.ndarray,
          thr: float = 1.5,
          preset: str = "fast") -> dict:
    """主入口：分离 global / local，返回运动掩码。

    返回 dict:
      global_H   单应矩阵或 None
      gflow      global flow 场（背景）
      lflow      local flow 场（主体真运动）
      mag        local flow 幅值
      mask       uint8 掩码，255=主体在动
      ratio      运动像素占比
    """
    flow = dense_flow(prev_gray, next_gray, preset)
    H = global_homography(prev_gray, next_gray)
    if H is None:
        # 退化：无法估背景运动，视为静止相机，global 取中位向量
        med = np.median(flow.reshape(-1, 2), axis=0)
        gflow = np.zeros_like(flow)
        gflow[..., 0] = med[0]
        gflow[..., 1] = med[1]
    else:
        gflow = global_flow_field(H, flow.shape)
    lflow = flow - gflow
    mag = np.sqrt(lflow[..., 0] ** 2 + lflow[..., 1] ** 2)
    mask = (mag > thr).astype(np.uint8) * 255
    # 形态学清理：去噪点 + 填补空洞
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, k)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    return {
        "global_H": H,
        "gflow": gflow,
        "lflow": lflow,
        "mag": mag,
        "mask": mask,
        "ratio": float((mask > 0).mean()),
        "degraded": H is None,
    }


# ---------- 自检 ----------
def self_check() -> None:
    h, w = 240, 320
    # 结构化纹理（棋盘格）：光流需要可追踪的边角，
    # 模糊随机噪声各向同性，位移后光流算不出——这是测试构造的坑，不是代码缺陷
    yy, xx = np.mgrid[0:h, 0:w]
    bg = (((xx // 16) + (yy // 16)) % 2 * 200 + 30).astype(np.uint8)
    bg = cv2.GaussianBlur(bg, (0, 0), 0.8)

    # frame A
    A = bg.copy()
    # frame B：整体右移 3px（相机/背景运动）+ 中心块下移 12px（主体真运动）
    M = np.float32([[1, 0, 3], [0, 1, 0]])
    B = cv2.warpAffine(bg, M, (w, h))
    # 主体：把一块结构化图案整体下移 12px（不是 roll，roll 在周期纹理上退化）
    patch = bg[80:140, 120:200].copy()
    B[80:140, 120:200] = 0
    B[92:152, 120:200] = np.maximum(B[92:152, 120:200], patch)

    ga, gb = to_gray(A), to_gray(B)
    r = split(ga, gb, thr=1.5)

    # 1) 掩码应主要落在主体区域，而非静止背景
    inside = r["mask"][92:152, 120:200].mean() / 255.0
    outside = r["mask"][0:70, 0:100].mean() / 255.0
    assert inside > 0.4, (
        f"主体区域未被检出: {inside:.3f} mag_max={r['mag'].max():.2f}")
    assert outside < 0.25, f"静止背景被误判为运动: {outside:.3f}"

    # 2) global 平移应约等于 3px
    if not r["degraded"]:
        g = r["gflow"][..., 0]
        assert abs(np.median(g) - 3.0) < 1.2, f"global 平移估错: {np.median(g)}"

    # 3) local 幅值：主体区域应显著大于背景
    mi = r["mag"][92:152, 120:200].mean()
    mo = r["mag"][0:70, 0:100].mean()
    assert mi > mo * 2, f"local 未分离: 主体{mi:.2f} 背景{mo:.2f}"

    # 4) 纯静止两帧：掩码应几乎为零（背景锁死验证）
    r2 = split(ga, ga, thr=1.5)
    assert r2["ratio"] < 0.02, f"静止帧仍报运动: {r2['ratio']}"

    # 5) 尺寸不一致必须抛
    try:
        split(ga, gb[:, :100])
        raise AssertionError("应当抛 ValueError")
    except ValueError:
        pass

    print("flowsplit self_check OK  主体%.2f 背景%.2f global=%.2fpx ratio=%.3f"
          % (inside, outside, np.median(r["gflow"][..., 0]), r["ratio"]))


if __name__ == "__main__":
    self_check()
