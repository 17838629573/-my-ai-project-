#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""hier —— 分层表（大/中/小模块归属）。由 contract_gen.py 拆出以过体积门禁。

人工维护：语义分组，机器不猜。改动后须重跑 contract_gen.py。
"""

HIER = {
    "ATOM": {
        "math":  ["_common", "_common_selfcheck", "_px"],
        "phys":  ["physics", "physics_rules",
              "zmp", "contact_plan", "contact_ik", "oneshot"],  # 交互域
        "frame": ["framerate", "_loopspec"],
        "aero":  ["cloth_aero", "cloth_wire", "wind_response", "wind_sway"],
        "water": ["water", "rain_layer"],
        "cam":   ["_camera", "_camera_selfcheck", "_perspective", "_surface",
              "_wall_geom"],  # 墙顶/墙深几何（自 _surface 拆出）
        "path":  ["path", "path_align", "groundline", "scale_map", "placement", "anchor",
              "_ground_arc"],   # 地面坐标反投影/世界弧长推进（V2）
        "img":   ["chroma", "chroma_selfcheck", "composite", "_layer_style", "_matting",
              "_despill"],  # 绿幕溢色反解（Aksoy 凸包解混）
        "rule":  ["photo_rules", "param_decl", "actors", "_family_map"],
    },
    "SOLVE": {
        "spec":  ["solver_survey", "driver", "gen_chain"],
        "base":  ["_solver_base", "_solver_chain_aux", "_solver_geom"],
        "chain": ["_solver_chain", "_solver_probe"],
        "sheet": ["_solver_sheet", "_solver_reuse", "_solver_run"],
        "check": ["_chk_base", "_chk_physics", "_chk_chain", "_chk_assemble",
                  "_chk_survey", "_chk_motion", "_chk_multi", "_chk_sheet",
                  "_chk_reuse", "_chk_pack", "solver_check"],
    },
    "BUILD": {
        "util":  ["build_util"],
        "phase": ["build_phase_time", "build_phase_setup", "build_phase_asset",
                  "build_phase_gen", "build_phase_render"],
    },
    "SHOT": {
        "skel":  ["skeleton_runtime", "skeleton_runtime_selfcheck", "pose",
                  "pose_selfcheck", "pose_prompt",
                  "foot_lock", "puppet"],   # puppet=部件化绑定(V6补帧)
        "sheet": ["character_sheet"],
        "sys":   ["systems", "systems_phys", "systems_view", "systems_selfcheck"],
        "loop":  ["loop_engine"],
        "sub":   ["subtitle"],
        "gen":   ["genqueue", "prompt_tpl", "shot_plan"],
        "assemble": ["film_assemble", "film_assemble_render"],
    },
    "GATE": {
        "core":  ["enforce", "enforce_cmds"],
        "size":  ["gate_module", "gate_doc", "gate_size"],
    },
    "OPS": {
        "audit": ["_audit_dead", "_audit_dup", "_import_sweep", "_actor_audit"],
        "tool":  ["_extract_tool", "_extract2", "_migrate_common",
                  "_split_sheet", "_split_tool", "_split_plan"],
        "demo":  ["render_gate_banner", "render_desert_banner", "_build32",
                  "run_batch", "run_gen_queue", "environment", "motion_lib",
                  "_问卷", "占位音轨", "骨架_行走"],
    },
}
TOP = {"SOLVE": ["solver"], "BUILD": ["build_video"],
       "SHOT": ["render_v4", "render_v4_main"]}

LDESC = {
    "ATOM":  "原子层：无业务语义的纯函数与常量，被一切模块依赖",
    "SOLVE": "物理求解：AI填物性 → 代码算无量纲数/周期/帧数 → 答案包 → AI生图",
    "BUILD": "出片合成：素材 → 基线/比例尺/路径 → 逐帧合成 → mp4",
    "SHOT":  "镜头装配：叙事意图 → 解机位 → 骨架动画 → 装配 → 渲染",
    "GATE":  "门禁：唯一裁判，判定必须带命令输出",
    "OPS":   "手动工具与审计：入度0 属设计（脚本不被 import），非死代码",
}

