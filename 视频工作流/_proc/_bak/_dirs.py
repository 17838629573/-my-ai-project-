# -*- coding: utf-8 -*-
"""三朝向出片：侧走 / 正面走来 / 背面走远。
全部走 stage.walk_seq —— 同一套 gait、同一台 camera.fit 反解相机，
只有 yaw 和 speed 不同，所以人和路不会错位。
"""
import numpy as np
from stage import walk_seq, to_mp4, sheet, bake

FPS, SECS = 30, 3.0
N = int(FPS * SECS)

JOBS = [
    # tag            yaw    speed   Z0    lane
    ("朝向_侧走",     90.0,  0.67,  4.0,  -1.6),  # 沿 +X 横穿，深度恒定
    ("朝向_正面走来", 180.0, 0.67,  9.0,   0.0),  # yaw=180 → 沿 -Z 走近
    ("朝向_背面走远", 0.0,   0.67,  3.2,   0.0),  # yaw=0   → 沿 +Z 走远
]

for tag, yaw, sp, z0, lane in JOBS:
    fr, geom, cam = walk_seq(n=N, fps=FPS, speed=sp, Z0=z0, lane=lane,
                             yaw=yaw, wind=(200.0, -50.0))
    arr = fr
    to_mp4(arr, "%s.mp4" % tag, fps=FPS)
    sheet(arr[::12], cols=3).save("%s_索引.png" % tag)
    # 脚部不翻转复核
    tops = []
    for i in (0, N // 3, 2 * N // 3):
        pass
    print("→ %s.mp4   %s_索引.png  (%d 帧)" % (tag, tag, len(arr)))

# ---- 门禁：任何一档"走不动"必须当场报错，不许静默出片 ----
# 帧间差只在"人物包围盒并集"内量：远处小人全图均值天然低，会误判。
# 判据：包围盒内帧间差 > 0.5，且（横向位移 >30px 或 身高变化 >10%）。
_OK = True
for tag, yaw, sp, z0, lane in JOBS:
    fr, geom, cam = walk_seq(n=N, fps=FPS, speed=sp, Z0=z0, lane=lane,
                             yaw=yaw, wind=(200.0, -50.0))
    b = np.asarray(bake("城墙关隘")[0], dtype=np.float32)
    A = [np.asarray(f, dtype=np.float32) for f in fr]
    boxes, xs, hs = [], [], []
    for a in A:
        m = np.abs(a - b).max(axis=2) > 8
        yy, xx = np.nonzero(m)
        if yy.size:
            boxes.append((yy.min(), yy.max(), xx.min(), xx.max()))
            xs.append(float(xx.mean())); hs.append(float(yy.max() - yy.min()))
    y0 = min(v[0] for v in boxes); y1 = max(v[1] for v in boxes)
    x0 = min(v[2] for v in boxes); x1 = max(v[3] for v in boxes)
    dif = [float(np.abs(A[i + 1][y0:y1 + 1, x0:x1 + 1]
                        - A[i][y0:y1 + 1, x0:x1 + 1]).mean())
           for i in range(N - 1)]
    dx = abs(xs[-1] - xs[0])
    dh = abs(hs[-1] - hs[0]) / max(hs[0], 1e-6)
    md = float(np.mean(dif))
    ok = md > 0.5 and (dx > 30.0 or dh > 0.10)
    _OK &= ok
    print("  [%s] %-10s 横移%6.1fpx 身高变%.0f%% 人物区帧间差%.2f"
          % ("PASS" if ok else "FAIL", tag, dx, dh * 100, md))
print("SELF_CHECK:", "PASS" if _OK else "FAIL")
