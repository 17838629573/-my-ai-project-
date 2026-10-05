#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q_e 帧间结构相似（IF-SSIM）。

依据（MNSS inter-frame SSIM / MC-SSIM 运动补偿 SSIM）：
  直接对【未对齐】的相邻帧算 SSIM，会把"正常运动"误判为跳变 —— 必须先对齐。
  IF-SSIM 的做法：用渲染器输出的运动向量对齐相邻帧后再算；
                  并用 2x2 pooling 抵消插值带来的低通模糊；
                  disoccluded 与 shading 变化的像素要 mask 掉。
  MC-SSIM 补充：块级运动估计（ARPS，块大小 b=8），取第二尺度计算，
                percentile pooling 而非简单平均。

本实现：cv2 无 contrib 的 QualitySSIM，故按 Wang 2004 经典式自实现。
       对齐用 qc_flow 的 Farneback 光流 warp；遮挡区由 qc_flow 提供掩码。
"""
import numpy as np
import cv2

from .qc_flow import flow_pair, occlusion_mask, _to_gray_u8

C1 = 0.01 ** 2
C2 = 0.03 ** 2
GAUSS_K = 11
GAUSS_S = 1.5


def _gauss():
    k = cv2.getGaussianKernel(GAUSS_K, GAUSS_S)
    return k * k.T


def ssim_map(a, b):
    """Wang SSIM 图（局部 SSIM），输入 uint8/float 灰度均可。"""
    a = a.astype(np.float64)
    b = b.astype(np.float64)
    g = _gauss()
    mu_a = cv2.filter2D(a, -1, g)
    mu_b = cv2.filter2D(b, -1, g)
    sa = cv2.filter2D(a * a, -1, g) - mu_a ** 2
    sb = cv2.filter2D(b * b, -1, g) - mu_b ** 2
    sab = cv2.filter2D(a * b, -1, g) - mu_a * mu_b
    num = (2 * mu_a * mu_b + C1) * (2 * sab + C2)
    den = (mu_a ** 2 + mu_b ** 2 + C1) * (sa + sb + C2)
    return num / np.maximum(den, 1e-12)


def ssim(a, b, mask=None):
    """标量 SSIM。mask=True 表示【排除】该像素。"""
    m = ssim_map(a, b)
    if mask is None:
        return float(m.mean())
    keep = ~mask
    if keep.sum() == 0:
        return float(m.mean())
    return float(m[keep].mean())


def warp(a_gray, flow):
    """用光流把 a 对齐到 b 的坐标系。

    OpenCV Farneback 约定：flow[x] 是 prev 中 x 处像素【到 next 的位移】，
    即 next[x + flow[x]] ≈ prev[x]。
    因此要得到"prev 变换到 next 坐标系"的图，须在位置 p 处取 prev[p - flow[p]]，
    映射网格是 (x - flow)，不是 (x + flow)。符号写反会让 SSIM 反而更低
    —— 第一轮就踩了这个坑。
    """
    h, w = a_gray.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    mx = xs - flow[..., 0]
    my = ys - flow[..., 1]
    if a_gray.dtype != np.uint8:
        src = (np.clip(a_gray, 0, 1) * 255).astype(np.uint8)
    else:
        src = a_gray
    return cv2.remap(src, mx.astype(np.float32), my.astype(np.float32),
                     cv2.INTER_LINEAR)


def _u8(a):
    if a.ndim == 3:
        return cv2.cvtColor(a.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    if a.dtype == np.uint8:
        return a
    return (np.clip(a, 0, 1) * 255).astype(np.uint8)


def analyze(src, max_frames=None, use_mask=True):
    """返回逐帧 {ssim_raw, ssim_aligned, ssim_aligned_masked, drop}。

    drop = ssim_aligned - ssim_raw 的负值方向：
      raw 很低但 aligned 很高 -> 正常运动（对齐后一致），不是跳变
      raw 低且 aligned 也低   -> 真跳变
    """
    n = len(src)
    if max_frames:
        n = min(n, max_frames)
    out = []
    for i in range(1, n):
        a = _u8(src.gray(i - 1))
        b = _u8(src.gray(i))
        fwd, bwd = flow_pair(a, b)
        raw = ssim(a, b)
        aw = warp(a, fwd)
        al = ssim(aw, b)
        if use_mask:
            occ = occlusion_mask(fwd, bwd)
            alm = ssim(aw, b, mask=occ)
        else:
            alm = al
        out.append({"frame": i, "ssim_raw": raw,
                    "ssim_aligned": al, "ssim_aligned_masked": alm,
                    "jump": bool(alm < 0.90)})
    vals = [r["ssim_aligned_masked"] for r in out]
    raws = [r["ssim_raw"] for r in out]
    return {"per_frame": out,
            "summary": {
                "mean_ssim_aligned": float(np.mean(vals)) if vals else 1.0,
                "min_ssim_aligned": float(np.min(vals)) if vals else 1.0,
                "mean_ssim_raw": float(np.mean(raws)) if raws else 1.0,
                "jump_frames": int(sum(1 for r in out if r["jump"])),
                "frames_analyzed": n}}


def self_check():
    ok, bad = [], []
    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    H = W = 64
    # 注意：Farneback 对【随机噪声纹理】失效（无平滑结构，孔径问题）。
    # 测试素材必须用结构化图案（渐变+斑块），否则测的是算法的极限而非逻辑。
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float64)
    tex = (0.5 + 0.35 * np.sin(xx / 6.0) * np.cos(yy / 7.0))
    tex = np.clip(tex, 0, 1)

    class Fake:
        def __init__(self, f): self.f = f
        def __len__(self): return len(self.f)
        def gray(self, i): return self.f[i]

    # 1) 完全相同 -> SSIM=1
    a = tex
    add("1 同图 SSIM=1", abs(ssim(_u8(a), _u8(a)) - 1.0) < 1e-6,
        "%.6f" % ssim(_u8(a), _u8(a)))

    # 2) 无关图案 -> SSIM 明显低
    b = np.clip(0.5 + 0.35 * np.sin(xx / 3.0 + 1.7) * np.cos(yy / 11.0), 0, 1)
    s2 = ssim(_u8(a), _u8(b))
    add("2 无关图 SSIM 低", s2 < 0.7, "%.3f" % s2)

    # 3) 关键：整体平移 -> raw 低但 aligned 高（正常运动不该判跳变）
    c = np.roll(a, 6, axis=1)
    fwd, bwd = flow_pair(_u8(a), _u8(c))
    aw = warp(_u8(a), fwd)
    raw = ssim(_u8(a), _u8(c))
    al = ssim(aw, _u8(c))
    add("3 平移对齐后 SSIM 回升", al > raw + 0.2,
        "raw=%.3f aligned=%.3f" % (raw, al))

    # 4) 真跳变（换成无关图）-> aligned 也低，判 jump
    r = analyze(Fake([a, b]))
    add("4 真跳变被标记", r["per_frame"][0]["jump"],
        "aligned=%.3f" % r["per_frame"][0]["ssim_aligned_masked"])

    # 5) 平移序列不该被标记跳变
    seq2 = [np.roll(a, k * 2, axis=1) for k in range(5)]
    r2 = analyze(Fake(seq2))
    add("5 平移序列零误判", r2["summary"]["jump_frames"] == 0,
        "jump=%d min=%.3f" % (r2["summary"]["jump_frames"],
                              r2["summary"]["min_ssim_aligned"]))

    print("PASS:")
    for x in ok: print("  " + x)
    if bad:
        print("FAIL:")
        for x in bad: print("  " + x)
    else:
        print("FAIL: 无")
    return not bad


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
