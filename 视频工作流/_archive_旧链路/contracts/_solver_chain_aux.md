[S] _solver_chain_aux @SOLVE/base  d1  in=1  gen:contract_gen
does: chain 求解子函数真身（自拆分前快照恢复）
api: flag_lift_deg, amp_over_L, chain_response, chain_response_multi, frame_durations, loop_seam_ratio, transient_envelope
impl: 入口 flag_lift_deg；内部helper 1个
up: _solver_base,framerate
down: _solver_chain
edit: _solver_base,_solver_chain,framerate   # 改_solver_chain_aux须同步核对这些文件
rule: T20 T31 T32 T42 T43
why : IMPROVE__solver_chain_aux.md
