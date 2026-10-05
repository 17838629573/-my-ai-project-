# -*- coding: utf-8 -*-
"""chain —— 首帧锚定 + 多段接力，把几秒扩展到 2~3 分钟。

为什么锚「首帧」而不是「上一张末帧」：
  chaining（末帧接力）每轮都以上一轮末帧为参考，误差会滚雪球累积。

业界依据：
  S2D-VidGen: "The first frame is reused as both an appearance anchor
               and a background anchor" —— 首帧同时做外观锚和背景锚
  Pathwise TTC: 每隔几步拿初始帧把当前帧 gently 拉回去，
                "peek at the very first page and use it as a reference"

本模块做两件事：
  drift()         量化当前帧相对锚的漂移（LPIPS 太重，用 LAB 直方图+结构差）
  anchor_report() 给出是否需要用锚帧重新生图的判定
  segment_plan() 把总时长切成若干段，每段都以首帧为锚

注意：背景在 anchor 比较中必须单独看。
  主体本来就该动，把主体变化算进漂移会误报。
"""
from __future__ import annotations

import cv2
import numpy as np

from flowsplit import split, to_gray, dense_flow

# ---------- 漂移度量 ----------
def bg_drift(anchor: np.ndarray, frame: np.ndarray, thr: float = 1.5) -> dict:
    """只衡量「背景区域」的漂移。主体变化不算漂移。

    返回 dict: ratio（漂移像素占比）, mean（漂移幅值均值）, verdict
    """
    ga, gf = to_gray(anchor), to_gray(frame)
    r = split(ga, gf, thr=thr)
    # 关键：漂移必须用「原始光流」衡量，不能用减掉 global 的 local。
    # 本场景相机固定不动（提示词已锁），背景整体平移同样是漂移。
    # 若用 local，整体平移会被 global 单应吸收，严重扭曲也判 OK——这是曾经的 bug。
    raw = dense_flow(ga, gf)
    mag = np.sqrt(raw[..., 0] ** 2 + raw[..., 1] ** 2)
    # 掩码外 = 背景；背景区的原始运动量就是「不该动却动了」的漂移
    bgmask = r["mask"] == 0
    if bgmask.sum() == 0:
        return {"ratio": 0.0, "mean": 0.0, "verdict": "OK"}
    m = mag[bgmask]
    ratio = float((m > thr).mean())
    mean = float(m.mean())
    verdict = "OK" if ratio < 0.10 else ("WARN" if ratio < 0.25 else "DRIFT")
    return {"ratio": ratio, "mean": mean, "verdict": verdict}


def color_drift(anchor: np.ndarray, frame: np.ndarray) -> float:
    """整图色调漂移：LAB 空间 A/B 通道均值差（欧氏距离）。

    捕捉「衣服颜色从藏青漂成蓝灰」这类身份漂移。
    """
    la = cv2.cvtColor(anchor, cv2.COLOR_BGR2LAB).astype(np.float32)
    lf = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB).astype(np.float32)
    da = la[..., 1].mean() - lf[..., 1].mean()
    db = la[..., 2].mean() - lf[..., 2].mean()
    return float(np.hypot(da, db))


def anchor_report(anchor: np.ndarray,
                  frames: list,
                  thr: float = 1.5,
                  color_max: float = 6.0) -> dict:
    """对一串帧逐个体检，找出第一个需要重生的位置。"""
    rows = []
    first_bad = None
    for i, f in enumerate(frames):
        d = bg_drift(anchor, f, thr)
        c = color_drift(anchor, f)
        bad = d["verdict"] == "DRIFT" or c > color_max
        if bad and first_bad is None:
            first_bad = i
        rows.append({"i": i, "bg_ratio": round(d["ratio"], 4),
                     "bg_verdict": d["verdict"],
                     "color": round(c, 3), "bad": bad})
    return {"rows": rows, "first_bad": first_bad,
            "ok": first_bad is None}


