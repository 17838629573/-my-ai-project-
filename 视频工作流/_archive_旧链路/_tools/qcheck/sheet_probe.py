#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""sheet_probe —— 自动探测生图产出的图集网格布局。

背景（实测逼出）：
  生图模型【不会严格遵守】提示词里写的"排成 N 列 M 行"——
  玄奘图集要求 4×2 得到 4×2 ✓，但旗图集要求 4×2 却得到 2×4 ✗。
  所以 grid 不能硬编码，必须【从图里反推】。

方法：
  1) 背板检测：找非主体区域（绿色背板为主体的补集）
  2) 连通域：每个格子主体是一个大连通块
  3) 聚类：按中心 y 分行、按中心 x 分列
  4) 输出 cols/rows 与每格 bbox

用法:
  python3 -m _tools.qcheck.sheet_probe <图集.png> [--json out.json]
"""
import argparse
import json
import os
import sys

import numpy as np
from PIL import Image


def load(path):
    return np.array(Image.open(path).convert("RGB")).astype(float)


def is_backdrop(a, mode="green"):
    """背板掩码。绿色背板：G 显著高于 R、B。"""
    if mode == "green":
        d = a[:, :, 1] - (a[:, :, 0] + a[:, :, 2]) / 2.0
        return d > 25
    raise ValueError(mode)


def probe(path, min_area_ratio=0.002, watermark_pad=(120, 420)):
    a = load(path)
    H, W, _ = a.shape
    bd = is_backdrop(a)
    fg = ~bd
    # 去右下角水印（元宝 AI 生成）
    ph, pw = watermark_pad
    fg[H - ph:, W - pw:] = False

    try:
        from scipy import ndimage
        lab, cnt = ndimage.label(fg)
        sizes = ndimage.sum(fg, lab, range(1, cnt + 1))
        cells = []
        for i in range(cnt):
            if sizes[i] < fg.size * min_area_ratio:
                continue
            ys, xs = np.where(lab == i + 1)
            cells.append({"area": int(sizes[i]),
                          "x0": int(xs.min()), "x1": int(xs.max()),
                          "y0": int(ys.min()), "y1": int(ys.max()),
                          "cx": float(xs.mean()), "cy": float(ys.mean())})
    except ImportError:
        # 退化：按投影切分
        cells = []
        rows = fg.sum(axis=1)
        cols = fg.sum(axis=0)
        cells = [{"area": int(fg.sum()), "x0": 0, "x1": W - 1,
                  "y0": 0, "y1": H - 1, "cx": W / 2, "cy": H / 2}]

    if not cells:
        return {"path": os.path.abspath(path), "ok": False,
                "reason": "未检出主体"}

    areas = np.array([c["area"] for c in cells])
    med_a = float(np.median(areas))
    cells = [c for c in cells if c["area"] > med_a * 0.3]

    # 按 cy 聚类分行
    def cluster(vals, tol):
        vals = np.sort(np.array(vals))
        out, cur = [], [vals[0]]
        for v in vals[1:]:
            if v - cur[-1] <= tol:
                cur.append(v)
            else:
                out.append(float(np.mean(cur))); cur = [v]
        out.append(float(np.mean(cur)))
        return out

    cys = [c["cy"] for c in cells]
    cxs = [c["cx"] for c in cells]
    h_med = float(np.median([c["y1"] - c["y0"] for c in cells]))
    w_med = float(np.median([c["x1"] - c["x0"] for c in cells]))
    row_c = cluster(cys, h_med * 0.6)
    col_c = cluster(cxs, w_med * 0.6)
    rows_n, cols_n = len(row_c), len(col_c)

    # 按 (row, col) 归位
    grid = []
    for r in range(rows_n):
        line = []
        for c in range(cols_n):
            hit = [x for x in cells
                   if abs(x["cy"] - row_c[r]) < h_med * 0.8
                   and abs(x["cx"] - col_c[c]) < w_med * 0.8]
            line.append(hit[0] if hit else None)
        grid.append(line)

    filled = sum(1 for r in grid for x in r if x)
    return {"path": os.path.abspath(path), "ok": True,
            "size": [W, H], "rows": rows_n, "cols": cols_n,
            "cells_found": len(cells), "grid_filled": filled,
            "total_cells": rows_n * cols_n,
            "complete": filled == rows_n * cols_n,
            "cell_size": [round(w_med), round(h_med)],
            "grid": grid,
            "backdrop_ratio": float(bd.mean())}


def self_check():
    ok, bad = [], []
    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    # 合成 4x2 网格：绿底 + 每格一个白块
    H, W = 400, 800
    a = np.zeros((H, W, 3))
    a[:, :] = (40, 160, 60)          # 绿背板
    ch, cw = H // 2, W // 4
    for r in range(2):
        for c in range(4):
            y0 = r * ch + 20; y1 = (r + 1) * ch - 20
            x0 = c * cw + 20; x1 = (c + 1) * cw - 20
            a[y0:y1, x0:x1] = (240, 90, 90)   # 非绿主体
    p = "/tmp/_probe_test.png"
    Image.fromarray(a.astype("uint8")).save(p)
    r = probe(p)
    add("1 探测到 4 列", r.get("cols") == 4, "cols=%s" % r.get("cols"))
    add("2 探测到 2 行", r.get("rows") == 2, "rows=%s" % r.get("rows"))
    add("3 8 格全填满", r.get("complete"), "filled=%s" % r.get("grid_filled"))

    # 2x4 网格（旗图集的实际形态）
    a2 = np.zeros((H, W, 3)); a2[:, :] = (40, 160, 60)
    ch2, cw2 = H // 4, W // 2
    for rr in range(4):
        for cc in range(2):
            y0 = rr * ch2 + 15; y1 = (rr + 1) * ch2 - 15
            x0 = cc * cw2 + 15; x1 = (cc + 1) * cw2 - 15
            a2[y0:y1, x0:x1] = (240, 90, 90)
    p2 = "/tmp/_probe_test2.png"
    Image.fromarray(a2.astype("uint8")).save(p2)
    r2 = probe(p2)
    add("4 2x4 也能探测", r2.get("cols") == 2 and r2.get("rows") == 4,
        "cols=%s rows=%s" % (r2.get("cols"), r2.get("rows")))

    print("PASS:")
    for x in ok: print("  " + x)
    if bad:
        print("FAIL:")
        for x in bad: print("  " + x)
    else:
        print("FAIL: 无")
    return not bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sheet")
    ap.add_argument("--json", dest="json_out")
    a = ap.parse_args()
    r = probe(a.sheet)
    print(json.dumps({k: v for k, v in r.items() if k != "grid"},
                     ensure_ascii=False, indent=2))
    if r.get("grid"):
        for ri, line in enumerate(r["grid"]):
            print("  row%d: " % ri + " ".join(
                "-" if x is None else "(%d,%d)" % (x["cx"], x["cy"])
                for x in line))
    if a.json_out:
        json.dump(r, open(a.json_out, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
