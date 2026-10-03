#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""骨架_行走 —— 侧面行走骨架图集（pose.py 驱动）

契约: contracts/gait_sheet.md
依赖: pose
被依赖: build_video
改前必读: IMPROVE_pose.md
"""
from __future__ import annotations
import os, math, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pose

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(HERE, "_骨架")

# ---- 物性：Winter 1990 / Drillis & Contini 1966（搜证值，非手填）----
ANTHRO = {"trunk": 0.288, "head": 0.130, "neck": 0.052, "upperarm": 0.186,
          "lowerarm": 0.146, "hand": 0.108, "thigh": 0.245, "shank": 0.246,
          "shoulder_half": 0.1295, "hip_half": 0.095}
FACE = {"eye_back": 0.15, "ear_back": 0.35, "face_side": 0.30}
POSE_STAND = {"a_trunk": 90, "a_head": 90, "a_shoulder_l": 180, "a_shoulder_r": 0,
              "a_upperarm_l": -90, "a_upperarm_r": -90, "a_forearm_l": -90,
              "a_forearm_r": -90, "a_hip_l": 180, "a_hip_r": 0,
              "a_thigh_l": -90, "a_thigh_r": -90, "a_shank_l": -90, "a_shank_r": -90}
# 步态：cadence = 120/cycle，步行区间 100–120 步/分
GAIT = {"speed_m_s": 1.5, "cycle_s": 1.0, "stride_m": 1.5, "stance_ratio": 0.60,
        "swing_height_m": 0.10, "ankle_y_m": 0.039 * 1.70}

N_FRAME = 30         # 完整周期帧数（铁律75修订：侧视禁镜像复用）
CELL = 256
GRID = (5, 6)        # 5列6行 = 30 格


def solve_frame(spec, t):
    """返回【相对身体坐标】：减去整体平移 speed*t（pivot 锁定，人物不漂移）。"""
    r = pose.solve(spec, "walk", t)
    shift = spec["gait"]["speed_m_s"] * t
    rel = {n: (x - shift, y) for n, (x, y) in r["joints"].items()}
    return rel, r["meta"]


def auto_fit(all_pts, cell, pad=0.10):
    """所有帧共用一套缩放/平移，保证人物不漂移、完整落格（铁律40/47）。"""
    xs = [p[0] for f in all_pts for p in f.values()]
    ys = [p[1] for f in all_pts for p in f.values()]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = max(1e-6, x1 - x0), max(1e-6, y1 - y0)
    usable = cell * (1 - 2 * pad)
    s = min(usable / w, usable / h)
    ox = (cell - w * s) / 2 - x0 * s
    oy = (cell - h * s) / 2 - y0 * s
    return s, ox, oy


def draw_one(joints, s, ox, oy, cell):
    img = np.full((cell, cell, 3), 255, np.uint8)
    idx = {n: i for i, n in enumerate(pose.NAMES)}
    P = {}
    for n, (x, y) in joints.items():
        P[n] = (ox + x * s, cell - (oy + y * s))   # y 翻转：米制向上 -> 图像向下
    # 地面线
    gy = int(round(cell - oy))
    cv2.line(img, (6, gy), (cell - 6, gy), (200, 200, 200), 1)
    # 骨
    for a, b in pose.BONES:
        na, nb = pose.NAMES[a], pose.NAMES[b]
        if na in P and nb in P:
            cv2.line(img, (int(P[na][0]), int(P[na][1])), (int(P[nb][0]), int(P[nb][1])),
                     (30, 30, 30), 2, cv2.LINE_AA)
    # 关节
    for n, (px, py) in P.items():
        cv2.circle(img, (int(px), int(py)), 3, (0, 0, 200), -1)
    # 头
    if "nose" in P:
        cv2.circle(img, (int(P["nose"][0]), int(P["nose"][1])), 9, (0, 0, 0), 2)
    # 朝向箭头（+x = 前进方向）
    cv2.arrowedLine(img, (cell - 40, 18), (cell - 12, 18), (0, 140, 0), 2, tipLength=0.6)
    return img


def build_sheet():
    spec = {"height_m": 1.70, "anthro": ANTHRO, "face": FACE,
            "poses": {"stand": POSE_STAND}, "gait": GAIT}
    cycle = GAIT["cycle_s"]
    ts = [cycle * i / N_FRAME for i in range(N_FRAME)]        # 完整周期，等相位
    frames, metas = [], []
    for t in ts:
        j, m = solve_frame(spec, t)
        frames.append(j)
        metas.append(m)
    s, ox, oy = auto_fit(frames, CELL)
    cols, rows = GRID
    W, H = cols * CELL, rows * CELL
    sheet = np.full((H, W, 3), 255, np.uint8)
    for i, j in enumerate(frames):
        c = draw_one(j, s, ox, oy, CELL)
        r, cc = divmod(i, cols)
        sheet[r * CELL:(r + 1) * CELL, cc * CELL:(cc + 1) * CELL] = c
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "行走_侧视_30帧.png")
    cv2.imwrite(path, sheet)
    return path, frames, metas, (s, ox, oy)


def self_check(frames, metas, fit):
    ok = []
    # 1 支撑期脚世界坐标恒定（铁律74）
    drift = 0.0
    for i in range(len(frames) - 1):
        for side in ("l", "r"):
            if metas[i].get(f"{side}_phase") == "stance" and \
               metas[i + 1].get(f"{side}_phase") == "stance":
                a = metas[i][f"{side}_target"]
                b = metas[i + 1][f"{side}_target"]
                drift = max(drift, abs(a[0] - b[0]))
    ok.append(("1 支撑脚零滑移", drift < 1e-9, f"drift={drift:.2e}m"))
    # 2 双支撑存在（连续性）
    dual = sum(1 for m in metas if m.get("l_phase") == "stance" and m.get("r_phase") == "stance")
    ok.append(("2 双支撑帧存在", dual > 0, f"{dual}/{len(metas)}帧"))
    # 3 脚不穿地
    low = min(min(p[1] for p in f.values()) for f in frames)
    ok.append(("3 脚不穿地", low >= -1e-6, f"min_y={low:.4f}m"))
    # 4 完整落格
    s, ox, oy = fit
    xs = [p[0] for f in frames for p in f.values()]
    ys = [p[1] for f in frames for p in f.values()]
    px = [ox + x * s for x in xs]
    py = [CELL - (oy + y * s) for y in ys]
    ok.append(("4 完整落格", min(px) >= 0 and max(px) <= CELL and min(py) >= 0 and max(py) <= CELL,
               f"x[{min(px):.0f},{max(px):.0f}] y[{min(py):.0f},{max(py):.0f}]"))
    # 5 步态参数业界区间
    cad = 120 / GAIT["cycle_s"]
    ok.append(("5 cadence 步行区间", 100 <= cad <= 120, f"{cad:.0f}步/分"))
    ok.append(("6 speed=stride/cycle", abs(GAIT["speed_m_s"] - GAIT["stride_m"] / GAIT["cycle_s"]) < 1e-9, ""))
    # 7 摆动期足端离地
    sw = [m[f"{sd}_target"][1] for m in metas for sd in ("l", "r") if m.get(f"{sd}_phase") == "swing"]
    ok.append(("7 摆动期足端离地", len(sw) > 0 and max(sw) > GAIT["ankle_y_m"] + 1e-3,
               f"max={max(sw) if sw else 0:.3f}m"))
    # 8 循环闭合：t=0 与 t=cycle 必须同一姿态（否则循环播放跳变）
    spec = {"height_m": 1.70, "anthro": ANTHRO, "face": FACE,
            "poses": {"stand": POSE_STAND}, "gait": GAIT}
    j_end, _ = solve_frame(spec, GAIT["cycle_s"])
    close = max(math.dist(frames[0][n], j_end[n]) for n in pose.NAMES)
    ok.append(("8 循环闭合", close < 1e-9, f"首末差={close:.2e}m"))
    # 9 左右腿交替：两脚相位不得长期相同（否则同手同脚）
    alt = sum(1 for m in metas if m.get("l_phase") != m.get("r_phase"))
    ok.append(("9 左右腿交替", alt > len(metas) * 0.5, f"{alt}/{len(metas)}帧异相"))
    # 10 侧视禁用水平镜像（铁律75修订）：镜像残差必须【大】，否则说明是伪侧视
    mir = 0.0
    for j in frames:
        mir = max(mir, abs(j["l_ankle"][0] - j["r_ankle"][0]))
    ok.append(("10 确为侧视(两腿分离)", mir > 0.05, f"踝间距max={mir:.3f}m"))
    for n, good, info in ok:
        print(("PASS" if good else "FAIL") + f" {n}  {info}")
    return all(g for _, g, _ in ok)


if __name__ == "__main__":
    path, frames, metas, fit = build_sheet()
    print(f"图集: {path}  {len(frames)}帧")
    good = self_check(frames, metas, fit)
    print("-> " + ("PASS" if good else "FAIL"))
    sys.exit(0 if good else 1)
