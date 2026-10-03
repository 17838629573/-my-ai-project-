# deps.md — 模块依赖登记表
# 由 deps_sync.py 自动从源码 import 反推 + 拓扑分层，禁止手填
# 改了任何 import 后重跑: python deps_sync.py --write

# L0 L0 原子层（无本项目依赖）
_family_map -> (无)
_px -> (无)
composite -> (无)
deps_sync -> (无)
framerate -> (无)
gate_doc -> (无)
gate_size -> (无)
gen_chain -> (无)
groundline -> (无)
param_decl -> (无)
path -> (无)
placement -> (无)
prompt_tpl -> (无)
scale_map -> (无)
water -> (无)

# L1 L1 计算层
anchor -> framerate
cloth_aero -> param_decl
loop_engine -> framerate
path_align -> path
rain_layer -> _common, water
subtitle -> framerate
wind_response -> _common

# L2 L2 规划层
cloth_wire -> cloth_aero, param_decl, wind_response
wind_sway -> wind_response

# L3 L3 渲染/编排层
_split_sheet -> chroma
build_video -> build_phase_asset, build_phase_gen, build_phase_render, build_phase_setup, build_phase_time, build_util, chroma, cloth_wire, composite, framerate, genqueue, groundline, path, placement, scale_map, shot_plan, wind_sway
chroma -> chroma_selfcheck
chroma_selfcheck -> chroma
driver -> genqueue
enforce -> enforce_cmds
film_assemble -> character_sheet, chroma, film_assemble_render, photo_rules, subtitle
film_assemble_render -> film_assemble, framerate
genqueue -> pose, prompt_tpl
pose -> pose_selfcheck
pose_prompt -> pose
pose_selfcheck -> pose
render_v4 -> actors, film_assemble, framerate, loop_engine, photo_rules, physics, render_v4_main, systems
render_v4_main -> character_sheet, render_v4
run_batch -> enforce
shot_plan -> path, placement, scale_map, wind_sway
skeleton_runtime -> skeleton_runtime_selfcheck
skeleton_runtime_selfcheck -> skeleton_runtime
solver -> _solver_base, _solver_chain, _solver_geom, _solver_probe, _solver_reuse, _solver_run, _solver_sheet, solver_check, solver_survey
solver_check -> _chk_assemble, _chk_base, _chk_chain, _chk_motion, _chk_multi, _chk_pack, _chk_physics, _chk_reuse, _chk_sheet, _chk_survey
systems -> framerate, physics, physics_rules, skeleton_runtime, systems_phys, systems_selfcheck, systems_view
systems_selfcheck -> framerate, physics, physics_rules, skeleton_runtime, systems
骨架_行走 -> pose

# X X 休眠层（一次性脚本/归档/无自检）
_actor_audit -> character_sheet
_audit_dead -> (无)
_audit_dup -> (无)
_build32 -> _layer_style
_chk_assemble -> _chk_base
_chk_base -> _solver_base, _solver_chain, _solver_probe, _solver_reuse, _solver_run, _solver_sheet, anchor, framerate, physics, solver_survey
_chk_chain -> _chk_base
_chk_motion -> _chk_base
_chk_multi -> _chk_base
_chk_pack -> _chk_base
_chk_physics -> _chk_base
_chk_reuse -> _chk_base
_chk_sheet -> _chk_base
_chk_survey -> _chk_base
_common -> (无)
_common_selfcheck -> _common
_extract2 -> (无)
_extract_tool -> (无)
_import_sweep -> (无)
_layer_style -> (无)
_migrate_common -> (无)
_solver_base -> (无)
_solver_chain -> _family_map, _solver_base, _solver_chain_aux, _solver_geom, anchor, framerate, physics
_solver_chain_aux -> _solver_base, framerate
_solver_geom -> _solver_base, anchor
_solver_probe -> _solver_base
_solver_reuse -> (无)
_solver_run -> _solver_base, _solver_chain, _solver_reuse, _solver_sheet
_solver_sheet -> _solver_base
_split_plan -> (无)
_split_tool -> (无)
_问卷 -> solver
actors -> physics
build_phase_asset -> _px, build_util, chroma
build_phase_gen -> _common, build_util, genqueue, pose, prompt_tpl, shot_plan, wind_response
build_phase_render -> build_util, framerate, path
build_phase_setup -> _px, build_util, cloth_wire, groundline, path, path_align, scale_map, wind_response
build_phase_time -> wind_response
build_util -> _common, chroma, cloth_wire, composite, framerate, genqueue, groundline, path, placement, pose, scale_map, shot_plan, wind_sway
character_sheet -> chroma, photo_rules
enforce_cmds -> character_sheet, chroma, enforce
environment -> actors, physics, physics_rules
gate_module -> (无)
motion_lib -> (无)
photo_rules -> (无)
physics -> _common, _px
physics_rules -> _common
render_desert_banner -> actors, character_sheet, framerate, physics, render_v4, systems
render_gate_banner -> actors, character_sheet, framerate, physics, render_v4, systems
run_gen_queue -> build_phase_gen
solver_survey -> driver
systems_phys -> framerate, physics, physics_rules, skeleton_runtime, systems
systems_view -> framerate, physics, physics_rules, skeleton_runtime, subtitle
占位音轨 -> (无)

