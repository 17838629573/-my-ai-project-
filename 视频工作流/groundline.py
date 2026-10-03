#!/usr/bin/env python3
"""地基线探测：从背景图自动找出"人能站在哪条水平线上"。
依赖: (无本地依赖)
被依赖: build_video, scale_map
改前必读: IMPROVE_groundline.md
"""
import numpy as np
import cv2


def _row_strength(bgr, sigma=None):
    """高斯低通去细边 -> Sobel-y 提水平边缘 -> 按行累加。对应 ODU + Simon et al."""
    gray = cv2.cvtColor(bgr.astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float64)
    # σ = H/50（ODU 原值）。低通是滤砖缝的核心机制：周期 60px 的振荡
    # 在 σ=19 下衰减到约 0.1 倍，而墙顶这类大尺度阶跃几乎不受影响。
    # 曾收窄到 [2,8] 导致砖缝滤不掉，勿再改小。
    s = float(np.clip(bgr.shape[0] / 50.0, 4.0, 40.0)) if sigma is None else sigma
    blur = cv2.GaussianBlur(gray, (0, 0), s)
    sob = np.abs(cv2.Sobel(blur, cv2.CV_64F, 0, 1, ksize=3))
    return sob.sum(axis=1) / max(1, sob.shape[1])


def probe(bgr, y, band_px=24):
    """返回指定行的双侧窄带颜色对比度，供 AI 复核某条候选。"""
    H = bgr.shape[0]
    y = int(np.clip(y, 1, H - 2))
    a = bgr[max(0, y - band_px):y].reshape(-1, 3).mean(axis=0)
    b = bgr[y + 1:min(H, y + 1 + band_px)].reshape(-1, 3).mean(axis=0)
    na = min(y, band_px); nb = min(H - 1 - y, band_px)
    return {"y": y, "contrast": float(np.abs(a - b).mean()),
            "n_above": na, "n_below": nb,
            "above_rgb": [round(float(v), 1) for v in a[::-1]],
            "below_rgb": [round(float(v), 1) for v in b[::-1]]}


MULTI_SCALE = (24, 48, 96)


def _multiscale_contrast(bgr, y, band_px):
    """多尺度双侧对比度取最小。

    真实分界线在任何尺度上都成立；砖缝/条纹只在小于其周期的窗口里像分界。
    取最小即可让任何周期 < 最大窗口的振荡结构自动出局。
    """
    vals = []
    for b in MULTI_SCALE:
        if b < band_px // 2:
            continue
        p = probe(bgr, y, b)
        # 窗口被图像边界截断时该尺度作废：靠边的行会拿到虚高对比度
        if min(p["n_above"], p["n_below"]) < b * 0.9:
            continue
        vals.append(p["contrast"])
    return min(vals) if vals else 0.0


