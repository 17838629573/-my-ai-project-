# deps.md — 模块依赖登记表
# 由 depgraph.py 自动从源码 import 反推，禁止手填
# 改了任何 import 后重跑: python3 depgraph.py
# 校验是否漂移: python3 depgraph.py --check

# L0 原子层（无本项目依赖）
_audit_dead -> (无)
_audit_dup -> (无)
_common -> (无)
_despill -> (无)
_extract2 -> (无)
_extract_tool -> (无)
_family_map -> (无)
_ground_arc -> (无)
_import_sweep -> (无)
_loopspec -> (无)
_migrate_common -> (无)
_perspective -> (无)
_px -> (无)
_solver_base -> (无)
_solver_reuse -> (无)
_split_plan -> (无)
_split_tool -> (无)
composite -> (无)
contact_ik -> (无)
contact_plan -> (无)
foot_lock -> (无)
framerate -> (无)
gate_doc -> (无)
gate_module -> (无)
gate_size -> (无)
gen_chain -> (无)
groundline -> (无)
motion_lib -> (无)
oneshot -> (无)
param_decl -> (无)
path -> (无)
photo_rules -> (无)
placement -> (无)
prompt_tpl -> (无)
scale_map -> (无)
water -> (无)
zmp -> (无)
占位音轨 -> (无)

# L1
_camera -> (无)
_common_selfcheck -> _common
_layer_style -> (无)
_matting -> (无)
_solver_chain_aux -> _solver_base, framerate
_solver_probe -> _solver_base
_solver_sheet -> _solver_base
_wall_geom -> _perspective
anchor -> (无)
cloth_aero -> param_decl
loop_engine -> (无)
path_align -> (无)
physics -> (无)
physics_rules -> (无)
rain_layer -> _common, water
subtitle -> (无)
wind_response -> (无)

# L2
_build32 -> _layer_style
_camera_selfcheck -> _camera
_solver_geom -> _solver_base, anchor
_surface -> _perspective, _wall_geom, param_decl
actors -> (无)
build_phase_time -> wind_response
cloth_wire -> cloth_aero, param_decl, wind_response
wind_sway -> wind_response

# L3
_solver_chain -> _family_map, _solver_base, _solver_geom, anchor, framerate, physics
environment -> physics, physics_rules
shot_plan -> path, placement, scale_map, wind_sway

# L4
_solver_run -> _solver_base, _solver_chain, _solver_reuse, _solver_sheet

# L37
_actor_audit -> character_sheet
_chk_assemble -> _chk_base, solver_survey
_chk_base -> _solver_base, _solver_chain, _solver_probe, _solver_reuse, _solver_run, _solver_sheet, anchor, framerate, physics, solver_survey
_问卷 -> solver
build_phase_render -> _ground_arc, build_util, framerate, path
build_phase_setup -> _px, build_util, cloth_wire, groundline, path, path_align, scale_map, wind_response
driver -> (无)

# L38
_chk_chain -> _chk_base, _solver_chain
_chk_motion -> _chk_base, _solver_base, _solver_chain, _solver_run, physics
_chk_multi -> _chk_base, _solver_chain
_chk_pack -> _chk_base, _solver_chain, _solver_sheet
_chk_physics -> _chk_base, _solver_base, _solver_chain, _solver_sheet, framerate
_chk_reuse -> _chk_base, _solver_reuse
_chk_sheet -> _chk_base, _solver_chain, _solver_probe, _solver_sheet
_chk_survey -> _chk_base, solver_survey
_split_sheet -> chroma
build_phase_asset -> _px, build_util, chroma
build_phase_gen -> build_util, genqueue, prompt_tpl, shot_plan, wind_response
build_util -> chroma, cloth_wire, composite, framerate, genqueue, groundline, path, placement, scale_map, shot_plan, wind_sway
character_sheet -> chroma
genqueue -> prompt_tpl
skeleton_runtime -> (无)
solver -> _solver_base, _solver_chain, _solver_geom, _solver_probe, _solver_reuse, _solver_run, _solver_sheet, solver_survey
solver_survey -> (无)

# L39
build_video -> _ground_arc, build_phase_asset, build_phase_gen, build_phase_render, build_phase_setup, build_phase_time, build_util, chroma, cloth_wire, composite, framerate, genqueue, groundline, path, placement, scale_map, shot_plan, wind_sway
chroma -> _despill, composite
enforce -> (无)
pose -> foot_lock
run_gen_queue -> build_phase_gen
skeleton_runtime_selfcheck -> skeleton_runtime
solver_check -> _chk_assemble, _chk_base, _chk_chain, _chk_motion, _chk_multi, _chk_pack, _chk_physics, _chk_reuse, _chk_sheet, _chk_survey
systems_view -> composite, framerate, physics, physics_rules, skeleton_runtime

# L40
chroma_selfcheck -> chroma
enforce_cmds -> enforce
film_assemble -> character_sheet, chroma, photo_rules, subtitle
pose_prompt -> (无)
pose_selfcheck -> pose
puppet -> (无)
render_desert_banner -> actors, framerate, physics, render_v4, systems
render_gate_banner -> actors, framerate, physics, render_v4, systems
run_batch -> (无)
systems -> framerate, physics, physics_rules, skeleton_runtime, systems_phys, systems_view
骨架_行走 -> pose

# L41
film_assemble_render -> character_sheet, chroma, film_assemble, photo_rules, subtitle
render_v4 -> actors, film_assemble, framerate, loop_engine, photo_rules, physics, systems
systems_phys -> framerate, physics, physics_rules, skeleton_runtime
systems_selfcheck -> framerate, physics, physics_rules, skeleton_runtime

# L42
render_v4_main -> actors, film_assemble, framerate, photo_rules, physics, render_v4, systems

# 懒加载边：函数内 / __main__ 内 import，被 import 时不执行，不构成环
_camera -> _perspective [runtime]
_layer_style -> composite [runtime]
_matting -> composite [runtime]
_solver_chain -> _solver_chain_aux [runtime]
actors -> physics [runtime]
anchor -> framerate [runtime]
build_phase_gen -> _common [runtime]
build_phase_gen -> pose [runtime]
build_util -> _common [runtime]
build_util -> pose [runtime]
build_video -> _surface [runtime]
character_sheet -> photo_rules [runtime]
chroma -> chroma_selfcheck [runtime]
driver -> genqueue [runtime]
enforce -> enforce_cmds [runtime]
enforce_cmds -> character_sheet [runtime]
enforce_cmds -> chroma [runtime]
environment -> actors [runtime]
film_assemble -> film_assemble_render [runtime]
film_assemble_render -> framerate [runtime]
genqueue -> pose [runtime]
loop_engine -> framerate [runtime]
path_align -> path [runtime]
physics -> _common [runtime]
physics -> _px [runtime]
physics_rules -> _common [runtime]
pose -> pose_selfcheck [runtime]
pose_prompt -> pose [runtime]
puppet -> _common [runtime]
puppet -> pose [runtime]
render_desert_banner -> character_sheet [runtime]
render_gate_banner -> character_sheet [runtime]
render_v4 -> render_v4_main [runtime]
render_v4_main -> character_sheet [runtime]
run_batch -> enforce [runtime]
skeleton_runtime -> skeleton_runtime_selfcheck [runtime]
solver -> solver_check [runtime]
solver_survey -> driver [runtime]
subtitle -> framerate [runtime]
systems -> systems_selfcheck [runtime]
systems_phys -> systems [runtime]
systems_selfcheck -> systems [runtime]
systems_view -> subtitle [runtime]
wind_response -> _common [runtime]

# 模块 115 个 | 边 207 条 | 环 0 个
