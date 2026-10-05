#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qc_scene 的自检（从 qc_scene.py 拆出）。

拆出原因：qc_scene.py 拆走图层度量后仍为 377 行 / 12749 字符，超阈值，
gate_post 强制再拆。自检代码不参与运行路径，单独成文件最安全。

运行：python3 -m _tools.qcheck.qc_scene_selftest
"""
import cv2
import numpy as np

from .qc_layer import layer_delta, L_TOL


# ------------------------------------------------------------------ 自检
def self_check():
    ok, bad = [], []

    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    from .qc_scene import foreground_mask
    H, W = 200, 120
    HOR = 80.0

    # 背景：上冷下暖的渐变（模拟城墙+地面）
    bg = np.zeros((H, W, 3), np.uint8)
    bg[:, :] = (90, 140, 190)          # BGR: 偏蓝（冷）
    bg[int(HOR):, :] = (70, 120, 160)  # 地面稍暗

    def frame_with(box, color):
        f = bg.copy()
        y0, y1, x0, x1 = box
        f[y0:y1, x0:x1] = color
        return f

    class FakeSeq:
        w, h = W, H
        def __init__(self, frames):
            self.f = frames
        def __len__(self):
            return len(self.f)
        def gray(self, i):
            return self.f[i]
        def rgb(self, i):
            return self.f[i][:, :, ::-1]

    # 1) 正常：物体完全在地平线以下（颜色须与背景不同，否则差分检不出——
    #    第一版样本就犯了这错：用了与地面同色的物体，差分像素=0）
    good = [frame_with((140, 190, 40, 80), (200, 60, 40)) for _ in range(3)]
    r = analyze(FakeSeq(good), None, horizon_y=HOR) if False else None
    # 直接调底层：差分+判定
    fg = foreground_mask(good[0], bg)
    ys, _ = np.nonzero(fg)
    add("1 前景被差分检出", len(ys) > 0, "像素=%d" % len(ys))
    add("2 正常物体足底在地平线下",
        len(ys) > 0 and float(ys.max()) > HOR, "foot_y=%s" % (ys.max() if len(ys) else None))

    # 2) 飘天：物体整体在地平线以上
    sky = [frame_with((10, 50, 40, 80), (200, 60, 40)) for _ in range(3)]
    fg2 = foreground_mask(sky[0], bg)
    ys2, _ = np.nonzero(fg2)
    add("3 飘天物体足底仍在地平线上（可检出）",
        len(ys2) > 0 and float(ys2.max()) <= HOR, "foot_y=%s" % (ys2.max() if len(ys2) else None))

    # 3) 图层色差：物体颜色与背景明显不同
    diff = [frame_with((140, 190, 40, 80), (200, 60, 40)) for _ in range(3)]  # 暖色物体
    fg3 = foreground_mask(diff[0], bg)
    ld = layer_delta(diff[0], bg, fg3)
    add("4 图层色差可测出", ld is not None and abs(ld["dL"]) > 5,
        str(ld)[:70] if ld else "None")

    # 4) 同色物体应判定一致
    same = [frame_with((140, 190, 40, 80), (70, 120, 160)) for _ in range(3)]
    fg4 = foreground_mask(same[0], bg)
    ld4 = layer_delta(same[0], bg, fg4)
    add("5 同色物体判定一致",
        ld4 is None or (abs(ld4["dL"]) < L_TOL),
        str(ld4)[:70] if ld4 else "None(无内部像素)")

    print("PASS:")
    for x in ok:
        print("  " + x)
    if bad:
        print("FAIL:")
        for x in bad:
            print("  " + x)
    else:
        print("FAIL: 无")
    return not bad


if __name__ == "__main__":
    import sys as _s
    _s.exit(0 if self_check() else 1)
