#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_puppet_render —— V6 部件化合成：骨骼驱动部件，替代序列帧硬切

【为什么不用图像域混合】Unity URP 序列帧教程原话：两帧线性混合本质上就是叠加，
运动剧烈的帧之间会产生重影。所以 cross-dissolve 的重影是固有缺陷，必须走部件化。

【原理】pose.solve 在任意 t 连续可算关节坐标 → part_transform 算出每个部件的
{anchor_px, angle_rad, length_px} → 把部件图绕锚点旋转+缩放后合成。
60fps 下每帧都是精确姿态，480 帧 = 480 个连续角度（对比 16 格只有 16 个离散角度）。
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

_CACHE = {}


def load_puppet(cfg="puppet.json"):
    """读 puppet.json + 预加载部件图（RGBA float）。"""
    if _CACHE:
        return _CACHE
    d = json.load(open(os.path.join(BASE, cfg), encoding="utf-8"))
    for pid, v in d["parts"].items():
        im = Image.open(os.path.join(BASE, v["file"])).convert("RGBA")
        _CACHE[pid] = {
            "rgba": np.array(im).astype(np.float32) / 255.0,
            "u": v["anchor_u"], "v": v["anchor_v"],
            "dir": v.get("dir", "down"),
        }
    return _CACHE


def _rotate_part(rgba, u, v, angle, scale):
    """绕锚点旋转 + 缩放。

    【修复记录】旧实现返回锚点为 (u*nw, v*nh) —— 旋转后锚点没跟着移动。
    实测：rot=0 尺寸(376,156) 锚点(78,22.6)；rot=90° 尺寸(157,377) 锚点仍是
    (78,22.6)。形状变了锚点不动 = 部件错位装配，这是高宽比只有 1.79 的根因。

    正确做法：把锚点放到【正方形画布的正中心】，绕画布中心旋转 ——
    中心点在旋转下不动，所以输出锚点恒为画布中心，装配偏移可直接算。
    画布边长取对角线，保证任何角度都不裁切。
    """
    h, w = rgba.shape[:2]
    nh, nw = max(1, int(round(h * scale))), max(1, int(round(w * scale)))
    pil = Image.fromarray((np.clip(rgba[..., :3], 0, 1) * 255).astype(np.uint8), "RGB")
    pa = Image.fromarray((np.clip(rgba[..., 3], 0, 1) * 255).astype(np.uint8), "L")
    pil = pil.resize((nw, nh), Image.LANCZOS)
    pa = pa.resize((nw, nh), Image.LANCZOS)
    ax, ay = u * nw, v * nh
    D = int(math.ceil(math.hypot(nh, nw))) + 4
    cx = cy = D / 2.0
    # 把锚点挪到画布中心
    ox, oy = cx - ax, cy - ay
    canvas = Image.new("RGB", (D, D), (0, 0, 0))
    canvas.paste(pil, (int(round(ox)), int(round(oy))))
    acanvas = Image.new("L", (D, D), 0)
    acanvas.paste(pa, (int(round(ox)), int(round(oy))))
    deg = -math.degrees(angle)          # 图像系 y 向下，PIL 正角度=逆时针，故取负
    pil = canvas.rotate(deg, resample=Image.BICUBIC, center=(cx, cy), expand=False)
    pa = acanvas.rotate(deg, resample=Image.BICUBIC, center=(cx, cy), expand=False)
    out = np.zeros((D, D, 4), np.float32)
    out[..., :3] = np.array(pil).astype(np.float32) / 255.0
    out[..., 3] = np.array(pa).astype(np.float32) / 255.0
    return out, (cx, cy)


