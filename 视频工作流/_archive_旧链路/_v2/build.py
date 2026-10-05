# -*- coding: utf-8 -*-
"""build —— 整图关键帧流水线主入口。

新逻辑（与旧版根本区别）：
  旧：抠图 → 部件拆分 → 骨架驱动部件 → 逐帧合成
  新：整图生成 → 物理算关键帧间隔 → 光流分离（背景锁死）→ 插帧 → 首帧锚定

流程：
  S1 plan      spec 算周期/关键帧数/间隔          （纯算）
  S2 prompt    keygen 生成整周期提示词            （纯算）
  S3 shot      外部生图，落到 keys/               （外部，本模块只校验）
  S4 interp    flowsplit+interp 插帧出片          （纯算，可离线跑）
  S5 anchor    chain 首帧锚定体检                 （纯算）

S3 是唯一的外部依赖；其余全是纯代码，可反复重跑不产生成本。
"""
from __future__ import annotations

import os
import glob
import cv2
import numpy as np

import spec as SPEC
import keygen as KG
import flowsplit as FS
import interp as IT
import chain as CH

ROOT = os.path.dirname(os.path.abspath(__file__))
KEYS_DIR = os.path.join(ROOT, "keys")
OUT_DIR = os.path.join(ROOT, "out")


# ---------- S1 ----------
def plan(speed: float = None, stride: float = None,
         keys: int = None, total_s: float = None) -> dict:
    """纯算：周期 / 关键帧数 / 间隔 / 插帧倍数 / 分段。"""
    s = SPEC.build(speed=speed, stride=stride, keys=keys)
    seg = None
    if total_s:
        seg = CH.segment_plan(total_s, s["period_s"])
    return {**s, "segment": seg}


# ---------- S2 ----------
DEFAULT_BG = ("唐代城墙，青灰夯土砖石，夕阳侧逆光，"
              "远处佛塔剪影，地面青石板路")


def prompts(p: dict, background: str = None, subject: str = "僧人") -> list:
    """返回 [{"index","phase","t","prompt"}, ...]，prompt 已做背景锁定前置。"""
    r = KG.plan(background or DEFAULT_BG, p["n_keys"],
                p["speed_mps"], subject)
    return r["prompts"]


# ---------- S3：一次生成图集，切格得关键帧 ----------
# 为什么是图集而不是逐张生成：
#   分 N 次生图 = 背景被独立重绘 N 次 = 主动制造累积漂移。
#   一次生图集，N 格是同一次生图产物，背景/光照/服装天然同源，
#   漂移从「N 次」降到「1 次」。
def sheet_bands(mask: np.ndarray, min_ratio: float = 0.35) -> list:
    """投影法找网格带：mask 为 True 表示有内容。

    必须过滤窄带：图集里常出现贯穿全图的细长元素（衣角、水印、缝），
    会把多格连成一片，导致格数虚高。判定：宽度 < 最宽带 * min_ratio 的丢弃。
    """
    v = mask.sum(axis=1) if mask.ndim == 2 else mask
    on = v > v.max() * 0.15
    raw, st = [], None
    for i, x in enumerate(on):
        if x and st is None:
            st = i
        elif not x and st is not None:
            raw.append((st, i))
            st = None
    if st is not None:
        raw.append((st, len(v)))
    if not raw:
        return []
    wmax = max(b - a for a, b in raw)
    return [b for b in raw if (b[1] - b[0]) >= wmax * min_ratio]


def sheet_cut(img, fg_mask=None) -> list:
    """切图集。返回格子列表（按行优先）。

    fg_mask 不给时，用非绿幕 + 非纯黑自动判定内容区。
    """
    bgr = img[:, :, :3]
    if fg_mask is None:
        b, g, r = (bgr[:, :, i].astype(np.int16) for i in range(3))
        green = (g - np.maximum(r, b)) > 40
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        fg_mask = (~green) & (gray > 25)
    rb = sheet_bands(fg_mask.sum(axis=1))
    if not rb:
        raise SystemExit("未探测到行带，图集可能全空")
    cells = []
    for r0, r1 in rb:
        cb = sheet_bands(fg_mask[r0:r1].sum(axis=0))
        for c0, c1 in cb:
            cells.append(bgr[r0:r1, c0:c1].copy())
    return cells


