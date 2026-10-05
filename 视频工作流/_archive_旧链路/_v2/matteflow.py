# -*- coding: utf-8 -*-
"""matteflow —— 抠图 + 背景单帧 + alpha 区内插帧（v2 正确架构）。

为什么是这个架构（由实测数据推出，不是拍脑袋）：

  整场景 N 格生图 → 背景必然不一致：
    实测 8 格亮度 114.0/128.8/114.5/127.1/109.6/125.3/111.6/129.3（奇偶交替差 14 级）
    各格上半部差异 34~194 → 人物在格里的位置都不一样
    结果：光流全图判为运动，mask ratio=1.000，背景板失效

  光流分辨运动区这条路本身不成立：
    绿幕（真·纯色）实测 mag p50=3.89，比真正运动的人物区 2.23 还高
    → 光流在纯色区追踪到的是噪声
    但同一组数据：绿幕区像素差 3.31 vs 人物区 22.54，区分度 6.8 倍
    → 差异本身区分度极好，只是不该用光流测，该用 alpha

  所以：
    背景 1 张，全程复用        → 一致性由流程保证，不靠生图
    人物绿幕 8 格 → 抠 alpha   → 运动区精确已知，不用猜
    只在 alpha 并集内插帧      → 背景恒定，虚影只可能出现在人物区
"""
from __future__ import annotations

import os
import sys

import cv2
import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, ROOT)

import _matting      # noqa: E402
import _despill      # noqa: E402
import composite     # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import interp as IT  # noqa: E402

GEN = os.path.join(ROOT, "_生成")


# ---------- 切图集 + 抠图 ----------
def cut_sheet(path: str, cols: int = 4, rows: int = 2) -> list:
    """按显式行列切图集。

    split_sheet(sheet, cols, rows) —— 参数顺序是 cols 在前。
    曾经传反得到 2列4行，bbox x 出现 [300,553] 与 [22,266] 两组值，
    说明人物位置忽左忽右；改对后 bbox 全部收敛到 x[15~271]。
    """
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise SystemExit(f"读图失败: {path}")
    return _matting.split_sheet(im, cols, rows)


def key_all(cells: list) -> list:
    """逐格抠图，返回 BGRA 列表。"""
    out = []
    for i, c in enumerate(cells):
        bgra = _despill.flood_key(c)[0]
        a = bgra[..., 3]
        if (a > 128).sum() == 0:
            raise SystemExit(f"第 {i+1} 格抠空，绿幕参数需重标定")
        out.append(bgra)
    return out


def trim_all(bgras: list, size=None) -> list:
    """按 alpha 包围盒裁剪并统一尺寸。

    必须裁：各格 bbox 虽高度一致（实测 435~438），但 y 起点分两档
    （第一行 41、第二行 551），不裁直接合成人物会上下跳。
    """
    if not size:
        size = (256, 440)
    out = []
    for b in bgras:
        a = b[..., 3]
        ys, xs = np.where(a > 128)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        out.append(cv2.resize(b[y0:y1, x0:x1], size,
                              interpolation=cv2.INTER_AREA))
    return out


# ---------- 合成 ----------
def place(bg: np.ndarray, bgra: np.ndarray,
          cx: float, base_y: float, scale: float = 1.0) -> np.ndarray:
    """把一帧人物贴到背景上。脚底对齐 base_y，水平中心 cx。"""
    h, w = bg.shape[:2]
    ph = int(bgra.shape[0] * scale)
    pw = int(bgra.shape[1] * scale)
    if ph < 2 or pw < 2:
        raise ValueError("scale 过小")
    p = cv2.resize(bgra, (pw, ph), interpolation=cv2.INTER_AREA)
    x = int(round(cx - pw / 2.0))
    y = int(round(base_y - ph))
    out = bg.copy()
    # 边界裁剪
    sx0, sy0 = max(0, -x), max(0, -y)
    sx1 = min(pw, w - x) if x < w else 0
    sy1 = min(ph, h - y) if y < h else 0
    if sx1 <= sx0 or sy1 <= sy0:
        return out
    src = p[sy0:sy1, sx0:sx1]
    dx0, dy0 = x + sx0, y + sy0
    a = (src[..., 3:].astype(np.float32) / 255.0)
    dst = out[dy0:dy0 + (sy1 - sy0), dx0:dx0 + (sx1 - sx0)].astype(np.float32)
    out[dy0:dy0 + (sy1 - sy0), dx0:dx0 + (sx1 - sx0)] = np.clip(
        src[..., :3].astype(np.float32) * a + dst * (1.0 - a), 0, 255
    ).astype(np.uint8)
    return out


def compose(bg: np.ndarray, bgras: list, cx: float,
            base_y: float, scale: float = 1.0) -> list:
    """把整串人物帧贴到同一张背景上 → 关键帧序列。"""
    return [place(bg, b, cx, base_y, scale) for b in bgras]


