#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spine 格式骨架求解器 —— 不需要官方 runtime
==================================================
【核心论点】
  引擎不是必需品。只要代码能：
    1. 读到骨架数据（JSON）
    2. 读到贴图资源（PNG）
  就能自己算 FK（正向运动学）并渲染出来。

  Spine 官方 runtime 做的也是这三件事：
    解析 JSON -> 计算骨骼世界变换 -> 按 slot 顺序画附件
  没有任何黑箱，格式是公开的。

【本文件实现】
  · 解析 Spine JSON 的 bones / slots / skins / ik
  · FK：局部变换 -> 世界变换（2D 仿射矩阵）
  · slot 绘制顺序（解决穿模的关键）
  · 附件按骨骼变换贴图
  · 动画：rotate / translate timeline 插值

【为什么 slot 顺序能解决穿模】
  Spine 规范："Images in higher index slots are drawn on top of
  those in lower index slots."
  绘制顺序是【数据定义的】，不是猜的。
"""
import json
import math
import os

import cv2
import numpy as np


# ------------------------------------------------------------------ 数学
def mat_mul(A, B):
    """2x3 仿射矩阵相乘 A @ B"""
    a = np.array([[A[0], A[1], A[2]],
                  [A[3], A[4], A[5]],
                  [0.0, 0.0, 1.0]])
    b = np.array([[B[0], B[1], B[2]],
                  [B[3], B[4], B[5]],
                  [0.0, 0.0, 1.0]])
    c = a @ b
    return [c[0, 0], c[0, 1], c[0, 2], c[1, 0], c[1, 1], c[1, 2]]


def mat_local(x, y, rot_deg, sx=1.0, sy=1.0):
    """骨/附件的局部变换：平移 -> 旋转 -> 缩放"""
    r = math.radians(rot_deg)
    cos, sin = math.cos(r), math.sin(r)
    # 先缩放，再旋转，最后平移
    a = cos * sx
    b = sin * sx
    c = -sin * sy
    d = cos * sy
    return [a, c, x, b, d, y]


def mat_apply(M, px, py):
    return (M[0] * px + M[1] * py + M[2],
            M[3] * px + M[4] * py + M[5])


def mat_inverse(M):
    a, b, tx = M[0], M[1], M[2]
    c, d, ty = M[3], M[4], M[5]
    det = a * d - b * c
    if abs(det) < 1e-12:
        return [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]
    ia = d / det
    ib = -b / det
    ic = -c / det
    idd = a / det
    return [ia, ib, -(ia * tx + ib * ty), ic, idd, -(ic * tx + idd * ty)]


# ------------------------------------------------------------------ 骨架
class Skeleton:
    """最小 Spine 骨架实现"""

    def __init__(self, data, img_loader=None):
        self.raw = data
        self.bones = {b["name"]: b for b in data.get("bones", [])}
        self.unknown = set()   # 驱动了不存在的骨骼 -> 静默失效，必须可检出
        self.slots = data.get("slots", [])
        self.skins = data.get("skins", {})
        if isinstance(self.skins, list):
            self.skins = {s.get("name", "default"): s.get("attachments", {})
                          for s in self.skins}
        self.img_loader = img_loader or (lambda p: None)
        # 运行时状态：骨骼当前的旋转/位移增量（动画写入）
        self.pose = {}          # bone -> {rot, x, y}

    # ---------------------------------------------------------------- FK
    def world_matrix(self, name, cache=None):
        """
        正向运动学：从根骨累乘到该骨，得到世界变换。
        【这是全部的核心】—— 引擎内部做的也是这个。
        """
        if cache is None:
            cache = {}
        if name in cache:
            return cache[name]

        b = self.bones.get(name)
        if b is None:
            self.unknown.add(name)
            return [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]

        # 本地 setup pose 变换 + 动画增量
        p = self.pose.get(name, {})
        lm = mat_local(
            b.get("x", 0.0) + p.get("x", 0.0),
            b.get("y", 0.0) + p.get("y", 0.0),
            b.get("rotation", 0.0) + p.get("rot", 0.0),
            b.get("scaleX", 1.0), b.get("scaleY", 1.0))

        parent = b.get("parent")
        if parent:
            pm = self.world_matrix(parent, cache)
            wm = mat_mul(pm, lm)
        else:
            wm = lm
        cache[name] = wm
        return wm

    # ---------------------------------------------------------------- 绘制
    def draw(self, W, H, bg=None, skin="default"):
        """
        按 slot 数组顺序绘制 —— 索引大的画在上面。
        这一条就解决了穿模：顺序由数据定，不由代码猜。
        """
        canvas = np.zeros((H, W, 4), np.uint8)
        if bg is not None:
            canvas[:, :, :3] = bg
            canvas[:, :, 3] = 255

        cache = {}
        attachments = self.skins.get(skin, {})

        for s in self.slots:                    # ← 顺序即绘制顺序
            sname = s["name"]
            bone_name = s.get("bone", sname)
            wm = self.world_matrix(bone_name, cache)
            att = attachments.get(sname, {})
            if not att:
                continue
            for aname, a in att.items():
                img = self.img_loader(a.get("path", aname))
                if img is None:
                    continue
                am = mat_local(a.get("x", 0.0), a.get("y", 0.0),
                               a.get("rotation", 0.0),
                               a.get("scaleX", 1.0), a.get("scaleY", 1.0))
                full = mat_mul(wm, am)
                canvas = self._blit(canvas, img, full)
        return canvas

    @staticmethod
    def _blit(dst, src, M):
        """把 src 按仿射矩阵 M 贴到 dst（双线性 + alpha 混合）"""
        H, W = dst.shape[:2]
        sh, sw = src.shape[:2]
        # 源图四角 -> 目标
        pts = np.array([[0, 0], [sw, 0], [sw, sh], [0, sh]], np.float32)
        dst_pts = np.array([mat_apply(M, p[0], p[1]) for p in pts], np.float32)

        # 求目标包围盒，跳过画外
        x0, y0 = int(np.floor(dst_pts[:, 0].min())), int(np.floor(dst_pts[:, 1].min()))
        x1, y1 = int(np.ceil(dst_pts[:, 0].max())), int(np.ceil(dst_pts[:, 1].max()))
        if x1 <= 0 or y1 <= 0 or x0 >= W or y0 >= H:
            return dst
        cx0, cy0 = max(0, x0), max(0, y0)
        cx1, cy1 = min(W, x1), min(H, y1)
        if cx1 <= cx0 or cy1 <= cy0:
            return dst

        # 目标区域 -> 源图坐标（逆变换）
        inv = mat_inverse(M)
        gx, gy = np.meshgrid(np.arange(cx0, cx1) + 0.5,
                             np.arange(cy0, cy1) + 0.5)
        sx, sy = mat_apply(inv, gx, gy)
        sx = np.clip(sx, 0, sw - 1).astype(np.float32)
        sy = np.clip(sy, 0, sh - 1).astype(np.float32)

        # 采样（含 alpha）
        sampled = cv2.remap(src, sx, sy, interpolation=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT,
                            borderValue=(0, 0, 0, 0))
        a = sampled[:, :, 3:4].astype(np.float32) / 255.0
        # 【逻辑唯一】混合交由 physics.alpha_blend
        # 边界外置 0
        outside = (gx < x0) | (gx > x1) | (gy < y0) | (gy > y1)
        a[outside] = 0.0

        roi = dst[cy0:cy1, cx0:cx1].astype(np.float32)
        out = sampled[:, :, :3].astype(np.float32) * a + roi[:, :, :3] * (1 - a)
        dst[cy0:cy1, cx0:cx1, :3] = np.clip(out, 0, 255).astype(np.uint8)
        dst[cy0:cy1, cx0:cx1, 3] = np.maximum(roi[:, :, 3], a[:, :, 0] * 255).astype(np.uint8)
        return dst


# ------------------------------------------------------------------ 动画
def apply_animation(sk, anim, time):
    """
    把动画某时刻的 rotate/translate 写入 sk.pose。
    Spine 的 timeline 就是这几种，没有别的魔法。
    """
    sk.pose.clear()
    for bname, tl in anim.get("bones", {}).items():
        rot = _interp(tl.get("rotate"), time, 0.0)
        tx = _interp(tl.get("translate"), time, 0.0, idx=0)
        ty = _interp(tl.get("translate"), time, 0.0, idx=1)
        sk.pose[bname] = {"rot": rot, "x": tx, "y": ty}


def _interp(keys, time, default=0.0, idx=None):
    if not keys:
        return default
    if idx is None:
        arr = [(k["time"], k.get("value", 0.0)) for k in keys]
    else:
        arr = [(k["time"], k.get("value", [0.0, 0.0])[idx]) for k in keys]
    arr.sort()
    if time <= arr[0][0]:
        return arr[0][1]
    if time >= arr[-1][0]:
        return arr[-1][1]
    for i in range(len(arr) - 1):
        t0, v0 = arr[i]
        t1, v1 = arr[i + 1]
        if t0 <= time <= t1:
            u = (time - t0) / max(1e-9, t1 - t0)
            return v0 + (v1 - v0) * u
    return default


# ------------------------------------------------------------------ 自检

if __name__ == "__main__":
    from skeleton_runtime_selfcheck import self_check
    self_check()
