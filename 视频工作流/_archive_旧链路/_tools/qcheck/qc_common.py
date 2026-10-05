#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qc_common —— 质量工具的公共层：读帧、亮度、灰度、帧差。

只用 numpy + cv2，无模型权重。
"""
import os
import numpy as np
import cv2

# Rec.709 亮度权重（与 ffmpeg/EBU 一致）
Y_W = np.array([0.2126, 0.7152, 0.0722], dtype=np.float64)


def read_gray(path):
    """读图 -> 灰度 float64 [0,1]。"""
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError("无法读取: %s" % path)
    bgr = img.astype(np.float64) / 255.0
    return bgr[:, :, 2] * Y_W[0] + bgr[:, :, 1] * Y_W[1] + bgr[:, :, 0] * Y_W[2]


def read_bgr(path):
    img = cv2.imread(path, cv2.IMREAD_COLOR)
    if img is None:
        raise FileNotFoundError("无法读取: %s" % path)
    return img


class Seq:
    """帧序列源：目录里的图片，或视频文件。"""

    def __init__(self, src, fps=30.0):
        self.fps = float(fps)
        self.frames = []          # 惰性：只在需要时解码
        self.paths = []
        if isinstance(src, (list, tuple)):
            self.paths = [str(p) for p in src]
        elif os.path.isdir(src):
            exts = (".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff")
            self.paths = sorted(
                os.path.join(src, f) for f in os.listdir(src)
                if f.lower().endswith(exts))
            if not self.paths:
                raise ValueError("目录无图片: %s" % src)
        elif os.path.isfile(src):
            self._cap = cv2.VideoCapture(src)
            if not self._cap.isOpened():
                raise ValueError("无法打开视频: %s" % src)
            self._video = True
            f = self._cap.get(cv2.CAP_PROP_FPS)
            if f and f > 0:
                self.fps = float(f)
            return
        else:
            raise ValueError("不支持的输入: %s" % src)
        self._video = False

    def __len__(self):
        if self._video:
            return int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        return len(self.paths)

    def gray(self, i):
        if self._video:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, img = self._cap.read()
            if not ok:
                raise IndexError(i)
            bgr = img.astype(np.float64) / 255.0
            return bgr[:, :, 2] * Y_W[0] + bgr[:, :, 1] * Y_W[1] + bgr[:, :, 0] * Y_W[2]
        return read_gray(self.paths[i])

    def bgr(self, i):
        if self._video:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ok, img = self._cap.read()
            if not ok:
                raise IndexError(i)
            return img
        return read_bgr(self.paths[i])

    def luma_series(self):
        """全部帧的平均亮度序列（用于闪烁检测）。"""
        return np.array([float(self.gray(i).mean()) for i in range(len(self))])


def frame_diff_sq(a, b):
    """FD(i) = MEAN((Y(i+1)-Y(i))^2)。业界帧冻结判据的分子。"""
    d = b - a
    return float(np.mean(d * d))


def pearson(a, b):
    """归一化帧间相关系数 ρk —— 用于区分【静态场景】与【真冻结】。

    静态场景的相邻帧相关性天然高，光看相关系数会把静态误判为冻结；
    必须配合"该镜头是否本应有运动"来判。
    """
    a = a.ravel() - a.mean()
    b = b.ravel() - b.mean()
    den = np.sqrt((a * a).sum() * (b * b).sum())
    if den < 1e-12:
        return 1.0
    return float((a * b).sum() / den)
