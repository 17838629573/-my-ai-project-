#!/usr/bin/env python3
"""skeleton_runtime 自检（原 107 行 __main__ 块抽出）。
依赖: skeleton_runtime
被依赖: 无（自检入口）
改前必读: IMPROVE_skeleton_runtime.md
"""
import os
import numpy as np
import cv2
import math
from skeleton_runtime import Skeleton, apply_animation, mat_mul, mat_local, mat_apply, mat_inverse


def self_check():
    BASE = os.path.dirname(os.path.abspath(__file__))
    print("=" * 70)
    print("骨架求解器自检 —— 不依赖任何官方 runtime")
    print("=" * 70)

    # 1) 最小骨架：root -> hip -> torso -> head，加一条腿
    data = {
        "bones": [
            {"name": "root", "x": 270, "y": 800},
            {"name": "hip", "parent": "root", "x": 0, "y": 0, "rotation": 0},
            {"name": "torso", "parent": "hip", "x": 0, "y": 90, "rotation": 0},
            {"name": "head", "parent": "torso", "x": 0, "y": 80, "rotation": 0},
            {"name": "legL", "parent": "hip", "x": -18, "y": 0, "rotation": 0},
            {"name": "legR", "parent": "hip", "x": 18, "y": 0, "rotation": 0},
            {"name": "armL", "parent": "torso", "x": -35, "y": 60, "rotation": 0},
            {"name": "armR", "parent": "torso", "x": 35, "y": 60, "rotation": 0},
        ],
        # slot 顺序 = 绘制顺序：后面的画在上面
        "slots": [
            {"name": "legL", "bone": "legL"},      # 先画 = 在后
            {"name": "legR", "bone": "legR"},
            {"name": "armL", "bone": "armL"},      # 手臂盖躯干
            {"name": "armR", "bone": "armR"},
            {"name": "torso", "bone": "torso"},    # 躯干盖住腿根
            {"name": "head", "bone": "head"},      # 头在最上
        ],
        "skins": {"default": {
            "legL": {"legL": {"x": 0, "y": 40, "path": "legL"}},
            "legR": {"legR": {"x": 0, "y": 40, "path": "legR"}},
            "torso": {"torso": {"x": 0, "y": 45, "path": "torso"}},
            "head": {"head": {"x": 0, "y": 30, "path": "head"}},
            "armL": {"armL": {"x": 0, "y": 30, "path": "armL"}},
            "armR": {"armR": {"x": 0, "y": 30, "path": "armR"}},
        }},
    }

    # 2) 用代码生成部件图（不依赖任何外部文件）
    def part(w, h, color):
        im = np.zeros((h, w, 4), np.uint8)
        cv2.rectangle(im, (2, 2), (w - 3, h - 3), color, -1)
        im[:, :, 3] = 255
        return im

    parts = {
        "head": part(60, 60, (60, 90, 220)),      # BGR 橙
        "torso": part(80, 130, (40, 140, 60)),    # 绿
        "legL": part(34, 150, (200, 80, 40)),     # 蓝
        "legR": part(34, 150, (220, 60, 160)),    # 紫
        "armL": part(28, 120, (120, 180, 90)),   # 青
        "armR": part(28, 120, (90, 150, 200)),   # 黄
    }

    sk = Skeleton(data, img_loader=lambda p: parts.get(p))
    W, H = 540, 960

    # 3) FK 验证：计算各骨世界位置
    print("\n--- FK 世界坐标（正向运动学）---")
    for b in ["root", "hip", "torso", "head", "legL", "legR", "armL", "armR"]:
        M = sk.world_matrix(b)
        x, y = mat_apply(M, 0, 0)
        print(f"  {b:<7} -> ({x:7.1f}, {y:7.1f})")

    # 4) 关键验证：父骨旋转，子骨必须跟着走（层级生效）
    print("\n--- 层级验证：root 旋转 30 度，head 应该跟着动 ---")
    before = mat_apply(sk.world_matrix("head"), 0, 0)
    sk.pose["torso"] = {"rot": 30.0, "x": 0, "y": 0}
    after = mat_apply(sk.world_matrix("head"), 0, 0)
    d = math.hypot(after[0] - before[0], after[1] - before[1])
    print(f"  torso 旋转前 head = ({before[0]:.1f}, {before[1]:.1f})")
    print(f"  torso 旋转后 head = ({after[0]:.1f}, {after[1]:.1f})")
    print(f"  位移 = {d:.1f}px  -> {'PASS 层级生效' if d > 5 else 'FAIL 层级没生效'}")
    sk.pose.clear()

    # 5) 渲染（静止）
    img = sk.draw(W, H)
    cv2.imwrite(os.path.join(BASE, "_骨架_静止.png"), img)

    # 6) 动画：走路 —— 双腿反相摆动
    anim = {"bones": {
        "legL": {"rotate": [{"time": 0.0, "value": -20.0},
                            {"time": 0.4, "value": 20.0},
                            {"time": 0.8, "value": -20.0}]},
        "legR": {"rotate": [{"time": 0.0, "value": 20.0},
                            {"time": 0.4, "value": -20.0},
                            {"time": 0.8, "value": 20.0}]},
    }}
    os.makedirs(os.path.join(BASE, "_骨架序列"), exist_ok=True)
    angles = []
    for i in range(8):
        t = i * 0.1
        apply_animation(sk, anim, t)
        angles.append((sk.pose["legL"]["rot"], sk.pose["legR"]["rot"]))
        frame = sk.draw(W, H)
        cv2.imwrite(os.path.join(BASE, "_骨架序列", f"{i:02d}.png"), frame)

    print("\n--- 动画插值（双腿反相）---")
    for i, (l, r) in enumerate(angles):
        print(f"  frame{i}  legL={l:+7.1f}  legR={r:+7.1f}  反相={abs(l+r)<1e-6}")

    print("\n--- 输出 ---")
    print(f"  静止帧: {BASE}/_骨架_静止.png")
    print(f"  8帧序列: {BASE}/_骨架序列/00-07.png")
    print("\n结论：JSON 解析 + FK + slot 绘制 全部自实现，无官方 runtime。")
