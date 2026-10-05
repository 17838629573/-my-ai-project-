# -*- coding: utf-8 -*-
"""interp —— 光流插帧补帧（纯代码，无模型权重）。

原理（业界标准）：
  对相邻关键帧 I0/I1 算双向光流 F01/F10，
  中间时刻 t 的合成帧 = 双向 warp 后按 t 加权融合。

为什么必须双向：
  单向 warp 会在遮挡区留下空洞（该处运动信息根本不存在）。
  双向 warp 互相填补。

背景处理（新版核心）：
  旧：非运动区直接取 prev 单帧 —— 单帧带着自己的噪声/伪影。
  新：N 张关键帧对齐后，在运动掩码之外逐像素平均，得到一张干净背景板。
      · 随机噪声互相抵消，静态结构被强化（多帧平均降噪，噪声降 √N）
      · 残余的微小差异被平均掉 → 背景略虚
      · 背景虚化不是副作用：景深错觉会把视线吸向清晰的人物

  硬前提：平均前必须先按 global flow 对齐，否则几何扭曲会导致重影。

业界：
  OpenCV DIS 无需模型权重，CPU 可用
  插帧倍数取奇数更稳（3/5/7）
  遮挡是光流的固有弱点，walking cycle 换腿时会踩到
"""
from __future__ import annotations

import cv2
import numpy as np

from flowsplit import (dense_flow, to_gray, split,
                      global_homography, global_flow_field)

_DILATE_K = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9))

# 全局位移低于此值视为「相机静止」，不做 warp
MIN_SHIFT_PX = 0.5