def grid_cut(img, rows: int, cols: int) -> list:
    """按显式行列硬切图集（整场景图集用）。

    sheet_cut 依赖绿幕/空白分隔，整场景图集每格都填满画面，
    投影法找不到分隔带（实测格数=1），所以必须硬切。
    网格线位置由生图提示词指定行列数来保证。
    """
    if rows < 1 or cols < 1:
        raise ValueError("rows/cols 必须 >= 1")
    bgr = img[:, :, :3] if img.ndim == 3 else img
    h, w = bgr.shape[:2]
    out = []
    for r in range(rows):
        for c in range(cols):
            out.append(bgr[r * h // rows:(r + 1) * h // rows,
                           c * w // cols:(c + 1) * w // cols].copy())
    return out


def load_sheet(path: str = None, rows: int = 0, cols: int = 0) -> list:
    """加载图集：优先硬切（rows/cols 都给了），否则投影法切格。"""
    if path is None:
        sh = sorted(glob.glob(os.path.join(KEYS_DIR, "sheet*.png")))
        if not sh:
            raise SystemExit("keys/ 下没有 sheet*.png")
        path = sh[0]
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise SystemExit(f"读图失败: {path}")
    if rows and cols:
        return grid_cut(im, rows, cols)
    return sheet_cut(im)


def keys_ready() -> dict:
    """检查关键帧是否就位：优先整张图集，其次单格图。"""
    if not os.path.isdir(KEYS_DIR):
        return {"ok": False, "n": 0, "files": [], "reason": "keys/ 不存在"}
    sheets = sorted(glob.glob(os.path.join(KEYS_DIR, "sheet*.png")))
    if sheets:
        im = cv2.imread(sheets[0], cv2.IMREAD_UNCHANGED)
        cs = []
        try:
            cs = sheet_cut(im)
        except SystemExit:
            pass
        if len(cs) < 2:
            # 整场景图集每格都填满画面，投影法找不到分隔带（实测格数=1），
            # 必须退回硬切；行列组合由提示词声明，逐种试到格间确有差异为止
            for rows, cols in ((2, 4), (4, 2), (1, 8), (8, 1), (3, 3)):
                if rows * cols >= 2:
                    cs = grid_cut(im, rows, cols)
                    if len({c.mean() for c in cs}) == len(cs):
                        break
        return {"ok": len(cs) >= 2, "n": len(cs),
                "files": [os.path.basename(f) for f in sheets],
                "mode": "sheet",
                "reason": "" if len(cs) >= 2 else "切格不足 2"}
    fs = sorted(glob.glob(os.path.join(KEYS_DIR, "*.png")))
    return {"ok": len(fs) >= 2, "n": len(fs),
            "files": [os.path.basename(f) for f in fs], "mode": "cells",
            "reason": "" if len(fs) >= 2 else "至少需要 2 张关键帧"}


def load_keys() -> list:
    """加载关键帧：图集优先，否则逐格。"""
    if not os.path.isdir(KEYS_DIR):
        raise SystemExit("keys/ 不存在")
    sheets = sorted(glob.glob(os.path.join(KEYS_DIR, "sheet*.png")))
    if sheets:
        return sheet_cut(cv2.imread(sheets[0], cv2.IMREAD_UNCHANGED))
    fs = sorted(glob.glob(os.path.join(KEYS_DIR, "*.png")))
    out = []
    for f in fs:
        im = cv2.imread(f, cv2.IMREAD_COLOR)
        if im is None:
            raise SystemExit(f"读图失败: {f}")
        out.append(im)
    return out


def keys_from_sheet(path: str, expect: int = 0) -> list:
    """从图集文件切出关键帧。expect>0 时校验格数。"""
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise SystemExit(f"读图失败: {path}")
    cells = sheet_cut(im)
    if expect and len(cells) != expect:
        raise SystemExit(
            f"图集格数 {len(cells)} != 期望 {expect}，"
            f"提示词需明确要求 {expect} 格")
    return cells


# ---------- S4 ----------
def interp_keys(imgs: list, mul: int, fps: int = None,
                thr: float = 1.5) -> dict:
    """对关键帧序列插帧。末尾自动闭合回第 0 帧，形成可循环周期。

    背景走多帧对齐平均（stack_bg）：
      N 张关键帧按 global flow 对齐 → 掩码外逐像素平均 → 干净背景板。
      随机噪声互相抵消（降 √N），真正的静态结构被强化，背景略虚 —— 观众视线被吸到清晰主体上。
    """
    if len(imgs) < 2:
        raise SystemExit("至少需要 2 张关键帧")
    fps = fps or SPEC.TARGET_FPS
    st = IT.stack_bg(imgs, thr=thr)
    seq = IT.close_loop(imgs, mul, lock_bg=True, bg=st["bg"])
    return {"frames": seq, "fps": fps, "closed": True,
            "bg": st["bg"], "mask": st["mask"],
            "n": len(seq), "dur_s": len(seq) / fps}


def write_mp4(frames: list, path: str, fps: int = None) -> str:
    fps = fps or SPEC.TARGET_FPS
    os.makedirs(os.path.dirname(path), exist_ok=True)
    h, w = frames[0].shape[:2]
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not vw.isOpened():
        raise SystemExit(f"VideoWriter 打开失败: {path}")
    for f in frames:
        vw.write(f.astype(np.uint8))
    vw.release()
    return path


# ---------- S5 ----------
def anchor_check(imgs: list, thr: float = 1.5) -> dict:
    """首帧锚定：所有关键帧都跟第 0 帧比，背景不该动。"""
    return CH.anchor_report(imgs[0], imgs[1:], thr=thr)


# ---------- 编排 ----------
def status(p: dict = None) -> dict:
    p = p or plan()
    k = keys_ready()
    return {
        "S1_plan": {"period_s": round(p["period_s"], 4),
                    "n_keys": p["n_keys"],
                    "key_interval_s": round(p["key_interval_s"], 4),
                    "interp_mul": p["interp_mul"]},
        "S2_prompt": {"n": p["n_keys"], "ready": True},
        "S3_shot": k,
        "S4_interp": {"ready": k["ok"]},
        "S5_anchor": {"ready": k["ok"]},
    }


# ---------- 自检 ----------
def self_check() -> None:
    # 1) 规划
    p = plan()
    assert p["n_keys"] >= 4, p["n_keys"]
    assert p["key_interval_s"] <= p["period_s"] * 0.5 + 1e-9, p
    assert p["interp_mul"] >= 2, p["interp_mul"]

    # 2) 提示词：背景锁定前置 + 无禁用词
    ps = prompts(p)
    assert len(ps) == p["n_keys"]
    for r in ps:
        assert r["prompt"].startswith("【背景严格锁定】"), "背景锁定未前置"
        for bad in KG.BG_FORBIDDEN:
            assert bad not in r["prompt"], f"出现闪烁导火索: {bad}"

    # 3) 分段
    seg = plan(total_s=120.0)["segment"]
    assert seg["n_segments"] >= 1

    # 4) 用合成关键帧跑通 S4 + S5（不依赖真实生图）
    h, w = 120, 160
    yy, xx = np.mgrid[0:h, 0:w]
    base = cv2.GaussianBlur(
        (((xx // 10) + (yy // 10)) % 2 * 170 + 45).astype(np.uint8), (0, 0), 0.8)
    bg = cv2.cvtColor(base, cv2.COLOR_GRAY2BGR)
    keys = [bg.copy() for _ in range(4)]
    for i, k in enumerate(keys):
        kk = k.copy()
        cv2.circle(kk, (60 + i * 12, 70 + (i % 2) * 8), 14, (30, 200, 250), -1)
        keys[i] = kk
    os.makedirs(KEYS_DIR, exist_ok=True)
    for i, k in enumerate(keys):
        cv2.imwrite(os.path.join(KEYS_DIR, f"_t{i:02d}.png"), k)

    r = interp_keys(keys, 3)
    assert r["n"] > len(keys), r["n"]
    assert r["dur_s"] > 0

    ac = anchor_check(keys)
    assert isinstance(ac["rows"], list) and len(ac["rows"]) == len(keys) - 1

    # 4b) 图集切分（用真实玄奘图集验证：应为 4x2=8 或 4x4=16 格）
    real = os.path.join(ROOT, "..", "_生成", "玄奘_图集.png")
    if os.path.exists(real):
        cs = sheet_cut(cv2.imread(real, cv2.IMREAD_UNCHANGED))
        assert len(cs) in (8, 16), f"切格数异常: {len(cs)}"
        assert all(c.size > 0 for c in cs)
    else:
        cs = []

    # 5) 出片可写
    out = os.path.join(OUT_DIR, "_t.mp4")
    write_mp4(r["frames"][:12], out, 30)
    assert os.path.getsize(out) > 0

    # 6) 状态机
    st = status(p)
    assert st["S3_shot"]["ok"] is True

    # 清理自检产物，避免污染真实关键帧
    for f in glob.glob(os.path.join(KEYS_DIR, "_t*.png")):
        os.remove(f)
    if os.path.exists(out):
        os.remove(out)

    print("build self_check OK  period=%.3fs keys=%d iv=%.3fs mul=%d | 插帧 %d帧 %.2fs | 图集切格 %d"
          % (p["period_s"], p["n_keys"], p["key_interval_s"],
             p["interp_mul"], r["n"], r["dur_s"], len(cs)))


if __name__ == "__main__":
    self_check()
