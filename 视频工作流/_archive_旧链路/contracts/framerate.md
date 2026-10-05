[S] framerate @ATOM/frame  d0  in=19  gen:contract_gen
does: framerate.py —— 帧率/时间基准（单一数据源）
api: frames_for_period, playrate, dt, seconds_to_frames, frame_index, cumulative_starts, duplicate_endpoint, self_check
const: FPS, PLAYRATE_CLAMP
impl: self_check → cumulative_starts → dt → frame_index
down: _chk_base,_chk_physics,_solver_chain,_solver_chain_aux,anchor,build_phase_render (+13)
edit: _chk_base,_chk_physics,_solver_chain,_solver_chain_aux,anchor,build_phase_render,build_util,build_video,film_assemble_render,loop_engine,render_desert_banner,render_gate_banner,render_v4,render_v4_main,subtitle,systems,systems_phys,systems_selfcheck,systems_view   # 改framerate须同步核对这些文件
rule: T28 T29 T30 T46
why : IMPROVE_framerate.md
