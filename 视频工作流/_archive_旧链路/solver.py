#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
solver.py —— facade（对外 API 不变，实现已按职责拆到 _solver_*.py）

契约:   contracts/solver_split.md
改前必读: IMPROVE_solver_split.md

拆分（依赖无环，被依赖方禁止反向 import）：
    _solver_base   常量 + 纯算术（零业务依赖）
    _solver_probe  探针/容纳性      → base
    _solver_geom   骨架几何         → base, anchor
    _solver_sheet  图集规划绘制     → base
    _solver_reuse  复用规划         → base, anchor
    _solver_chain  物理求解         → base, geom, physics, anchor, framerate
    _solver_run    编排 run_spec    → base, chain, sheet, reuse
"""
# 问卷段（已先期切出）
from solver_survey import (DRIVE_SOURCES, EXAMPLES, HOWTO, KINDS,
                           PART_ROLES, SLOT_TEMPLATE, assemble,
                           briefing_text, inventory, survey)

from _solver_base import (AMP_BY_LEVEL_DEFAULT, CHAIN_REQUIRED,
                          CHAIN_REQUIRED_SPEC, CONSTANTS, CONTAINMENT,
                          DRAW_PARAM, MAX_MAT_FRAMES, PROBE_MAX, REQUIRED,
                          WIND_DIR_DEFAULT, _grid_for, _interp, wind_sign)
from _solver_probe import (_cell_policy, _conf, containment_check,
                           probe_check, probe_plan)
from _solver_geom import skeleton_points
from _solver_sheet import _draw_one, draw_sheet, sheet_layout, sheet_plan
from _solver_reuse import _reuse_for, additive_offset, layer_plan, reuse_plan
from _solver_chain import (_check_spec, amp_over_L, chain_response,
                           chain_response_multi, flag_lift_deg,
                           frame_durations, loop_seam_ratio, solve,
                           transient_envelope)
from _solver_run import run_spec


def self_check():
    """facade：保留对外 API。实现在 solver_check.py，懒加载破环。"""
    import solver_check
    return solver_check.self_check()


__all__ = [
    "CONSTANTS", "REQUIRED", "solve", "skeleton_points", "draw_sheet",
    "self_check", "run_spec", "sheet_plan", "sheet_layout",
    "probe_plan", "probe_check", "containment_check", "reuse_plan",
    "layer_plan", "additive_offset", "chain_response",
    "chain_response_multi", "frame_durations", "loop_seam_ratio",
    "transient_envelope", "wind_sign", "flag_lift_deg", "amp_over_L",
    "MAX_MAT_FRAMES", "CONTAINMENT", "AMP_BY_LEVEL_DEFAULT", "DRAW_PARAM",
    "WIND_DIR_DEFAULT", "PROBE_MAX",
    "DRIVE_SOURCES", "EXAMPLES", "HOWTO", "KINDS", "PART_ROLES",
    "SLOT_TEMPLATE", "assemble", "briefing_text", "inventory", "survey",
]


if __name__ == "__main__":
    import sys
    if "--run" in sys.argv:
        i = sys.argv.index("--run")
        if i + 1 >= len(sys.argv):
            raise SystemExit("--run 需指定 scene_spec.json 路径")
        for r in run_spec(sys.argv[i + 1]):
            s = r["sheet"]
            print("  %-8s %-9s f=%.3fHz T=%.3fs  渲染帧N=%d  "
                  "素材张数=%d  排布=%d行×%d列  playrate=%.2f"
                  % (r["物体"], r["regime"], r["freq_hz"],
                     r["period_s"], r["frames"], r["mat_frames"],
                     s["rows"], s["cols"], r["playrate"]))
            print("           每格相位(度) %s" % s["phase_map"])
            print("           骨架图集 %s" % r["图集"])
            print("           >>> AI 须生成 %d 张序列帧，按 %d行×%d列 排布，"
                  "第 i 格摆到 phase_map[i] 度"
                  % (r["mat_frames"], s["rows"], s["cols"]))
        raise SystemExit(0)
    import solver_check          # 懒加载破环（业界允许）
    solver_check.self_check()
    if "--build" in sys.argv:
        spec = {"family": "cloth",
                "geometry": {"L": 0.90, "W": 0.30, "t": 2.0e-4},
                "material": {"sigma": 0.062, "E": 5.0e9},
                "fluid": {"U": 12.3},
            "criteria": {"regime_by": "mu",
                         "mu_stable": 0.02, "mu_chaotic": 0.30}}
        a = solve(spec)
        print("\n答案包:")
        for k in ("regime", "freq_hz", "period_s", "frames", "tip_pp_amp_m"):
            print("  %-14s %s" % (k, a[k]))
        print("  dimensionless ", {k: "%.4g" % v for k, v in a["dimensionless"].items()})
        print("  derived       ", {k: "%.5g" % v for k, v in a["derived"].items()})
        fs = draw_sheet(a, "_骨架/solver")
        print("  图集:", fs)
