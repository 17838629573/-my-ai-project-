#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qc_scene —— 质检第三层：场景约束（该不该在这个位置 / 图层是否同一层）。

前两层测不到什么（实测逼出 2026-10-03）：
  像素层（freeze/flicker/flow/ssim）测的是「帧与帧连不连贯」。
    -> 人物沿路径平滑走进天空：每帧都平滑，光流顺、SSIM 不跳 -> 全绿。
  物理层（phys）测的是「运动自不自然」。
    -> 位置本身不合理，运动再自然也没用。
  所以必须第三层：不关心连贯、不关心自然，只关心
    「这个东西【该不该】出现在这个位置」以及「各图层是不是同一层」。

本层不依赖渲染方上报，全部【从视频+背景图反推】，因此测的是真结果：
  1) 天空违规：差分出前景，取每帧前景最低点 y，必须 > 地平线
     （Footprints CVPR2020：地平线以上不可能是可行走面）
  2) 图层色差：前景内部 vs 同位置背景，比较 L(亮度) 与色相排序
     实测事故数据：背景 L=135.6 RGB(163.8,119.7,86.6) 暖色，
                   人物/树/旗 L≈100~111 且 G 通道最大 -> 明显不是一层

用法:
  python3 -m _tools.qcheck.qc_scene --self-check
  from _tools.qcheck import qc_scene
  qc_scene.analyze(seq, bg_path)