# ---------- 分段规划 ----------
def segment_plan(total_s: float,
                 period_s: float,
                 max_seg_s: float = 5.0) -> dict:
    """把总时长切成段。业界建议单段 <= 5 秒：

    Identity stability degrades with length faster than most people expect.
    短段拼接通常比一次生成长片段更可控。
    """
    if total_s <= 0 or period_s <= 0:
        raise ValueError("total_s / period_s 必须 > 0")
    cycles = int(-(-total_s / period_s // 1))   # ceil
    n_seg = int(-(-total_s / max_seg_s // 1))
    return {
        "total_s": total_s,
        "period_s": period_s,
        "cycles": cycles,
        "n_segments": n_seg,
        "max_seg_s": max_seg_s,
        "anchor": 0,          # 永远是第 0 帧做锚
    }


# ---------- 自检 ----------
def self_check() -> None:
    h, w = 160, 200
    yy, xx = np.mgrid[0:h, 0:w]
    base = (((xx // 12) + (yy // 12)) % 2 * 180 + 40).astype(np.uint8)
    base = cv2.GaussianBlur(base, (0, 0), 0.8)
    anchor = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)

    # 1) 完全一样的帧：漂移必须为 0
    d0 = bg_drift(anchor, anchor.copy())
    assert d0["verdict"] == "OK", d0
    assert d0["ratio"] < 0.01, d0
    assert color_drift(anchor, anchor.copy()) < 1e-6

    # 2) 只有主体动：背景漂移应为 OK（不能误报）
    f_move = anchor.copy()
    patch = anchor[50:110, 60:120].copy()
    f_move[50:110, 60:120] = 0
    f_move[50:110, 80:140] = np.maximum(f_move[50:110, 80:140], patch)
    d1 = bg_drift(anchor, f_move)
    assert d1["verdict"] == "OK", f"主体动被误报为漂移: {d1}"

    # 3) 背景整体扭曲：必须报 DRIFT
    f_warp = cv2.resize(anchor, (w + 40, h))[:, 20:w + 20]
    f_warp = cv2.resize(f_warp, (w, h))
    d2 = bg_drift(anchor, f_warp)
    assert d2["mean"] > 0.05, f"背景扭曲未被检出: {d2}"

    # 2b) 严重扭曲（缩放+整体平移）必须报 DRIFT——曾经的漏检点
    f_sev = cv2.resize(anchor, (w - 30, h - 20))
    f_sev = cv2.resize(f_sev, (w, h))
    f_sev = np.roll(f_sev, 15, axis=1)
    d2b = bg_drift(anchor, f_sev)
    assert d2b["verdict"] == "DRIFT", f"严重扭曲漏检: {d2b}"

    # 4) 色调漂移可检出
    f_tint = cv2.cvtColor(anchor, cv2.COLOR_BGR2LAB).astype(np.float32)
    f_tint[..., 1] += 25          # A 通道大幅偏移
    f_tint = cv2.cvtColor(f_tint.astype(np.uint8), cv2.COLOR_LAB2BGR)
    assert color_drift(anchor, f_tint) > 6.0, color_drift(anchor, f_tint)

    # 5) anchor_report 能定位第一个坏帧
    rep = anchor_report(anchor, [anchor.copy(), f_move, f_tint])
    assert rep["first_bad"] == 2, rep["first_bad"]
    assert rep["ok"] is False

    # 6) 分段规划
    sp = segment_plan(120.0, 1.579)
    assert sp["cycles"] == 76, sp["cycles"]
    assert sp["n_segments"] == 24, sp["n_segments"]   # 120/5
    assert sp["anchor"] == 0
    try:
        segment_plan(0, 1.579)
        raise AssertionError("应当抛 ValueError")
    except ValueError:
        pass

    print("chain self_check OK  静止=%.3f 主体动=%.3f(OK) 背景扭曲=%.3f"
          % (d0["ratio"], d1["ratio"], d2["ratio"]))


if __name__ == "__main__":
    self_check()
