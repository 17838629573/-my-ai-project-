[FACT] _solver_chain_aux   207行   机器生成，勿手改
doc: chain 求解子函数真身（自拆分前快照恢复）
api:
  L16 flag_lift_deg(U)  # Rule of 4：旗面平均扬起角（离杆的角度）θ ≈ U(mph)×4，钳制 [0,90]。
  L20 amp_over_L(level,criteria)  # 峰峰振幅/特征长度 —— 按风级查表，表由 AI 传入（铁律32）。
  L63 chain_response(links,f_drive,amp_drive,zeta_default)  # 逐级递推：每级驱动 = 上一级末端响应。返回各级 [ω_n, r, M, φ, A]。
  L90 chain_response_multi(links,drives,zeta_default,weights,n_sample)  # 多驱动叠加（例：gait 步频 + wind 风）——**位移域 additive**。
  L148 frame_durations(N,T,tail_ratio,intentional_hold)  # 逐帧时长（秒）。默认**均匀**，不是末帧加长。
  L179 loop_seam_ratio(frames_pose_diff,internal_mean)  # 闭合检验：d(last,first) / 内部相邻差均值。
  L190 transient_envelope(f_n_hz,zeta,t_end,a_peak,a_steady,fps,t0)  # 冲击后回到 a_steady（原扰动量），不是回到 0。
internal:
  L28 _check_spec(spec)
calls_in: chain_response_multi→chain_response
calls_out: CHAIN_REQUIRED_SPEC,REQUIRED,comp,env,errs,lk,math,out,spec,tbl,xs
guard: return@L24, raise@L59, raise@L65, raise@L108, return@L110, raise@L113, raise@L118, raise@L167, return@L169, return@L171, raise@L174, return@L186
up: _solver_base,framerate
down: _solver_chain
