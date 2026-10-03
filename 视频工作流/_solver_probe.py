#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
探针与容纳性校验：先 8 格验一致性再升级（铁律48）。

契约: contracts/solver_split.md
改前必读: IMPROVE_solver_split.md
"""

import cv2
import numpy as np
from _solver_base import CONTAINMENT, PROBE_MAX, _grid_for




def _cell_policy(spec_or_pol):
    """取质心策略：缺声明即报错（铁律31）。"""
    pol = spec_or_pol
    if isinstance(pol, dict):
        pol = (pol.get("containment") or {}).get("centroid_policy") \
            or pol.get("centroid_policy")
    if pol not in ("planted", "free"):
        raise ValueError(
            "缺 centroid_policy（必填 planted|free）："
            "质心动不动是语义判断，代码不猜（铁律18/31）")
    return pol




def _conf(key):
    return CONTAINMENT[key]




def containment_check(cell_bgra, cw, ch, policy=None, conf=None):
    """单格容纳性校验（铁律47）。

    cell_bgra: 单格图像（BGR 或 BGRA），背景为纯色键控底。
    返回 (ok, detail)。任一子项 FAIL 即整体 FAIL，不静默。
    """
    c = dict(CONTAINMENT)
    c.update(conf or {})
    pol = _cell_policy(policy if policy is not None else c.get("centroid_policy"))
    img = cell_bgra
    if img.ndim == 2:
        fg = img > 0
    else:
        bgr = img[:, :, :3].astype(np.int16)
        # 键控色 = 四角众数（chroma.py 同法），不假定 #FF00FF
        corners = np.vstack([bgr[0, 0], bgr[0, -1], bgr[-1, 0], bgr[-1, -1]])
        key = np.median(corners, axis=0)
        dist = np.abs(bgr - key).sum(axis=2)
        fg = dist > 90
    ys, xs = np.nonzero(fg)
    det = {"policy": pol}
    if len(xs) == 0:
        det["reason"] = "格内无前景"
        return False, det
    x0, x1, y0, y1 = int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max())
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    det.update({"bbox": (x0, y0, bw, bh),
                "fill_w": round(bw / float(cw), 3),
                "fill_h": round(bh / float(ch), 3),
                "fill_area": round((bw * bh) / float(cw * ch), 3),
                "margin": (x0, y0, cw - 1 - x1, ch - 1 - y1)})
    ok = True
    ok &= bw <= cw * c["max_fill_w"] + 0.5
    ok &= bh <= ch * c["max_fill_h"] + 0.5
    ok &= (bw * bh) >= cw * ch * c["min_fill"] - 0.5
    ok &= min(x0, y0, cw - 1 - x1, ch - 1 - y1) >= c["margin_px"]
    det["centroid"] = (round(float(xs.mean()), 1), round(float(ys.mean()), 1))
    det["ok"] = bool(ok)
    return bool(ok), det




def probe_plan(ans, probe_max=PROBE_MAX):
    """【铁律48】探针计划：先出 min(probe_max, N) 格验一致性，通过才升级。"""
    n = int(ans["mat_frames"])
    n_probe = int(min(probe_max, n))
    rows, cols = _grid_for(n_probe)
    full_r, full_c = _grid_for(n)
    return {"n_probe": n_probe,
            "n_full": n,
            "probe_grid": [rows, cols],
            "full_grid": [full_r, full_c],
            "phase_map": [round(360.0 * i / n_probe, 2) for i in range(n_probe)],
            "order": "行优先，第 i 格 = 相位 phase_map[i] 度",
            "rule": "探针 4 项一致性全部通过，才允许按 n_full 出全量图集"}




def probe_check(sheet_path, cols, rows, n, policy=None, conf=None):
    """【铁律48】探针一致性 4 项（对应业界"脸/衣服/配色/比例"）。

    面积一致性 / 尺度一致性 / 配色一致性 / 足迹一致性（仅 planted）。
    """
    c = dict(CONTAINMENT)
    c.update(conf or {})
    pol = _cell_policy(policy if policy is not None else c.get("centroid_policy"))
    img0 = cv2.imread(sheet_path, cv2.IMREAD_UNCHANGED)
    if img0 is None:
        raise IOError("读不到图集: %s" % sheet_path)
    if img0.ndim == 2:
        img0 = cv2.cvtColor(img0, cv2.COLOR_GRAY2BGRA)
    if img0.shape[2] == 3:
        img0 = cv2.cvtColor(img0, cv2.COLOR_BGR2BGRA)
    H, W = img0.shape[:2]
    cw, ch = W // cols, H // rows
    bgr = img0[:, :, :3].astype(np.int16)
    corners = np.vstack([bgr[0, 0], bgr[0, -1], bgr[-1, 0], bgr[-1, -1]])
    key = np.median(corners, axis=0)
    fg = np.abs(bgr - key).sum(axis=2) > 90

    areas, bws, bhs, cols_, cents, conts = [], [], [], [], [], []
    for i in range(n):
        r, cc = divmod(i, cols)
        sub = img0[r * ch:(r + 1) * ch, cc * cw:(cc + 1) * cw]
        m = fg[r * ch:(r + 1) * ch, cc * cw:(cc + 1) * cw]
        okc, det = containment_check(sub, cw, ch, pol, conf)
        conts.append(okc)
        if len(det.get("bbox", ())) == 4:
            _, _, bw, bh = det["bbox"]
            areas.append(bw * bh)
            bws.append(bw)
            bhs.append(bh)
            cents.append(det["centroid"])
            sel = img0[:, :, :3][r * ch:(r + 1) * ch, cc * cw:(cc + 1) * cw][m]
            cols_.append(sel.mean(axis=0) if len(sel) else np.zeros(3))

    def spread(v):
        v = np.asarray(v, dtype=float)
        return float((v.max() - v.min()) / v.mean()) if v.mean() > 1e-9 else float("inf")

    det = {"n": n, "policy": pol,
           "containment_all_pass": bool(all(conts)),
           "containment_fail_idx": [i for i, o in enumerate(conts) if not o],
           "area_spread": round(spread(areas), 3),
           "scale_spread": round(max(spread(bws), spread(bhs)), 3)}
    cmax = 0.0
    for i in range(len(cols_)):
        for j in range(i + 1, len(cols_)):
            cmax = max(cmax, float(np.linalg.norm(cols_[i] - cols_[j])))
    det["color_maxdist"] = round(cmax, 2)
    if cents:
        cx = np.asarray([p[0] for p in cents])
        cy = np.asarray([p[1] for p in cents])
        det["centroid_drift"] = round(
            max(float(cx.max() - cx.min()) / cw, float(cy.max() - cy.min()) / ch), 3)
    ok = det["containment_all_pass"]
    c = dict(CONTAINMENT, **(conf or {}))
    ok &= det["area_spread"] <= c["area_spread"]
    ok &= det["scale_spread"] <= c["scale_spread"]
    ok &= det["color_maxdist"] <= c["color_maxdist"]
    if pol == "planted":
        ok &= det.get("centroid_drift", 9.9) <= c["centroid_max"]
    det["ok"] = bool(ok)
    return bool(ok), det
