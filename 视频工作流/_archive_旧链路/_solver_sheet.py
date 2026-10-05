#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
图集规划与绘制：网格选择、布局、骨架图集渲染。

契约: contracts/solver_split.md
改前必读: IMPROVE_solver_split.md
"""

import math
import cv2
import numpy as np
from _solver_base import CONTAINMENT, _grid_for




def sheet_layout(ans):
    """【铁律41】素材张数 + 排布 + 每格相位，代码算出来必须发给 AI。

    AI 生图时按 rows×cols 排布画 count 格，第 i 格摆到 phase_map[i] 度。
    """
    n = int(ans["mat_frames"])
    rows, cols = _grid_for(n)
    return {"rows": rows, "cols": cols, "count": n,
            "grids": rows * cols,
            "phase_map": [round(360.0 * i / n, 2) for i in range(n)],
            "order": "行优先，第 i 格 = 相位 phase_map[i] 度",
            "playrate": round(ans["frames"] / float(n), 3)}




def sheet_plan(ans, spec=None, max_cells=None, cell_px=None, bg=None,
               aspect=None):
    """【铁律54-57】把「生成张数」翻译成「画几张图集、每张几格、每格多大」。

    AI 只按本函数输出生图，不自己决定帧数/网格/格尺寸。
    """
    gen = int(ans.get("gen_frames") or ans.get("gen_n") or ans["mat_frames"])
    mat = int(ans["mat_frames"])
    play = int(ans["frames"])

    # 铁律56：格数上限是模型能力，不是代码常量，默认 16（GPT-Image 先8后16）
    mc = int(max_cells) if max_cells else int(
        (spec or {}).get("criteria", {}).get("max_cells", 16))
    if mc < 1:
        raise ValueError("max_cells 必须 >= 1，收到 %r" % (max_cells,))

    # 铁律57：长条物体走 strip（lobehub sprite-forge）
    if aspect is None:
        g = (spec or {}).get("geometry", {}) if spec else {}
        L_, W_ = float(g.get("L", 0) or 0), float(g.get("W", 0) or 0)
        aspect = (L_ / W_) if (W_ > 0 and L_ > 0) else 1.0
    layout = "strip" if aspect > 2.0 else "grid"

    # 格尺寸：默认 256，strip 用宽格
    if cell_px is None:
        cell_px = [512, 256] if layout == "strip" else [256, 256]
    cw, ch = int(cell_px[0]), int(cell_px[1])
    pad = 2  # spritesheetgenerator：防 texture bleeding
    bg = bg or "#FF00FF"

    # 每张容量：由「格尺寸 + 2048 上限 + max_cells」三者取小
    # （lobehub：strip 是 1x3/1x4，不是 1x16——塞太满会把每格压成糊）
    cap_x = max(1, 2048 // (cw + pad))
    cap_y = max(1, 2048 // (ch + pad))
    if layout == "strip":
        cap = min(mc, cap_x)          # 1 行
    else:
        cap = min(mc, cap_x * cap_y)

    sheets, idx0 = [], 0
    while idx0 < gen:
        take = min(cap, gen - idx0)
        if layout == "strip":
            rows, cols = 1, take
        else:
            rows, cols = _grid_for(take)
        W_ = cols * cw + (cols - 1) * pad
        H_ = rows * ch + (rows - 1) * pad
        # 兜底：仍超 2048 才降格尺寸（正常不会走到）
        while max(W_, H_) > 2048 and min(cw, ch) > 16:
            cw, ch = int(cw * 0.8), int(ch * 0.8)
            W_ = cols * cw + (cols - 1) * pad
            H_ = rows * ch + (rows - 1) * pad
        sheets.append({
            "idx": len(sheets), "rows": rows, "cols": cols,
            "cells": rows * cols, "cell_px": [cw, ch],
            "sheet_px": [W_, H_], "padding": pad, "layout": layout,
            "bg": bg,
            "frame_range": [idx0, idx0 + take - 1],
            "phase_map": [round(360.0 * i / mat, 2)
                          for i in range(idx0, idx0 + take)],
        })
        idx0 += take

    return {
        "gen_frames": gen, "mat_frames": mat, "play_frames": play,
        "max_cells": mc, "n_sheets": len(sheets), "sheets": sheets,
        "layout": layout, "aspect": round(aspect, 3),
        "shared_reference": "所有图集共用同一张身份参考图（铁律55）",
        "order": "行优先；sheet k 的第 j 格 = 第 (frame_range[0]+j) 帧",
    }




# ------------------------------------------------------------ 骨架图集
def draw_sheet(ans, prefix, cw=480, ch=210, cols=None, rows=None):
    """按答案包的几何画骨架图集（供图生图作参考）"""
    if cols is None or rows is None:
        _r_, _c_ = _grid_for(int(ans["mat_frames"]))
        rows = rows if rows is not None else _r_
        cols = cols if cols is not None else _c_
    # 【铁律17】先清旧图集：帧数变了旧片会残留并被误当本次产物（实测
    # N 从 176 降到 39 时，20 张旧图只剩 5 张被覆盖，其余 15 张全是垃圾）
    import glob as _glob, os as _os
    for p in _glob.glob(prefix + "*.png"):
        try:
            _os.remove(p)
        except OSError:
            pass
    # 【铁律40】素材张数 != 渲染帧数。素材张数只决定视觉平滑度，
    # 摆动频率由物理周期 T 决定：一个周期 = frames 个渲染帧 = mat_frames
    # 张素材循环一遍，播放速率 playrate = frames / mat_frames。
    # 之前把两者混为一谈，为了凑 39 帧拆成 5 张图集 -> 跨调用一致性崩
    # （实测跨图集形状差异是同图集内的 1.77 倍），这才是真正的"制造帧数"。
    N = ans["mat_frames"]
    dr = ans["draw"]
    # 【自适应缩放】按全部相位的真实包围盒统一缩放，保证曲线完整落在格内
    # 且尽量大。旧代码用经验 vfactor 估高度，实测 lift=30° 时末端 y=-28px
    # 被画到框外，只剩根部可见 -> 骨架图里旗只有 120px 宽、质心几乎不动，
    # 模型根本无从跟随（铁律1：必须有命令输出，不能"看着对"）。
    pg = ans["phase_geometry"][:N]
    xs = [p[0] for c in pg for p in c]
    ys = [p[1] for c in pg for p in c]
    bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
    bw = max(bx1 - bx0, 1e-6)
    bh = max(by1 - by0, 1e-6)
    # 骨架有宽度（垂直方向偏移 ±W_px/2）与描边，包围盒须把这些也算进去，
    # 否则缩放后仍会溢出可用区（实测 fill_w 到 0.95 > 上限 0.80）
    hw = 0.5 * dr["W_over_L"]
    bx0 -= hw
    bx1 += hw
    by0 -= hw
    by1 += hw
    bw = max(bx1 - bx0, 1e-6)
    bh = max(by1 - by0, 1e-6)
    # 【铁律47】可用区域由容纳性参数导出，不再写死 0.88/0.84：
    #  宽上限 = 格宽 × max_fill_w，且四边各留 margin_px
    avail_w = min(cw * CONTAINMENT["max_fill_w"], cw - 2 * CONTAINMENT["margin_px"])
    avail_h = min(ch * CONTAINMENT["max_fill_h"], ch - 2 * CONTAINMENT["margin_px"])
    L_px = int(min(avail_w / bw, avail_h / bh))
    # 内容顶端恒为 pad_t（oy 已含 -by0），故底端相对 oy 的偏移是 by1*L_px，
    # 不是 bh*L_px —— 用 bh 会多算一个 |by0|*L_px，把杆顶出格底（实测底边距 0）。
    bh_px = by1 * L_px
    # 杆在左(或右)侧，把包围盒平移进格内
    pad_l = cw * 0.06
    pad_t = ch * 0.10
    ox = int(pad_l + (0.0 - bx0) * L_px) if dr.get("dir_sign", 1.0) > 0 \
        else int(cw - pad_l - (0.0 - bx0) * L_px)
    oy = int(pad_t + (0.0 - by0) * L_px)
    half_w = 0.5 * dr["W_over_L"]
    files = []
    sheet = 0
    idx = 0
    while idx < N:
        grid = np.full((ch * rows, cw * cols, 3), 255, np.uint8)
        for i in range(cols * rows):
            if idx >= N:
                break
            r, c = divmod(i, cols)
            grid[r * ch:(r + 1) * ch, c * cw:(c + 1) * cw] = \
                _draw_one(ans["phase_geometry"][idx], idx, cw, ch, dr,
                          L_px, half_w, ox, oy, bh_px)
            idx += 1
        sheet += 1
        p = "%s%d.png" % (prefix, sheet)
        cv2.imwrite(p, grid)
        files.append(p)
    return files




def _draw_one(curve, idx, cw, ch, dr, L_px, half_w, ox=None, oy=None,
              bh_px=None):
    img = np.full((ch, cw, 3), 255, np.uint8)
    # 【铁律39】风向朝左时，旗杆改靠右，否则骨架画到框外
    sg = dr.get("dir_sign", 1.0)
    if ox is None:
        ox = int(cw * 0.88) if sg < 0 else int(cw * 0.12)
    if oy is None:
        oy = int(ch * 0.22)
    if bh_px is None:
        bh_px = ch * 0.66
    W_px = max(3, int(L_px * dr["W_over_L"]))
    # 旗杆：垂直、所有相位一致。旧代码用 ch*0.10 / ch*0.90 固定比例，
    # 与自适应缩放后的包围盒无关 -> 骨架高度被杆撑到 0.885 > 上限 0.80。
    # 改为杆的上下端严格对齐主体包围盒，整体再统一缩放，保证容纳性。
    pw = max(4, int(cw * 0.022))
    pole_top = int(oy)
    pole_bot = int(oy + bh_px)
    cv2.rectangle(img, (ox - pw // 2, pole_top),
                  (ox + pw // 2, pole_bot), (60, 60, 60), -1)
    # 幡身
    poly = [(int(ox + x * L_px), int(oy + y * L_px)) for x, y in curve]
    up, dn = [], []
    for i, (x, y) in enumerate(poly):
        if i == 0:
            dx, dy = poly[1][0] - poly[0][0], poly[1][1] - poly[0][1]
        else:
            dx, dy = poly[i][0] - poly[i - 1][0], poly[i][1] - poly[i - 1][1]
        n = math.hypot(dx, dy) or 1
        nx, ny = -dy / n, dx / n
        up.append((int(x + nx * W_px / 2), int(y + ny * W_px / 2)))
        dn.append((int(x - nx * W_px / 2), int(y - ny * W_px / 2)))
    cv2.fillPoly(img, [np.array(up + dn[::-1], np.int32)], (70, 70, 220))
    cv2.polylines(img, [np.array(poly, np.int32)], False, (40, 40, 160), 2)
    # 【铁律47】图集内禁文字（业界：no text）—— 旧代码在 (6,20) 画帧号，
    # 既是前景又贴边，容纳性恒 FAIL。帧序由 sheet_layout 的 phase_map 给 AI。
    return img
