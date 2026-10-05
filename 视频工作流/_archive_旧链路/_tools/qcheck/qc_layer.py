#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qc_layer —— 图层一致性判定（从 qc_scene.py 拆出）。

拆出原因：qc_scene.py 加业界 6 维度量后达 432 行 / 14883 字符，超体积阈值，
gate_post 强制拆分。此处按职责划出「图层/色彩一致性度量的全部实现」。

为什么是 6 维而不是 2 维（业界对照，详见 QC_SCENE_EVIDENCE.json）：
  原自拟判定只比 dL(亮度) 与 dRB(色温) 两维。
  业界（PAI-Studio / PAI-Actor）做图层融合一致性用的是
  contrast / saturation / grain / sharpness 四维；
  deepfake 检测文献用 RGB 直方图 Bhattacharyya 距离 + 感知亮度
  L = 0.2126R + 0.7152G + 0.0722B（不是简单平均，也不是 LAB 的 L）。
  故补齐为：dL / dBhatta / dContrast / dSat / dSharp / dRB。

  实测（玄奘成片 120 帧）失败 5 维：
    dL=-50.7  dBhatta=0.98  dContrast=5.6  dSat=104.2  dRB=43.7
  含义：主体比背景暗 50、饱和度高 104、色温偏冷 44 —— 确实不像同一层。
"""
import cv2
import numpy as np

# 阈值（业界量级 + 本项目实测标定，见 QC_SCENE_EVIDENCE.json）
L_TOL = 15.0          # 感知亮度差
BHATTA_TOL = 0.30     # 直方图 Bhattacharyya 距离
CONTRAST_TOL = 4.0    # 对比度（灰度 std）差
SAT_TOL = 20.0        # 饱和度差
SHARP_TOL = 300.0     # 锐度（Laplacian 方差）差
HUE_TOL = 12.0        # 色温倾向 R-B 差


def _perceptual_luma(bgr):
    """感知亮度（deepfake 合成一致性论文式）：L = 0.2126R+0.7152G+0.0722B"""
    return (bgr[:, :, 2] * 0.2126 + bgr[:, :, 1] * 0.7152 + bgr[:, :, 0] * 0.0722)

def _bhattacharyya(h1, h2):
    """直方图 Bhattacharyya 距离。业界用它而非均值差：
    均值相同但分布形状不同（前景双峰 / 背景单峰）仍是明显不融合。"""
    h1 = h1.astype(float) / (h1.sum() + 1e-9)
    h2 = h2.astype(float) / (h2.sum() + 1e-9)
    return float(-np.log(max(np.sqrt(h1 * h2).sum(), 1e-9)))

def _hist_rgb(bgr, m, bins=16):
    out = []
    for c in range(3):
        h, _ = np.histogram(bgr[:, :, c][m], bins=bins, range=(0, 256))
        out.append(h)
    return np.concatenate(out)

def layer_delta(frame_bgr, bg_bgr, fg):
    """前景内部 vs 同位置背景。维度按业界补齐，不是只测亮度+色温。

    业界依据：
      PAI-Studio(2606.01399) / PAI-Actor(2609.05918) FG-BG Fusion 要求
      contrast、saturation、grain、sharpness 全部匹配，不止亮度与色温。
      deepfake 合成一致性论文：色彩用【直方图 Bhattacharyya 距离】，
      亮度用【感知亮度 L=0.2126R+0.7152G+0.0722B】均值差。
    """
    inner = cv2.erode(fg, np.ones((5, 5), np.uint8), iterations=1)
    if inner.sum() == 0 or bg_bgr is None:
        return None
    m = inner > 0
    if m.sum() < 50:
        return None
    f, b = frame_bgr, bg_bgr

    # 亮度（感知公式，非 LAB 的 L 通道）
    dL = float(_perceptual_luma(f)[m].mean() - _perceptual_luma(b)[m].mean())

    # 色彩分布距离（Bhattacharyya，业界做法）
    dB = _bhattacharyya(_hist_rgb(f, m), _hist_rgb(b, m))

    # 对比度：std 之比（PAI 的 contrast 项）
    cf = float(_perceptual_luma(f)[m].std())
    cb = float(_perceptual_luma(b)[m].std())
    dContrast = (cf - cb) / (cb + 1e-6)

    # 饱和度：HSV 的 S 均值差（PAI 的 saturation 项）
    fv = cv2.cvtColor(f, cv2.COLOR_BGR2HSV)[:, :, 1][m].mean()
    bv = cv2.cvtColor(b, cv2.COLOR_BGR2HSV)[:, :, 1][m].mean()
    dSat = float(fv - bv)

    # 锐度：拉普拉斯方差之比（PAI 的 sharpness 项）
    lf = float(cv2.Laplacian(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
    lb = float(cv2.Laplacian(cv2.cvtColor(b, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
    dSharp = (lf - lb) / (lb + 1e-6)

    # 色温倾向（保留：便宜且直观）
    dRB = float((f[:, :, 2][m].mean() - f[:, :, 0][m].mean())
                - (b[:, :, 2][m].mean() - b[:, :, 0][m].mean()))
    return {"dL": round(dL, 2), "dBhatta": round(dB, 3),
            "dContrast": round(dContrast, 3), "dSat": round(dSat, 2),
            "dSharp": round(dSharp, 3), "dRB": round(dRB, 2)}