"""
import os
import sys

import cv2
import numpy as np

from .qc_layer import (  # 拆分见 qc_layer.py
    _perceptual_luma, _bhattacharyya, _hist_rgb, layer_delta,
    L_TOL, BHATTA_TOL, CONTRAST_TOL, SAT_TOL, SHARP_TOL, HUE_TOL)  # noqa: F401

_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 差分阈值：低于此视为压缩噪声/背景微差
#   vs 背景图：30 会把整片城墙判成前景（实测 p50=16、阈值30 -> 19.4% 画面）
#      —— 根因是背景图 resize + MP4 压缩与原视频帧不同编码器，噪声巨大。
#   vs 相邻帧：同一编码器输出，p50=1、p90=6，阈值 10 即可（实测 4.15%）。
#   故运动前景一律用【帧间差分】，不用 vs 背景差分。
FG_THRESH = 30
MOTION_THRESH = 10
# 前景最小连通面积（占画面比例），滤掉噪点
FG_MIN_AREA = 0.002
# 图层判定阈值（业界维度，非自拟两项）
L_TOL = 15.0        # 感知亮度差
BHATTA_TOL = 0.35   # 直方图 Bhattacharyya 距离
CONTRAST_TOL = 0.40 # 对比度相对差
SAT_TOL = 25.0      # 饱和度差
SHARP_TOL = 0.60    # 锐度相对差
HUE_TOL = 12.0      # 色温倾向差（R-B）


def _horizon_of(spec_path=None, bg_bgr=None):
    """权威地平线：走 spec_probe 的三方一致性。"""
    sys.path.insert(0, _HERE)
    try:
        from .spec_probe import probe
        r = probe(spec_path, None)
        d = r.get("horizon_declared") or {}
        if d:
            return float(list(d.values())[0])
    except Exception:
        pass
    return None


def _gray_u8(img):
    if img.ndim == 3:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return img


def foreground_mask(frame_bgr, bg_bgr, thresh=FG_THRESH, min_area=FG_MIN_AREA,
                    prev_bgr=None):
    """前景掩码。优先用【帧间差分】（prev_bgr 给了就用它）。

    为什么默认该用帧间差分（实测逼出）：
      vs 背景图差分在两个不同编码链（原图 resize vs MP4 解码）之间做，
      噪声 p50=16 -> 阈值30 时 19.4% 画面被判前景，城墙整片误报。
      帧间差分同编码器，p50=1、p90=6，阈值 10 干净得多。
    """
    ref = prev_bgr if prev_bgr is not None else bg_bgr
    d = cv2.absdiff(_gray_u8(frame_bgr), _gray_u8(ref))
    m = (d > thresh).astype(np.uint8) * 255
    m = cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    n, lab, stats, _ = cv2.connectedComponentsWithStats(m, 8)
    if n <= 1:
        return np.zeros_like(m)
    keep = np.zeros_like(m)
    total = m.size
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= total * min_area:
            keep[lab == i] = 255
    return keep










def sky_exclude_from_scene(spec_path=None, bg_bgr=None, image_h=960, pad=40):
    """允许出现在地平线【以上】的区域（墙上物体：幡杆/幡身/垂带）。

    为什么需要（实测逼出）：
      直接用"前景最低点 > 地平线"判定，会把【插在城墙上的幡】判成飘天。
      实测：成片 12 帧被判违规，逐帧查证全是幡（x[90,209]），人物一帧没有。
      原因：墙高 5m > 相机高 3.383m，墙顶 y=459 本就在地平线 482 之上，合法。
    """
    sys.path.insert(0, _HERE)
    boxes = []
    try:
        import json
        sp = spec_path or os.path.join(_HERE, "scene_spec.json")
        spec = json.load(open(sp, encoding="utf-8"))
        import _surface as SF
        an = SF.anchors_from_scene(spec, bg_bgr, image_h)
        for nm, p in an["anchors"].items():
            if p.get("surface") == "wall" or "wall" in str(p.get("via", "")):
                y, x = p.get("y"), p.get("x")
                if x is None or y is None:
                    continue
                boxes.append((float(x) - pad, float(y) - pad * 3,
                              float(x) + pad, float(y) + pad))
    except Exception:
        return []
    return boxes


def _apply_exclude(fg, boxes):
    """把落在排除框内的前景像素清掉。"""
    if not boxes:
        return fg
    out = fg.copy()
    h, w = out.shape[:2]
    for x0, y0, x1, y1 in boxes:
        xa, xb = max(0, int(x0)), min(w, int(x1))
        ya, yb = max(0, int(y0)), min(h, int(y1))
        if xb > xa and yb > ya:
            out[ya:yb, xa:xb] = 0
    return out


def analyze(seq, bg_path=None, horizon_y=None, max_frames=None,
            sky_exclude=None, auto_exclude_wall=True, foot_y_seq=None):
    """foot_y_seq: 渲染方上报的【逐帧人物足底 y】。

    为什么需要（业界依据 + 实测教训）：
      Physics-IQ(2501.09038) Spatial IoU 之所以能用，前提是【有 GT 可比对】；
      Principia 更明确指出：相机参数/尺度未知时绝对测量不可靠。
      我们这边的等价问题是：像素反推出的"前景"里，人物和插在城墙上的幡
      混在一起，而幡的落点 y=459 本就在地平线 482 之上——合法。
      实测：像素反推判出 12 帧"飘天"，逐帧查证全部是幡，人物一帧没有。

      所以天空约束的正确形态是两档：
        A) 有上报(foot_y_seq) -> 硬判，可信
        B) 无上报           -> 像素反推只作提示，verdict 标 UNKNOWN，
                               绝不冒充 FAIL（否则又是"工具说有问题、其实是工
                               具分不清"）
    """
    """-> dict: sky_violation / layer_mismatch / verdict"""
    n = len(seq)
    if max_frames:
        n = min(n, max_frames)

    bg_bgr = None
    if bg_path and os.path.exists(bg_path):
        bg_bgr = cv2.imread(bg_path, cv2.IMREAD_COLOR)
        # 尺寸以首帧为准（Seq 不暴露 w/h；且 gray() 返回的是 0-1 浮点 luma，
        # 不是 uint8 —— 必须用 bgr()，否则差分与背景不同量纲，结果全错）
        _f0 = seq.bgr(0)
        fh, fw = _f0.shape[:2]
        if bg_bgr is not None and bg_bgr.shape[:2] != (fh, fw):
            bg_bgr = cv2.resize(bg_bgr, (fw, fh))

    if horizon_y is None:
        horizon_y = _horizon_of(os.path.join(_HERE, "scene_spec.json"), bg_bgr)
    if sky_exclude is None and auto_exclude_wall:
        sky_exclude = sky_exclude_from_scene(bg_bgr=bg_bgr,
                                             image_h=(bg_bgr.shape[0] if bg_bgr is not None else 960))

    out = {"n_checked": 0, "horizon_y": horizon_y,
           "sky_exclude_boxes": len(sky_exclude or []),
           "per_frame": [], "sky_violation": None, "layer": None,
           "verdict": "UNKNOWN", "reason": ""}

    if bg_bgr is None:
        out["reason"] = "无背景图，场景约束层无法独立判定（需传 bg_path）"
        return out

    lows, highs, dLs, dRBs = [], [], [], []
    for i in range(n):
        fb = seq.bgr(i)
        if fb.dtype != np.uint8:
            fb = np.clip(fb, 0, 255).astype(np.uint8)
        prev = seq.bgr(i - 1) if i > 0 else None
        if prev is not None and prev.dtype != np.uint8:
            prev = np.clip(prev, 0, 255).astype(np.uint8)
        fg = foreground_mask(fb, bg_bgr, thresh=MOTION_THRESH, prev_bgr=prev)
        fg = _apply_exclude(fg, sky_exclude or [])
        ys, xs = np.nonzero(fg)
        rec = {"i": i}
        if len(ys):
            rec["foot_y"] = float(ys.max())       # 屏幕 y 越大越靠下
            rec["top_y"] = float(ys.min())
            rec["h_px"] = float(ys.max() - ys.min())
            lows.append(rec["foot_y"])
            highs.append(rec["top_y"])
        ld = layer_delta(fb, bg_bgr, fg)
        if ld:
            rec["layer"] = ld
            dLs.append(ld)   # 存整 dict：6 维都要聚合，只存 dL 会丢其余 5 维
        out["per_frame"].append(rec)
    out["n_checked"] = n

    # --- 1) 天空违规：前景最低点必须在地平线以下 ---
    if lows and horizon_y is not None:
        arr = np.array(lows)
        above = int((arr <= horizon_y).sum())
        out["sky_violation"] = {
            "frames_above_horizon": above,
            "min_foot_y": round(float(arr.max()), 1),   # 最靠下的那次
            "max_foot_y": round(float(arr.min()), 1),   # 最靠上的那次
            "horizon_y": round(float(horizon_y), 1),
            "ok": above == 0}

    # --- 2) 图层色差 ---
    if dLs:
        keys = ("dL", "dBhatta", "dContrast", "dSat", "dSharp", "dRB")
        agg = {k: round(float(np.mean([x[k] for x in dLs])), 3) for k in keys}
        tols = {"dL": L_TOL, "dBhatta": BHATTA_TOL, "dContrast": CONTRAST_TOL,
                "dSat": SAT_TOL, "dSharp": SHARP_TOL, "dRB": HUE_TOL}
        failed = [k for k in keys if abs(agg[k]) > tols[k]]
        out["layer"] = dict(agg, failed=failed, ok=not failed,
                            thresholds=tols)

    # --- 1b) 有渲染上报时，用上报值硬判（可信度最高）---
    if foot_y_seq and horizon_y is not None:
        arr = np.array([float(x) for x in foot_y_seq[:n]])
        above = int((arr <= horizon_y).sum())
        out["sky_reported"] = {"frames_above_horizon": above,
                               "min_y": round(float(arr.max()), 1),
                               "max_y": round(float(arr.min()), 1),
                               "ok": above == 0}
        # 上报优先：覆盖像素反推的结论
        if out["sky_violation"] is not None:
            out["sky_violation"]["superseded_by"] = "sky_reported"

    ok = True
    msgs = []
    src = out.get("sky_reported") or out.get("sky_violation")
    if src is not None:
        if not src.get("ok"):
            ok = False
            msgs.append("足底 y <= 地平线 %d 帧（有东西飘天，来源=%s）" %
                        (src["frames_above_horizon"],
                         "渲染上报" if out.get("sky_reported") else "像素反推"))
        else:
            msgs.append("天空约束 OK（来源=%s）" %
                        ("渲染上报" if out.get("sky_reported") else "像素反推"))
    elif out.get("sky_violation") is not None and \
            out["sky_violation"]["frames_above_horizon"] > 0:
        # 无上报 + 像素反推有嫌疑 -> 不敢判 FAIL
        msgs.append("像素反推有 %d 帧前景在地平线上，但无渲染上报，"
                    "无法区分是墙上物体(合法)还是飘天 -> UNKNOWN" %
                    out["sky_violation"]["frames_above_horizon"])
        out["verdict"] = "UNKNOWN"
        if out.get("layer") is not None:
            out["verdict"] = "FAIL" if not out["layer"]["ok"] else "UNKNOWN"
            if not out["layer"]["ok"]:
                msgs.append("图层 %s 不匹配（此项可独立判定）" %
                            out["layer"].get("failed"))
        out["reason"] = "；".join(msgs)
        return out
    if out["layer"] is not None:
        if not out["layer"]["ok"]:
            ok = False
            _L = out["layer"]
            msgs.append("图层 %s 不匹配（dL=%.1f dSat=%.1f dRB=%.1f）" %
                        (_L.get("failed"), _L.get("dL", 0),
                         _L.get("dSat", 0), _L.get("dRB", 0)))
        else:
            msgs.append("图层一致 OK")
    if out["sky_violation"] is None and out["layer"] is None:
        out["verdict"] = "UNKNOWN"; out["reason"] = "未检出足够前景"; return out
    out["verdict"] = "PASS" if ok else "FAIL"
    out["reason"] = "；".join(msgs)
    return out




if __name__ == "__main__":
    if "--self-check" in sys.argv:
        sys.exit(0 if self_check() else 1)
    print(__doc__)