def compose_person(joints, px_per_m, origin_px, draw_order):
    """按绘制顺序合成一个人。返回 (RGB, A) 及其在画布中的包围盒。"""
    import puppet
    parts = load_puppet()
    # all_transforms 返回 [(pid, transform)...]，已按绘制顺序排好（不是 dict）
    seq = puppet.all_transforms(joints, px_per_m, origin_px)
    layers = []
    for order, (pid, t) in enumerate(seq):
        p = parts.get(pid)
        if not t or p is None:
            continue
        layers.append((order, pid, t, p))
    layers.sort(key=lambda x: x[0])
    # 收集所有层的画布范围
    boxes = []
    for _o, pid, t, p in layers:
        rgba = p["rgba"]
        bone_len_px = t["length_px"]
        h, w = rgba.shape[:2]
        # 部件图的骨骼长度 = 部件高（假设部件沿骨骼方向竖直摆放）
        scale = bone_len_px / max(1.0, float(h))
        ang = t["angle_rad"]
        # 【基准角】部件图"零旋转时"骨骼指向由锚点端决定：
        #   四肢锚在【顶端】(髋/肩/膝/肘) → 骨骼朝下，as-drawn = +pi/2 → rot = ang - pi/2
        #   躯干锚在【底端】(pelvis/neck) → 骨骼朝上，as-drawn = -pi/2 → rot = ang + pi/2
        #   混用会整体翻转 180°（实测踩到）。
        drawn = math.pi / 2.0 if p.get("dir", "down") == "down" else -math.pi / 2.0
        rot = ang - drawn
        out, anc = _rotate_part(rgba, p["u"], p["v"], rot, scale)
        ax, ay = t["anchor_px"]
        # 旋转后锚点在图内的相对位置（按 scale 缩放，旋转中心不动）
        px, py = anc[0], anc[1]
        x0 = ax - px
        y0 = ay - py
        boxes.append((x0, y0, out))
    if not boxes:
        return None, None
    minx = min(b[0] for b in boxes)
    miny = min(b[1] for b in boxes)
    maxx = max(b[0] + b[2].shape[1] for b in boxes)
    maxy = max(b[1] + b[2].shape[0] for b in boxes)
    W = int(math.ceil(maxx - minx))
    H = int(math.ceil(maxy - miny))
    if W <= 0 or H <= 0:
        return None, None
    acc = np.zeros((H, W, 3), np.float32)
    acca = np.zeros((H, W), np.float32)
    for x0, y0, out in boxes:
        ix, iy = int(round(x0 - minx)), int(round(y0 - miny))
        h, w = out.shape[:2]
        a = out[..., 3]
        # porter_duff over（预乘）
        acc[iy:iy + h, ix:ix + w] = acc[iy:iy + h, ix:ix + w] * (1 - a[..., None]) + out[..., :3] * a[..., None]
        acca[iy:iy + h, ix:ix + w] = acca[iy:iy + h, ix:ix + w] * (1 - a) + a
    return acc, acca, (int(minx), int(miny))


def self_check():
    import pose, _common as C, json
    from puppet import PARTS, DRAW_ORDER, with_derived
    spec = json.load(open(os.path.join(BASE, "scene_spec.json"), encoding="utf-8"))
    rig = spec["biped_rig"]
    height_m = float(rig["身高m"])
    gait = dict(rig["gait"])
    speed = float(gait["speed_m_s"]); stride = float(gait.get("stride_m", height_m * 0.88))
    gait["cycle_s"] = C.gait_cycle_from_speed(speed, stride); gait["stride_m"] = stride
    pspec = {"height_m": height_m, "anthro": rig["anthro"], "face": rig["face"],
             "poses": rig["poses"], "gait": gait}
    ok = []
    for t in (0.0, 0.25, 0.5, 0.75):
        j = pose.solve(pspec, "walk", t=t)["joints"]
        r = compose_person(with_derived(j), 100.0, (0.0, 0.0), DRAW_ORDER)
        if r[0] is None:
            ok.append((t, None)); continue
        rgb, a, box = r
        ok.append((t, (rgb.shape[1], rgb.shape[0])))
    print("self_check 各 t 合成尺寸:")
    for t, sz in ok:
        print("  t=%.2f -> %s" % (t, sz))
    good = all(s is not None for _, s in ok)
    print("[PASS] 部件化合成" if good else "[FAIL] 有帧失败")
    return 0 if good else 1


if __name__ == "__main__":
    sys.exit(self_check())
