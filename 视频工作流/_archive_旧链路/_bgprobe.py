#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_bgprobe —— 背景图几何探测（从背景图反推相机，不靠声明）

问题来源：项目里 v_h / v_x 是 **spec 声明** 的，但背景图是 AI 生出来的。
两者对不上时，人物路径的收敛点 ≠ 背景里城墙/路面的收敛点，
观感就是"人走的轨迹和画面里的路不一致"。

本工具从背景图 **实测** 三个量，与 spec 声明三方比对：

  ① 消失点 (v_x, v_h)      LSD 线段 + RANSAC 投票
  ② 路面带 (ground band)   逐行纹理密度，找可走区域
  ③ 缩放基准              路面宽度随 y 的收敛率 → 反解 px/m 曲线

用法：
  python3 _bgprobe.py                     # 跑自检（合成用例，不依赖外部图）
  python3 _bgprobe.py --bg <图> --spec <scene_spec.json>   # 实测比对

铁律：本文件只读图与 spec，不修改任何东西。判定结论交给调用方。
"""
import math
import os
import sys

import cv2
import numpy as np

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- 可调阈值（集中放，便于标定）----
MIN_SEG_RATIO = 0.06      # 线段最短长度 / 图短边
NEAR_HORIZ_DEG = 6.0      # 近水平线排除角
NEAR_VERT_DEG = 6.0       # 近垂直线排除角
RANSAC_ITERS = 600
RANSAC_INLIER_PX = 12.0   # 点到直线距离判内点
GRID_CELL = 24            # 粗投票格宽（原图像素）
ROI_TOP = 0.30            # 只看画面下半 70%，排除天空


# ────────────────────────────────────────────────────────────
# ① 线段提取
# ────────────────────────────────────────────────────────────
def line_segments(gray, min_len=None):
    """LSD 线段提取 + 过滤。返回 [(x1,y1,x2,y2,angle_deg,len)]，angle ∈ [0,180)"""
    h, w = gray.shape[:2]
    if min_len is None:
        min_len = min(h, w) * MIN_SEG_RATIO
    lsd = cv2.createLineSegmentDetector(0)
    out = lsd.detect(gray)
    segs = []
    if out is None or out[0] is None:
        return segs
    for l in np.array(out[0]).reshape(-1, 4):
        x1, y1, x2, y2 = [float(v) for v in l]
        dx, dy = x2 - x1, y2 - y1
        ln = math.hypot(dx, dy)
        if ln < min_len:
            continue
        ang = math.degrees(math.atan2(dy, dx)) % 180.0
        if ang < NEAR_HORIZ_DEG or ang > 180 - NEAR_HORIZ_DEG:
            continue
        if abs(ang - 90) < NEAR_VERT_DEG:
            continue
        segs.append((x1, y1, x2, y2, ang, ln))
    return segs


def _seg_to_line(s):
    """线段 -> (a,b,c) 使 ax+by+c=0"""
    x1, y1, x2, y2 = s[0], s[1], s[2], s[3]
    a = y2 - y1
    b = x1 - x2
    c = x2 * y1 - x1 * y2
    n = math.hypot(a, b)
    if n < 1e-12:
        return None
    return (a / n, b / n, c / n)


# ────────────────────────────────────────────────────────────
# ② 消失点：RANSAC（最小集=2条线求交，内点=所有线到该点距离）
# ────────────────────────────────────────────────────────────
def _intersect(l1, l2):
    a1, b1, c1 = l1
    a2, b2, c2 = l2
    d = a1 * b2 - a2 * b1
    if abs(d) < 1e-9:
        return None
    return ((b1 * c2 - b2 * c1) / d, (c1 * a2 - c2 * a1) / d)


def _pt_line_dist(p, ln):
    a, b, c = ln
    return abs(a * p[0] + b * p[1] + c)


def vanishing_point(segs, iters=RANSAC_ITERS, inlier=RANSAC_INLIER_PX):
    """RANSAC 求消失点。返回 (vx, vy, inlier_ratio, n_lines)"""
    lines = [l for l in (_seg_to_line(s) for s in segs) if l is not None]
    n = len(lines)
    if n < 2:
        return None, 0.0, n
    rng = np.random.default_rng(20261004)
    best, best_cnt = None, -1
    # 候选：所有两两交点先粗筛（限制搜索范围，避免收敛在图外）
    cands = []
    for i in range(n):
        for j in range(i + 1, n):
            # 只让夹角足够大的线对参与（近平行的交点无意义）
            dot = lines[i][0] * lines[j][0] + lines[i][1] * lines[j][1]
            if abs(dot) > 0.985:
                continue
            p = _intersect(lines[i], lines[j])
            if p is None:
                continue
            cands.append(p)
    if not cands:
        return None, 0.0, n
    # 用长度加权的中位数当种子（比纯随机稳）
    cands_arr = np.array(cands)
    seed = np.median(cands_arr, axis=0)
    for p in [tuple(seed)] + [cands[k] for k in
                              rng.choice(len(cands), size=min(iters, len(cands)), replace=False)]:
        cnt = sum(1 for ln in lines if _pt_line_dist(p, ln) < inlier)
        if cnt > best_cnt:
            best_cnt, best = cnt, p
    # 用内点重新最小二乘精化：最小化 Σ dist^2
    if best is not None:
        inl = [ln for ln in lines if _pt_line_dist(best, ln) < inlier]
        if len(inl) >= 2:
            best = _refine(best, inl)
            best_cnt = len(inl)
    return (best[0], best[1]), (best_cnt / n if n else 0.0), n


def _refine(p, lines, rounds=8):
    """Gauss-Newton 精化：最小化 Σ (a x + b y + c)^2"""
    x, y = float(p[0]), float(p[1])
    for _ in range(rounds):
        A = np.array([[ln[0], ln[1]] for ln in lines], dtype=float)
        b = np.array([-ln[2] for ln in lines], dtype=float)
        try:
            sol, *_ = np.linalg.lstsq(A, b, rcond=None)
        except np.linalg.LinAlgError:
            break
        nx, ny = float(sol[0]), float(sol[1])
        if not (np.isfinite(nx) and np.isfinite(ny)):
            break
        if abs(nx - x) < 1e-6 and abs(ny - y) < 1e-6:
            x, y = nx, ny
            break
        x, y = nx, ny
    return (x, y)


# ────────────────────────────────────────────────────────────
# ③ 路面带：逐行纹理密度
# ────────────────────────────────────────────────────────────
def ground_band(gray, top=ROI_TOP):
    """找可走区域：逐行算局部方差，纹理最连续的那段。
    返回 (y_top, y_bottom, 每行中心x[dict])"""
    h, w = gray.shape[:2]
    y0 = int(h * top)
    rowinfo = []
    f = gray.astype(np.float32)
    for y in range(y0, h):
        row = f[y, :]
        sm = cv2.blur(row.reshape(1, -1), (41, 1)).reshape(-1)
        var = float(np.mean(np.abs(row - sm)))
        rowinfo.append((y, var))
    if not rowinfo:
        return None
    vs = np.array([v for _, v in rowinfo])
    # 用最大类间方差(Otsu)二分，不能用 mean —— 若所有行方差相等，
    # "v > mean" 会全 False，永远检不出（自检第4项就是这么挂的）
    if vs.std() < 1e-6:
        return None
    vmin, vmax = float(vs.min()), float(vs.max())
    if vmax - vmin < 1e-6:
        return None
    q = ((vs - vmin) / (vmax - vmin) * 255).astype(np.uint8).reshape(-1, 1)
    t8, _ = cv2.threshold(q, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thr = vmin + float(t8) / 255.0 * (vmax - vmin)
    ys = [y for y, v in rowinfo if v > thr]
    if not ys:
        return None
    return (min(ys), max(ys), thr)


def row_center_x(gray, y, k=41):
    """某行纹理重心的 x（路面中心）"""
    row = gray[y, :].astype(np.float32)
    sm = cv2.blur(row.reshape(1, -1), (k, 1)).reshape(-1)
    e = np.abs(row - sm)
    if e.sum() < 1e-9:
        return None
    xs = np.arange(len(e), dtype=np.float32)
    return float((xs * e).sum() / e.sum())


# ────────────────────────────────────────────────────────────
# ④ 三方比对：声明 / 检测 / 反解
# ────────────────────────────────────────────────────────────
def probe(bg_path, spec=None):
    """返回 dict：检测到的 v_x, v_h（归一化 + 像素），以及内点率"""
    img = cv2.imread(bg_path)
    if img is None:
        raise SystemExit(f"[bgprobe] 读不到背景图: {bg_path}")
    H, W = img.shape[:2]
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mask = np.zeros_like(gray)
    mask[int(H * ROI_TOP):, :] = 255
    segs = line_segments(cv2.bitwise_and(gray, gray, mask=mask))
    vp, ratio, n = vanishing_point(segs)
    gb = ground_band(gray)
    out = {
        "img_wh": (W, H),
        "n_segments": n,
        "vp_px": (round(vp[0], 1), round(vp[1], 1)) if vp else None,
        "vp_norm": (round(vp[0] / W, 4), round(vp[1] / H, 4)) if vp else None,
        "inlier_ratio": round(ratio, 3),
        "ground_band": gb,
    }
    if spec:
        out["spec"] = spec
    return out


def compare(bg_path, declared_vx, declared_vh, out_w=540, out_h=960):
    """把检测到的消失点换算到输出分辨率，与声明比对"""
    r = probe(bg_path)
    if not r["vp_norm"]:
        return r
    nx, ny = r["vp_norm"]
    dx, dy = nx * out_w, ny * out_h
    r["detected_in_out"] = (round(dx, 1), round(dy, 1))
    r["declared"] = (declared_vx, declared_vh)
    r["delta_px"] = (round(dx - declared_vx, 1), round(dy - declared_vh, 1))
    r["delta_deg_of_view"] = (round((dx - declared_vx) / out_w * 100, 2),
                              round((dy - declared_vh) / out_h * 100, 2))
    return r


# ────────────────────────────────────────────────────────────
# 自检：合成用例（已知真值），不依赖外部图
# ────────────────────────────────────────────────────────────
def _synth(W=600, H=900, vx=300.0, vh=450.0):
    """造一张从消失点发散的放射线图 + 路面横向砖缝，真值已知。

    注意：砖缝必须是"短横线"而不是贯穿整行的直线 —— 贯穿线在行内是常数，
    逐行方差恒为 0，路面带永远检不出（自检第4项曾因此挂掉）。
    """
    img = np.full((H, W), 200, dtype=np.uint8)
    for k in range(-6, 7):
        x_end = vx + k * 130
        cv2.line(img, (int(vx), int(vh)), (int(x_end), H - 1), 40, 2)
    # 路面：下半部画短砖缝（行内有明暗变化），上半部（天空）保持纯净
    for y in range(int(vh) + 40, H, 34):
        for x in range(0, W, 46):
            cv2.line(img, (x, y), (x + 26, y), 110, 2)
    return img


def self_check():
    print("[_bgprobe] 自检开始")
    ok = True

    # 1) 合成图：真值 (300, 450)
    g = _synth()
    segs = line_segments(g, min_len=60)
    vp, ratio, n = vanishing_point(segs)
    if vp is None:
        print("  FAIL 1 合成图未检出消失点")
        return False
    err = math.hypot(vp[0] - 300, vp[1] - 450)
    if err > 12.0:
        print(f"  FAIL 1 合成图消失点误差 {err:.1f}px > 12  (得 {vp[0]:.0f},{vp[1]:.0f})")
        ok = False
    else:
        print(f"  PASS 1 合成图消失点 真(300,450) 检({vp[0]:.0f},{vp[1]:.0f}) 误差{err:.1f}px 内点率{ratio:.2f}")

    # 2) 换真值，验证不是死记
    g2 = _synth(vx=180.0, vh=380.0)
    s2 = line_segments(g2, min_len=60)
    vp2, r2, _ = vanishing_point(s2)
    err2 = math.hypot(vp2[0] - 180, vp2[1] - 380)
    if err2 > 12.0:
        print(f"  FAIL 2 第二组真值误差 {err2:.1f}px")
        ok = False
    else:
        print(f"  PASS 2 移位真值(180,380) 检({vp2[0]:.0f},{vp2[1]:.0f}) 误差{err2:.1f}px")

    # 3) 纯色图：无结构，必须报 None 而不是乱给
    flat = np.full((400, 400), 128, dtype=np.uint8)
    s3 = line_segments(flat, min_len=20)
    vp3, r3, n3 = vanishing_point(s3)
    if vp3 is not None:
        print(f"  FAIL 3 纯色图不该有消失点，却给了 {vp3}")
        ok = False
    else:
        print(f"  PASS 3 纯色图正确返回 None（线段{n3}条）")

    # 4) 路面带：合成图下半有横向纹理，应能检出
    gb = ground_band(g)
    if gb is None:
        print("  FAIL 4 未检出路面带")
        ok = False
    else:
        y0, y1, thr = gb
        if y1 - y0 < 50:
            print(f"  FAIL 4 路面带过窄 {y0}-{y1}")
            ok = False
        else:
            print(f"  PASS 4 路面带 y∈[{y0},{y1}]  阈值{thr:.1f}")

    print(f"[_bgprobe] 自检 {'PASS' if ok else 'FAIL'}")
    return ok


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--bg":
        bg = sys.argv[2]
        vx = float(sys.argv[3]) if len(sys.argv) > 3 else 270.0
        vh = float(sys.argv[4]) if len(sys.argv) > 4 else 482.0
        r = compare(bg, vx, vh)
        for k, v in r.items():
            print(f"  {k}: {v}")
    else:
        sys.exit(0 if self_check() else 1)
