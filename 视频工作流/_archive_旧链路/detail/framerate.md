[FACT] framerate   308行   机器生成，勿手改
doc: framerate.py —— 帧率/时间基准（单一数据源）
api:
  L26 frames_for_period(T_phys,fps)  # 铁律29：周期(s) -> 应有序列帧数。禁止手填帧数。
  L33 playrate(n_have,n_want,clamp)  # 素材帧数 n_have vs 物理应有帧数 n_want。
  L50 dt(fps)  # 物理时间步。禁止写死 1/60（铁律28）。
  L55 seconds_to_frames(sec,fps)
  L60 frame_index(t,durations)  # 当前时刻该显示第几张素材 -> (i0, i1, f)。
  L85 cumulative_starts(durations)  # 前缀和边界（业界要求：从 index 算，不累加）。
  L94 duplicate_endpoint(frames)  # 末帧是否≈首帧（循环接缝重复的端点）。
  L110 self_check()
calls_in: self_check→cumulative_starts, self_check→dt, self_check→frame_index, self_check→frames_for_period, self_check→playrate
calls_out: accs,assigns,ast,bad,fn,math,np,os,out
guard: return@L28, raise@L38, raise@L42, raise@L70, raise@L72, return@L100, return@L104
const: FPS=60, PLAYRATE_CLAMP[2]
main: __main__@L306  self_check@L110
up: -
down: _chk_base,_chk_physics,_solver_chain,_solver_chain_aux,anchor,build_phase_render,build_util,build_video,film_assemble_render,loop_engine,render_desert_banner,render_gate_banner,render_v4,render_v4_main,subtitle,systems,systems_phys,systems_selfcheck,systems_view