def _remap(img: np.ndarray, flow: np.ndarray) -> np.ndarray:
    """按光流场反向采样：out(x) = img(x + flow)。"""
    h, w = img.shape[:2]
    ys, xs = np.mgrid[0:h, 0:w].astype(np.float32)
    return cv2.remap(img, xs + flow[..., 0], ys + flow[..., 1],
                     cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def _warp_to_t(prev: np.ndarray, next: np.ndarray,
               f01: np.ndarray, f10: np.ndarray, t: float) -> np.ndarray:
    """在时刻 t∈(0,1) 合成一帧（双向 warp + 线性融合）。"""
    a = _remap(prev, f01 * t).astype(np.float32)
    b = _remap(next, f10 * (1.0 - t)).astype(np.float32)
    return np.clip(a * (1.0 - t) + b * t, 0, 255).astype(np.uint8)


# ---------- 背景板：多帧对齐平均 ----------
def align_to_anchor(anchor_gray: np.ndarray, frame: np.ndarray) -> np.ndarray:
    """把 frame 对齐到 anchor 的坐标系。

    global_homography(anchor, frame) 给出 anchor→frame 的 H，
    所以对齐要用它的逆：把 frame 拉回 anchor。
    """
    g = to_gray(frame)
    H = global_homography(anchor_gray, g)
    if H is None:
        return frame
    # 关键：位移近零时必须跳过 warp。
    # 噪声会让单应估出微小但非零的 H，用它 warp 等于给干净底图加畸变，
    # 反而比不平均更糟（实测 19.85 → 23.56）。这是曾经的 bug。
    if np.median(np.abs(global_flow_field(H, g.shape))) < MIN_SHIFT_PX:
        return frame
    try:
        Hi = np.linalg.inv(H)
    except np.linalg.LinAlgError:
        return frame
    h, w = frame.shape[:2]
    return cv2.warpPerspective(frame, Hi, (w, h), flags=cv2.INTER_LINEAR)


def stack_bg(frames: list, thr: float = 1.5) -> dict:
    """把 N 张关键帧合成一张干净背景板。

    步骤（顺序不能换）：
      1. 逐帧按 global flow 对齐到 anchor（不先对齐就平均 = 重影）
      2. 运动掩码之外的像素做加权平均（掩码内是主体，被遮挡不参与）
      3. 掩码全遮处回落到 anchor

    返回 dict: bg(干净背景板), mask(主体并集), aligned(对齐后的帧), n
    """
    if len(frames) < 2:
        raise ValueError("至少需要 2 张关键帧才能叠背景")
    anchor = frames[0]
    ga = to_gray(anchor)
    h, w = anchor.shape[:2]

    acc = np.zeros((h, w), np.float32)
    cnt = np.zeros((h, w), np.float32)
    union = np.zeros((h, w), bool)
    aligned = [anchor]

    # anchor 自身也参与（掩码外）
    for i, f in enumerate(frames):
        if i == 0:
            fa, m = anchor, np.zeros((h, w), bool)
        else:
            gf = to_gray(f)
            r = split(ga, gf, thr=thr)
            fa = align_to_anchor(ga, f)
            m = r["mask"] > 0
            m = cv2.dilate(m.astype(np.uint8), _DILATE_K, iterations=2) > 0
            union |= m
        wgt = (~m).astype(np.float32)
        g = to_gray(fa).astype(np.float32)
        acc += g * wgt
        cnt += wgt
        if i:
            aligned.append(fa)

    cnt_safe = np.where(cnt < 1e-6, 1.0, cnt)
    bg_gray = acc / cnt_safe
    # 掩码全遮处回落到 anchor
    fallback = to_gray(anchor).astype(np.float32)
    bg_gray = np.where(cnt < 1e-6, fallback, bg_gray)

    if anchor.ndim == 3:
        bg = cv2.cvtColor(np.clip(bg_gray, 0, 255).astype(np.uint8),
                          cv2.COLOR_GRAY2BGR)
    else:
        bg = np.clip(bg_gray, 0, 255).astype(np.uint8)

    # bg_gray 供度量用：bg 是 GRAY2BGR 再经 to_gray 会被二次模糊，
    # 拿它去比对只模糊一次的参考图会虚高（实测 1.54 -> 6.55）。
    return {"bg": bg, "bg_gray": np.clip(bg_gray, 0, 255).astype(np.uint8),
            "mask": union, "aligned": aligned, "n": len(frames)}


def _soft_alpha(mask: np.ndarray, blur: float = 3.0) -> np.ndarray:
    """掩码转软 alpha：边缘羽化，避免运动区与背景板之间出现硬接缝。"""
    a = mask.astype(np.float32)
    a = cv2.GaussianBlur(a, (0, 0), blur)
    mx = a.max()
    if mx > 1e-6:
        a = a / mx
    return np.clip(a, 0.0, 1.0)


# ---------- 插帧 ----------
def interp_pair(prev: np.ndarray,
                next: np.ndarray,
                n: int,
                lock_bg: bool = True,
                thr: float = 1.5,
                bg: np.ndarray = None) -> list:
    """在 prev / next 之间插 n 帧，返回 n 帧列表（不含首尾）。

    bg 给了（推荐）：运动区走光流 warp，非运动区取背景板，
                    两者用软 alpha 融合 —— 背景干净且略虚。
    bg 为 None   ：退化成旧行为，非运动区取 prev 单帧。
    """
    if n < 1:
        raise ValueError("n 必须 >= 1")
    if prev.shape != next.shape:
        raise ValueError("两帧尺寸必须一致")
    if bg is not None and bg.shape != prev.shape:
        raise ValueError("bg 尺寸必须与帧一致")

    gp, gn = to_gray(prev), to_gray(next)
    f01 = dense_flow(gp, gn)
    f10 = dense_flow(gn, gp)

    mask = None
    alpha = None
    if lock_bg or bg is not None:
        r = split(gp, gn, thr=thr)
        mask = cv2.dilate((r["mask"] > 0).astype(np.uint8),
                          _DILATE_K, iterations=2) > 0
        alpha = _soft_alpha(mask)

    out = []
    for i in range(1, n + 1):
        t = i / (n + 1.0)
        fr = _warp_to_t(prev, next, f01, f10, t)
        if bg is not None:
            a = alpha[..., None] if fr.ndim == 3 else alpha
            fr = np.clip(fr.astype(np.float32) * a
                         + bg.astype(np.float32) * (1.0 - a), 0, 255
                         ).astype(np.uint8)
        elif mask is not None:
            m = mask[..., None] if fr.ndim == 3 and mask.ndim == 2 else mask
            fr = np.where(m, fr, prev)
        out.append(fr)
    return out


def on_bg(frame: np.ndarray, bg: np.ndarray, thr: float = 1.5) -> np.ndarray:
    """把单张关键帧贴到背景板上：运动区保留该帧，其余取背景板。

    关键帧本身也带自己的噪声/伪影，直接塞进序列会让背景逐帧跳，
    破坏「背景板恒定」的效果 —— 所以关键帧同样要过一遍背景板。
    """
    if frame.shape != bg.shape:
        raise ValueError("帧与背景板尺寸必须一致")
    r = split(to_gray(bg), to_gray(frame), thr=thr)
    m = cv2.dilate((r["mask"] > 0).astype(np.uint8), _DILATE_K,
                   iterations=2) > 0
    if m.sum() == 0:
        return bg.copy()
    a = _soft_alpha(m)
    a = a[..., None] if frame.ndim == 3 else a
    return np.clip(frame.astype(np.float32) * a
                   + bg.astype(np.float32) * (1.0 - a), 0, 255).astype(np.uint8)


def interp_seq(frames: list, n: int, lock_bg: bool = True,
               bg: np.ndarray = None) -> list:
    """对整串关键帧逐对插帧，首尾保留。

    bg 给定时，关键帧自身也会先贴到背景板（见 on_bg）。
    """
    if len(frames) < 2:
        raise ValueError("至少需要 2 张关键帧")
    put = (lambda f: on_bg(f, bg)) if bg is not None else (lambda f: f)
    out = [put(frames[0])]
    for i in range(len(frames) - 1):
        out.extend(interp_pair(frames[i], frames[i + 1], n, lock_bg, bg=bg))
        out.append(put(frames[i + 1]))
    return out


def close_loop(frames: list, n: int, lock_bg: bool = True,
               bg: np.ndarray = None) -> list:
    """循环闭合：额外在最后一张 → 第一张之间插帧，使周期可无缝循环。"""
    return interp_seq(frames + [frames[0]], n, lock_bg, bg=bg)[:-1]


# ---------- 自检 ----------
def _rmse(a: np.ndarray, b: np.ndarray) -> float:
    d = a.astype(np.float32) - b.astype(np.float32)
    return float(np.sqrt((d * d).mean()))


def self_check() -> None:
    h, w = 160, 200
    yy, xx = np.mgrid[0:h, 0:w]
    # 纹理周期必须 >= 16：to_gray 会做 5x5 高斯模糊，
    # 周期 6~10 的细纹理被抹平后梯度归零，光流追踪不到，
    # 掩码全空 -> 主体被算进背景一起平均，反而更糊（实测 24.95->25.42）。
    clean = (((xx // 16) + (yy // 16)) % 2 * 180 + 40).astype(np.uint8)
    clean = cv2.GaussianBlur(clean, (0, 0), 0.8)
    clean_bgr = cv2.cvtColor(clean, cv2.COLOR_GRAY2BGR)
    clean_g = to_gray(clean_bgr)   # 与待测帧同处理，避免模糊次数不一致

    rng = np.random.default_rng(11)
    keys = []
    PS, MV, NOISE = 70, 22, 5.0
    for i in range(4):
        nz = rng.normal(0, NOISE, (h, w)).astype(np.float32)
        f = np.clip(clean.astype(np.float32) + nz, 0, 255).astype(np.uint8)
        f = cv2.cvtColor(f, cv2.COLOR_GRAY2BGR)
        py, px = 70, 50 + i * MV
        ty, tx = np.mgrid[0:PS, 0:PS]
        patch = (((tx // 16) + (ty // 16)) % 2 * 150 + 60).astype(np.uint8)
        f[py:py + PS, px:px + PS] = cv2.cvtColor(patch, cv2.COLOR_GRAY2BGR)
        keys.append(f)

    # 1) 叠背景：噪声必须被压下去（只在真正的背景区衡量）
    st = stack_bg(keys)
    assert st["bg"].shape == keys[0].shape, st["bg"].shape
    assert 0.02 < st["mask"].mean() < 0.6, f"掩码占比异常: {st['mask'].mean()}"

    region = ~cv2.dilate(st["mask"].astype(np.uint8), _DILATE_K,
                         iterations=3).astype(bool)
    assert region.sum() > 2000, region.sum()

    def rmse_at(img):
        return _rmse(to_gray(img)[region], clean[region])

    single = rmse_at(keys[0])
    stacked = _rmse(st["bg_gray"][region], clean_g[region])
    assert stacked < single * 0.75, (
        f"多帧平均未降噪: 单帧{single:.2f} 平均{stacked:.2f}")

    # 2) 用背景板插帧：背景区必须恒定贴住背景板（不再逐帧抖动）
    seq = close_loop(keys, 3, lock_bg=True, bg=st["bg"])
    # 角落在掩码膨胀范围之外：patch 顶部 y=70，膨胀 ~18px 后到 52，
    # 取 0..40 行才不会碰到软边
    corner = (slice(0, 40), slice(0, 25))
    ref = st["bg"][corner]
    for f in seq:
        assert _rmse(f[corner], ref) < 1.0, "背景区未锁定到背景板"

    # 3) 运动区确实在推进（不是静止复制）
    def cx(img):
        d = np.abs(img.astype(float) - clean_bgr.astype(float)).sum(axis=2)
        m = d > 60
        m = cv2.erode(m.astype(np.uint8), np.ones((11, 11), np.uint8)) > 0
        return float(np.mgrid[0:h, 0:w][1][m].mean()) if m.sum() else None

    cs = [c for c in (cx(f) for f in seq) if c is not None]
    assert len(cs) >= 4 and (max(cs) - min(cs)) > 5.0, f"主体未推进: {cs}"

    # 4) 背景板模式必须与「取单帧 prev」不同（证明背景板真的生效）
    seq_prev = close_loop(keys, 3, lock_bg=True, bg=None)
    k = len(keys)
    d = np.abs(seq[k][corner].astype(float)
               - seq_prev[k][corner].astype(float)).mean()
    assert d > 0.5, f"背景板未生效，与单帧模式相同: {d}"

    # 5) 序列长度
    assert len(interp_seq(keys[:2], 3)) == 5
    assert len(close_loop(keys, 3)) > len(keys)

    # 6) 越界抛错
    for fn in (lambda: interp_pair(keys[0], keys[1], 0),
               lambda: interp_pair(keys[0], keys[1][:, :50], 3),
               lambda: interp_seq([keys[0]], 3),
               lambda: stack_bg([keys[0]])):
        try:
            fn()
            raise AssertionError("应当抛 ValueError")
        except ValueError:
            pass

    print("interp self_check OK  背景噪声 单帧%.2f→平均%.2f | 锁定✓ 推进✓ 与单帧差%.2f"
          % (single, stacked, d))


if __name__ == "__main__":
    self_check()
