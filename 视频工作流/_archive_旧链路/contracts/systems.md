[S] systems @SHOT/sys  d4  in=6  gen:contract_gen
does: systems：常量与编排。已拆出 systems_selfcheck / systems_phys / systems
api: init_skeleton, step_px, scroll_per_frame, matched_playrate, com_vertical_amp, update_animation, self_check
const: REAL_HEIGHT_M, STRIDE_RATIO, STEP_LENGTH_M, CADENCE_SPM, STEPS_PER_SEC, WALK_PERIOD, PLAYRATE_CLAMP, WALK_POSE_TABLE (+5)
impl: 入口 self_check；内部helper 1个
up: framerate,physics,physics_rules,skeleton_runtime,systems_phys,systems_selfcheck,systems_view
down: render_desert_banner,render_gate_banner,render_v4,render_v4_main,systems_phys,systems_selfcheck
edit: framerate,physics,physics_rules,render_desert_banner,render_gate_banner,render_v4,render_v4_main,skeleton_runtime,systems_phys,systems_selfcheck,systems_view   # 改systems须同步核对这些文件
rule: T28
why : IMPROVE_systems.md