def detect(bgr, band_px=24, top_n=16, y_range=None, sigma=None):
    """自动探测地基线。

    score = 归一化行强度 × 归一化多尺度对比度
    只取强度会把"砖缝/条纹"误判成地线——需靠多尺度对比度排除。
    """
    H = bgr.shape[0]
    st = _row_strength(bgr, sigma)
    y0, y1 = (1, H - 2) if y_range is None else (max(1, y_range[0]), min(H - 2, y_range[1]))
    st[:y0] = 0.0
    st[y1 + 1:] = 0.0
    if st.max() <= 1e-9:
        return {"baseline_y": None, "confidence": 0.0, "candidates": [],
                "evidence": "全图无有效水平边缘"}

    order = np.argsort(st)[::-1]
    gap = max(1, band_px // 2)
    cands = []
    for y in order:
        y = int(y)
        if all(abs(y - c) >= gap for c in cands):      # 非极大抑制
            cands.append(y)
        if len(cands) >= top_n:
            break

    rows = []
    for y in cands:
        p = probe(bgr, y, band_px)
        rows.append({"y": y, "strength": float(st[y]),
                     "contrast": _multiscale_contrast(bgr, y, band_px),
                     "contrast_local": p["contrast"]})
    smax = max(r["strength"] for r in rows) or 1.0
    cmax = max(r["contrast"] for r in rows) or 1.0
    for r in rows:
        r["score"] = (r["strength"] / smax) * (r["contrast"] / cmax)
    rows.sort(key=lambda r: -r["score"])

    top = rows[0]
    margin = top["score"] - (rows[1]["score"] if len(rows) > 1 else 0.0)
    return {
        "baseline_y": top["y"],
        "confidence": round(float(margin), 4),
        "candidates": rows,
        "evidence": probe(bgr, top["y"], band_px),
    }


def self_check():
    ok = True

    def chk(name, cond, info=""):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name + (("  " + info) if info else ""))
        if not cond:
            ok = False

    # 1 基本功能：上浅下深分界在 y=480
    im = np.zeros((960, 540, 3), np.uint8)
    im[:480] = (200, 200, 200)
    im[480:] = (60, 60, 60)
    r = detect(im)
    chk("1 基本分界定位", abs(r["baseline_y"] - 480) <= 3, f"得 {r['baseline_y']}")

    # 2 关键证伪：零均值砖缝（在 205 上下对称振荡，无直流跳变）
    im2 = np.full((960, 540, 3), 255, np.uint8)
    im2[300:] = 205                                  # 真实地线：255->205
    for y in range(400, 960, 60):                    # 零均值条纹：均值同为 205
        im2[y:y + 30] = 155
        im2[y + 30:y + 60] = 255
    r2 = detect(im2)
    pure_strength_row = int(np.argsort(_row_strength(im2))[::-1][0])
    chk("2a 纯强度会选错", pure_strength_row >= 400,
        f"纯强度选了 y={pure_strength_row}(砖缝区，错误答案)")
    chk("2b score 选真实分界", abs(r2["baseline_y"] - 300) <= 4,
        f"得 {r2['baseline_y']}")
    c_loc = probe(im2, 700, 24)["contrast"]
    c_mul = _multiscale_contrast(im2, 700, 24)
    chk("2c 多尺度压低砖缝", c_mul < c_loc * 0.5,
        f"局部 {c_loc:.1f} -> 多尺度 {c_mul:.1f}")
    chk("2d 真实分界多尺度稳定",
        abs(_multiscale_contrast(im2, 300, 24) - 50.0) < 1.0,
        f"y=300 多尺度 {_multiscale_contrast(im2, 300, 24):.1f}")

    # 3 非极大抑制：候选间距足够
    r3 = detect(im2, band_px=24)
    ys = sorted(c["y"] for c in r3["candidates"])
    chk("3 候选非极大抑制", all(b - a >= 12 for a, b in zip(ys, ys[1:])), f"候选 {ys[:4]}")

    # 4 y_range 限定生效
    r4 = detect(im, y_range=(600, 900))
    chk("4 y_range 限定", r4["baseline_y"] is None or r4["baseline_y"] >= 600,
        f"得 {r4['baseline_y']}")

    # 5 probe 与 detect 一致
    r5 = detect(im)
    p5 = probe(im, r5["baseline_y"])
    chk("5 probe 一致", abs(p5["contrast"] - r5["evidence"]["contrast"]) < 1e-6)

    # 6 纯色图不崩
    r6 = detect(np.full((200, 200, 3), 128, np.uint8))
    chk("6 纯色图不崩", r6["baseline_y"] is None, r6["evidence"] if isinstance(r6["evidence"], str) else "")

    # 7 返回键齐全
    need = {"baseline_y", "confidence", "candidates", "evidence"}
    chk("7 返回键齐全", need <= set(r.keys()), str(sorted(r.keys())))

    print(("8 项 -> PASS" if ok else "8 项 -> FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    import sys
    sys.exit(self_check())
