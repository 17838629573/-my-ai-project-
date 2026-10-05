#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q_c 光流一致性 + Q_d 遮挡/鬼影检测。

Q_c 依据（SpikeMM 2024 / NR-VQA optical flow GlobalSIP 2014）：
  ΔF_i = F_{i+1} - F_i         逐像素流场变化
  σ    = std(ΔF_i)             流一致性，越低越好
  σ_S  = std(||F_i||)          运动平滑度，越低越好
  失真会在光流统计上表现为局部与全局的不规则。
  关键洞见：通道丢失导致的时序不一致，SSIM 仍是 0.998 但光流已明显异常
           —— 说明像素级指标会漏判时序问题。

Q_d 依据（AP Flow Occlusion Mask / 计算摄影 §18.4）：
  前向-后向一致性残差  Δ(x) = F_{t→t+1}(x) + F_{t+1→t}(x + F_{t→t+1}(x))
  ||Δ(x)|| > abs_eps + rel_eps * ||F||   则为遮挡
  默认 abs_epsilon = 1.0 px，rel_epsilon = 0.05（按运动量缩放）
  注意：backward flow 必须真算，直接取负前向流会使该检查失去意义。
"""
import numpy as np
import cv2

# Farneback 参数（OpenCV 常用默认量级）
FARN = dict(pyr_scale=0.5, levels=3, winsize=15, iterations=3,
            poly_n=5, poly_sigma=1.2, flags=0)

ABS_EPS = 1.0      # px
REL_EPS = 0.05     # 按运动量缩放


def _to_gray_u8(a):
    """float[0,1] 或 BGR uint8 -> uint8 灰度。"""
    if a.ndim == 3:
        return cv2.cvtColor(a.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    return (np.clip(a, 0, 1) * 255).astype(np.uint8)


def flow_pair(prev, nxt):
    """算前向与后向光流（后向必须真算）。"""
    fwd = cv2.calcOpticalFlowFarneback(prev, nxt, None, **FARN)
    bwd = cv2.calcOpticalFlowFarneback(nxt, prev, None, **FARN)
    return fwd, bwd


def occlusion_mask(fwd, bwd, abs_eps=ABS_EPS, rel_eps=REL_EPS):
    """往返一致性残差 -> 遮挡掩码。True = 该像素遮挡/不可靠。"""
    h, w = fwd.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    # bwd 采样点：x + fwd(x)
    sx = np.clip(xs + fwd[..., 0], 0, w - 1)
    sy = np.clip(ys + fwd[..., 1], 0, h - 1)
    bwd_at = np.stack([
        cv2.remap(bwd[..., 0], sx, sy, cv2.INTER_LINEAR),
        cv2.remap(bwd[..., 1], sx, sy, cv2.INTER_LINEAR)], axis=-1)
    resid = fwd + bwd_at
    rnorm = np.sqrt((resid ** 2).sum(-1))
    fmag = np.sqrt((fwd ** 2).sum(-1))
    return rnorm > (abs_eps + rel_eps * fmag)


def analyze(src, max_frames=None, abs_eps=ABS_EPS, rel_eps=REL_EPS):
    """遍历帧对，返回逐帧指标 + 汇总。"""
    n = len(src)
    if max_frames:
        n = min(n, max_frames)
    per_frame = []
    prev_g = _to_gray_u8(src.gray(0))
    prev_flow = None
    for i in range(1, n):
        cur_g = _to_gray_u8(src.gray(i))
        fwd, bwd = flow_pair(prev_g, cur_g)
        fmag = np.sqrt((fwd ** 2).sum(-1))
        occ = occlusion_mask(fwd, bwd, abs_eps, rel_eps)
        rec = {"frame": i, "mean_motion": float(fmag.mean()),
               "occlusion_ratio": float(occ.mean())}
        if prev_flow is not None:
            d = fwd - prev_flow
            rec["flow_delta_std"] = float(np.std(d))
            rec["flow_delta_mean"] = float(np.mean(np.sqrt((d ** 2).sum(-1))))
        per_frame.append(rec)
        prev_flow = fwd
        prev_g = cur_g

    def col(k):
        v = [r[k] for r in per_frame if k in r]
        return v
    ds = col("flow_delta_std")
    ms = col("mean_motion")
    oc = col("occlusion_ratio")
    return {"per_frame": per_frame,
            "summary": {
                "flow_consistency_std": float(np.mean(ds)) if ds else 0.0,
                "motion_smoothness_std": float(np.std(ms)) if ms else 0.0,
                "mean_occlusion_ratio": float(np.mean(oc)) if oc else 0.0,
                "max_occlusion_ratio": float(np.max(oc)) if oc else 0.0,
                "frames_analyzed": n}}


def self_check():
    ok, bad = [], []
    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    rng = np.random.default_rng(1)
    H = W = 64

    class Fake:
        def __init__(self, f): self.f = f
        def __len__(self): return len(self.f)
        def gray(self, i): return self.f[i]

    # 1) 匀速平移：运动平滑，一致性好
    base = rng.random((H, W))
    shift = [np.roll(np.roll(base, i, axis=1), 0, axis=0) for i in range(8)]
    r1 = analyze(Fake(shift))
    # 2) 随机噪声：完全不一致
    noise = [rng.random((H, W)) for _ in range(8)]
    r2 = analyze(Fake(noise))
    add("1 平移的一致性优于噪声",
        r1["summary"]["flow_consistency_std"] < r2["summary"]["flow_consistency_std"],
        "%.3f vs %.3f" % (r1["summary"]["flow_consistency_std"],
                          r2["summary"]["flow_consistency_std"]))
    add("2 平移的运动量更稳定",
        r1["summary"]["motion_smoothness_std"] <=
        r2["summary"]["motion_smoothness_std"] + 1e-9,
        "%.3f vs %.3f" % (r1["summary"]["motion_smoothness_std"],
                          r2["summary"]["motion_smoothness_std"]))

    # 3) 遮挡检测：造一个"凭空出现"的物体
    a = np.full((H, W), 0.3)
    b = a.copy(); b[20:40, 20:40] = 0.9     # 突然出现方块
    fwd, bwd = flow_pair(_to_gray_u8(a), _to_gray_u8(b))
    occ = occlusion_mask(fwd, bwd)
    # 注意：均匀色块【内部】无纹理，Farneback 算不出流（残差≈0），
    # 遮挡主要出现在【边缘带】。取样应取边缘，不是整块。
    edge = np.zeros_like(occ, dtype=bool)
    edge[18:22, 18:42] = True; edge[38:42, 18:42] = True
    edge[18:42, 18:22] = True; edge[18:42, 38:42] = True
    add("3 凭空出现区域边缘判为遮挡", occ[edge].mean() > 0.3,
        "边缘遮挡率=%.2f (整块=%.2f, 内部无纹理故低)" %
        (occ[edge].mean(), occ[20:40, 20:40].mean()))

    # 4) 纯平移不该有大片遮挡
    c = np.roll(a, 4, axis=1)
    fwd2, bwd2 = flow_pair(_to_gray_u8(a), _to_gray_u8(c))
    occ2 = occlusion_mask(fwd2, bwd2)
    add("4 纯平移遮挡率低", occ2.mean() < 0.3, "遮挡率=%.2f" % occ2.mean())

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
