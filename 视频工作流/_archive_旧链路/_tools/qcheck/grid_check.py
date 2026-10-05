#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""grid_check —— 图集切分的回归检查（P12 的固化版）。

为什么需要（实测逼出 2026-10-03）：
  "人物一闪一闪"的真凶是图集切分错位，不是抠图。两个叠加缺陷：
    ① grid 约定不一致：load_sheet 按 (rows, cols) 解读，
       而 sheet_probe 返回 (cols, rows)。
    ② 抠图粒度错：先对整张图集抠一次再切格 —— flood_key 只保留最大
       连通域，整图最大前景是单个主体，于是 8 格里只有 1 格有内容。
  这两个缺陷都不会报错，只会静默产出"大部分帧是空的"图集，
  播出来就是人物不停闪现。

  本工具把它固化成可重复跑的回归检查：
    零面积格 == 0   且   合成后绿边比例 < 阈值

用法:
  python3 -m _tools.grid_check <图集.png> [图集2.png ...] [--grid 4,2] [--tol 0.05]
  python3 -m _tools.grid_check --self-check
"""
import argparse
import os
import sys

from .sheet_audit import DEFAULT_BG

_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
# 绿边阈值：新版用「绿色残留」判据（Aksoy 式反解 F）。
# 旧版 0.05 是超绿指数口径，对暗绿背板失效，不可沿用。
# 新标定：cap=0.60 时玄奘 0.097 / 旗 -0.006；取 0.15 为合格线（留余量）。
GREEN_TOL = 0.15


def _load_sheet_frames(path, grid=None):
    sys.path.insert(0, _HERE)
    if grid is None:
        from _tools.qcheck.sheet_probe import probe
        r = probe(path)
        if not r.get("ok"):
            return None, "sheet_probe 失败: %s" % r.get("reason", "")
        grid = (r["cols"], r["rows"])
    import build_util as BU
    return BU.load_sheet(path, grid, grid[0] * grid[1]), grid


def _g_contam(rgb3, a, bg=None):
    """绿色残留（业界 Aksoy 式：反解前景色 F 后比较 G 通道抬升）。

    归一化到 [0,1]：0 = 无残留，1 = 完全等于背板色。
    可略小于 0（边缘 G 低于主体 G），属正常。
    """
    import numpy as np
    bg = np.array(DEFAULT_BG, np.float32) if bg is None else np.array(bg, np.float32)
    aa = np.clip(np.asarray(a, np.float32), 1e-6, 1.0)
    F = np.clip((np.asarray(rgb3, np.float32)
                 - (1 - aa[:, :, None]) * bg) / aa[:, :, None], 0, 255)
    core = aa > 0.95
    edge = (aa > 0.15) & (aa < 0.95)
    if core.sum() < 100 or edge.sum() < 50:
        return None
    cG = float(F[core][:, 1].mean())
    eG = float(F[edge][:, 1].mean())
    den = bg[1] - cG
    if abs(den) < 1e-6:
        return None
    return round((eG - cG) / den, 4)


def check(path, grid=None, tol=GREEN_TOL):
    """-> dict：每格面积、绿边、判定"""
    try:
        frames, g = _load_sheet_frames(path, grid)
    except Exception as e:
        # 错误 grid 会让 load_sheet 抛错 —— 这本身就是"抓到了"
        return {"path": os.path.abspath(path), "ok": False,
                "reason": "%s: %s" % (type(e).__name__, str(e)[:120])}
    if frames is None:
        return {"path": os.path.abspath(path), "ok": False, "reason": g}

    import numpy as np
    areas = [int((a > 0.5).sum()) for _, a in frames]
    # 绿边判据已升级（旧版用超绿指数，对暗绿背板失效，见 sheet_audit 说明）
    greens = []
    for rgb, a in frames:
        v = _g_contam(rgb, a)
        greens.append(0.0 if v is None else v)

    zero = [i for i, v in enumerate(areas) if v == 0]
    dirty = [i for i, v in enumerate(greens) if v > tol]
    return {"path": os.path.abspath(path), "grid": g,
            "n_cells": len(frames), "areas": areas,
            "green_edge": [round(x, 4) for x in greens],
            "zero_cells": zero, "dirty_cells": dirty,
            "ok": not zero and not dirty,
            "verdict": ("PASS" if not zero and not dirty else
                        "FAIL 空格=%s 绿边超标=%s" % (zero, dirty))}


def self_check():
    ok, bad = [], []

    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    # 合成一个 4x2 绿底图集，每格一个非绿方块
    import numpy as np
    from PIL import Image
    H, W = 400, 800
    a = np.zeros((H, W, 3), np.uint8)
    a[:, :] = (69, 124, 58)          # 暗绿背板 BGR->RGB 顺序无所谓
    ch, cw = H // 2, W // 4
    for r in range(2):
        for c in range(4):
            y0, y1 = r * ch + 30, (r + 1) * ch - 30
            x0, x1 = c * cw + 30, (c + 1) * cw - 30
            a[y0:y1, x0:x1] = (30, 20, 90)   # 非绿主体（暖色）
    p = "/tmp/_gridcheck.png"
    Image.fromarray(a).save(p)

    # 1) 正确 grid (4,2) 应全通过
    r = check(p, (4, 2))
    add("1 正确 grid 通过", r.get("ok"), r.get("verdict", "")[:60])
    add("2 8 格全部有主体", len(r.get("areas", [])) == 8 and
        all(v > 0 for v in r.get("areas", [])), str(r.get("areas", []))[:60])

    # 2) 错误 grid (2,4) 应被抓出（rows/cols 颠倒）
    r2 = check(p, (2, 4))
    add("3 颠倒 grid 被抓出", not r2.get("ok"), r2.get("verdict", "")[:60])

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheets", nargs="*")
    ap.add_argument("--grid")
    ap.add_argument("--tol", type=float, default=GREEN_TOL)
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        return 0 if self_check() else 1
    if not a.sheets:
        print("用法: grid_check <图集.png> ...")
        return 2
    grid = None
    if a.grid:
        grid = tuple(int(x) for x in a.grid.split(","))
    allok = True
    for s in a.sheets:
        r = check(s, grid, a.tol)
        allok &= bool(r.get("ok"))
        print("[%s] %s grid=%s" % ("PASS" if r.get("ok") else "FAIL",
                                   os.path.basename(r["path"]), r.get("grid")))
        print("    面积=%s" % r.get("areas"))
        print("    绿边=%s" % r.get("green_edge"))
        print("    %s" % r.get("verdict"))
    return 0 if allok else 1


if __name__ == "__main__":
    sys.exit(main())
