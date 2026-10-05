[FACT] _solver_chain   272行   机器生成，勿手改
doc: 物理求解：受迫链响应、regime 判定、周期与帧时长。
api:
  L23 flag_lift_deg(*a,**k)
  L30 amp_over_L(*a,**k)
  L45 solve(spec)  # AI 填物性 -> 代码算全部 -> 答案包（供 AI 拿去生图）
  L239 chain_response(*a,**k)
  L246 chain_response_multi(*a,**k)
  L253 frame_durations(*a,**k)
  L260 loop_seam_ratio(*a,**k)
  L270 transient_envelope(*a,**k)
internal:
  L37 _check_spec(*a,**k)
calls_in: solve→_check_spec, solve→amp_over_L, solve→chain_response_multi, solve→flag_lift_deg, solve→frame_durations
calls_out: DRAW_PARAM,anchor,drv,framerate,g,lk,mat,math,physics,pts,spec
guard: return@L51, raise@L102, raise@L140
up: _family_map,_solver_base,_solver_chain_aux,_solver_geom,anchor,framerate,physics
down: _chk_base,_chk_chain,_chk_motion,_chk_multi,_chk_pack,_chk_physics,_chk_sheet,_solver_run,solver