def alpha_union(bgras: list, bg_shape, cx: float, base_y: float,
                scale: float = 1.0) -> np.ndarray:
    """人物 alpha 在画面上的并集 —— 这就是精确运动区，不用光流猜。"""
    h, w = bg_shape[:2]
    u = np.zeros((h, w), bool)
    for b in bgras:
        ph, pw = int(b.shape[0] * scale), int(b.shape[1] * scale)
        a = cv2.resize(b[..., 3], (pw, ph), interpolation=cv2.INTER_AREA) > 128
        x = int(round(cx - pw / 2.0))
        y = int(round(base_y - ph))
        sx0, sy0 = max(0, -x), max(0, -y)
        if x >= w or y >= h:
            continue
        sub = a[sy0:sy0 + min(ph, h - y), sx0:sx0 + min(pw, w - x)]
        u[y + sy0:y + sy0 + sub.shape[0],
          x + sx0:x + sx0 + sub.shape[1]] |= sub
    return u


# ---------- 主流程 ----------
def run(bg_path: str, sheet_path: str, cols: int = 4, rows: int = 2,
        cx: float = 0.5, base_y: float = 0.82, scale: float = 1.0,
        mul: int = 7, loops: int = 8, out_path: str = None,
        out_size=None, height_ratio: float = 0.0) -> dict:
    """out_size=(w,h) 先把背景缩到成片尺寸再合成，避免 2048 高图白跑算力。
    height_ratio>0 时，scale 由「人物占画面高度比例」反算，不用手调。"""
    bg = cv2.imread(bg_path, cv2.IMREAD_COLOR)
    if bg is None:
        raise SystemExit(f"读背景失败: {bg_path}")
    if out_size:
        bg = cv2.resize(bg, tuple(out_size), interpolation=cv2.INTER_AREA)
    H, W = bg.shape[:2]
    cx_px, base_px = cx * W if cx <= 1.0 else cx, base_y * H if base_y <= 1.0 else base_y

    if height_ratio > 0:
        probe = trim_all(key_all(cut_sheet(sheet_path, cols, rows)))
        scale = (H * height_ratio) / float(probe[0].shape[0])

    cells = cut_sheet(sheet_path, cols, rows)
    bgras = trim_all(key_all(cells)) if height_ratio <= 0 else trim_all(probe)
    keys = compose(bg, bgras, cx_px, base_px, scale)
    u = alpha_union(bgras, bg.shape, cx_px, base_px, scale)

    seq = IT.close_loop(keys, mul, lock_bg=True, bg=bg)
    full = seq * max(1, loops)
    if out_path:
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        vw = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"),
                             60, (W, H))
        for f in full:
            vw.write(f.astype(np.uint8))
        vw.release()
    return {"keys": len(keys), "mask_ratio": float(u.mean()),
            "frames": len(full), "dur_s": len(full) / 60.0,
            "out": out_path}


# ---------- 自检 ----------
def self_check() -> None:
    # 1) 合成用例：纯色底 + 移动方块
    h, w = 120, 160
    bg = np.full((h, w, 3), 90, np.uint8)
    bgras = []
    for i in range(4):
        b = np.zeros((60, 40, 4), np.uint8)
        b[..., :3] = 200
        b[10 + i * 8:30 + i * 8, 10:30, 3] = 255
        bgras.append(b)
    keys = compose(bg, bgras, 80, 110, 1.0)
    assert len(keys) == 4
    # 背景区必须恒为背景
    corner = (slice(0, 20), slice(0, 20))
    for k in keys:
        assert np.allclose(k[corner], bg[corner]), "背景被污染"

    # 2) alpha 并集 = 精确运动区，占比应等于人物占画面的比例
    u = alpha_union(bgras, bg.shape, 80, 110, 1.0)
    assert 0.0 < u.mean() < 0.6, u.mean()
    # 并集外必须没有任何人物像素
    for k in keys:
        d = np.abs(k[~u].astype(float) - bg[~u].astype(float)).mean()
        assert d < 1.0, f"并集外出现差异: {d}"

    # 3) 并集内确实在变（不是静止复制）
    ds = [np.abs(keys[i][u].astype(float) - keys[0][u].astype(float)).mean()
          for i in range(1, 4)]
    assert max(ds) > 1.0, f"人物未动: {ds}"

    # 4) 插帧后背景仍恒定
    seq = IT.close_loop(keys, 3, lock_bg=True, bg=bg)
    for f in seq:
        assert np.allclose(f[corner], bg[corner]), "插帧后背景漂移"

    # 5) 越界
    for fn in (lambda: place(bg, bgras[0], 80, 110, 0.0),
               lambda: compose(bg, bgras, 80, 110, 0.001)):
        try:
            fn()
            raise AssertionError("应当抛 ValueError")
        except ValueError:
            pass

    # 6) 真实素材跑通（若存在）
    sheet = os.path.join(GEN, "玄奘_物理8格.png")
    bgp = os.path.join(GEN, "城墙背景.png")
    if os.path.exists(sheet) and os.path.exists(bgp):
        cs = cut_sheet(sheet, 4, 2)
        assert len(cs) == 8, len(cs)
        bs = trim_all(key_all(cs))
        hs = [int(np.where(b[..., 3] > 128)[0].max()
                  - np.where(b[..., 3] > 128)[0].min()) for b in bs]
        assert max(hs) - min(hs) < 30, f"各格人物高度不一致: {hs}"
    else:
        hs = []

    print("matteflow self_check OK  并集占比%.3f 背景恒定✓ 人物动✓ | 真实8格高度%s"
          % (u.mean(), hs))


if __name__ == "__main__":
    self_check()
