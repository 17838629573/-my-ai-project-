#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
编排：读 scene_spec.json 走完整流程，出每物体答案包。

契约: contracts/solver_split.md
改前必读: IMPROVE_solver_split.md
"""

import json
from _solver_base import WIND_DIR_DEFAULT
from _solver_chain import solve
from _solver_sheet import sheet_layout, draw_sheet
from _solver_reuse import _reuse_for




# ------------------------------------------------------------ --run 入口
def run_spec(path):
    """AI 把物性填进 scene_spec.json 后，跑这个：逐物体 solve + 出骨架图集。"""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    objs = data.get("物体") or []
    if not objs:
        raise ValueError("scene_spec.json 缺 '物体' 列表（先跑 assemble 生成）")
    # 【铁律39】风向全局唯一：scene 顶层 wind.dir_deg 广播给每个物体
    wd = (data.get("wind") or {}).get("dir_deg", WIND_DIR_DEFAULT)
    wd = float(wd)
    u_all = (data.get("wind") or {}).get("U")
    out = []
    for o in objs:
        spec = o.get("spec")
        if not spec:
            raise ValueError("物体 %r 缺 spec（AI 须补齐物性）"
                             % o.get("物体"))
        if "wind_dir" in spec and float(spec["wind_dir"]) != wd:
            raise ValueError("物体 %r 的 wind_dir=%s 与全片 %s 不一致（铁律39）"
                             % (o.get("物体"), spec["wind_dir"], wd))
        spec["wind_dir"] = wd                      # 广播，禁各物体自定
        if u_all is not None and spec.get("source") != "none":
            # 风不只吹旗：行人的衣摆/发丝也受同一风向（lift 由 U 算）
            spec.setdefault("fluid", {})["U"] = float(u_all)
        a = solve(spec)
        nm = o.get("物体", "obj")
        fs = draw_sheet(a, "_骨架/%s" % nm)
        out.append({"物体": nm, "regime": a["regime"],
                    "freq_hz": a["freq_hz"], "period_s": a["period_s"],
                    "frames": a["frames"], "lift_deg": a["lift_deg"],
                    "amp_over_L": a["amp_over_L"],
                    "wind_dir_deg": a["wind_dir_deg"], "图集": fs,
                    # 【铁律41】素材张数与排布必须发给 AI，否则 AI 不知道
                    # 该生成几张图（看 frames=136 会去生 136 张，或随手定）
                    "mat_frames": a["mat_frames"],
                    "playrate": round(a["playrate"], 3),
                    "sheet": sheet_layout(a),
                    # 【铁律52】输出帧数时必须同时问 AI：哪些帧可复用
                    "reuse": _reuse_for(o, spec, a)})
    return out
