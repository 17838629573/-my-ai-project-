[S] _solver_chain @SOLVE/chain  d3  in=9  gen:contract_gen
does: 物理求解：受迫链响应、regime 判定、周期与帧时长。
api: flag_lift_deg, amp_over_L, solve, chain_response, chain_response_multi, frame_durations, loop_seam_ratio, transient_envelope
impl: 入口 flag_lift_deg；内部helper 1个
up: _family_map,_solver_base,_solver_chain_aux,_solver_geom,anchor,framerate,physics
down: _chk_base,_chk_chain,_chk_motion,_chk_multi,_chk_pack,_chk_physics (+3)
edit: _chk_base,_chk_chain,_chk_motion,_chk_multi,_chk_pack,_chk_physics,_chk_sheet,_family_map,_solver_base,_solver_chain_aux,_solver_geom,_solver_run,anchor,framerate,physics,solver   # 改_solver_chain须同步核对这些文件
rule: T20 T29 T32 T34 T42 T43 T54 T88
why : IMPROVE__solver_chain.md
