[S] _chk_motion @SOLVE/check  d7  in=1  gen:contract_gen
does: 检查域5：run_spec 契约/扬角/振幅比/风向全局一致。
api: check
impl: 入口 check
up: _chk_base,_solver_base,_solver_chain,_solver_run,physics
down: solver_check
edit: _chk_base,_solver_base,_solver_chain,_solver_run,physics,solver_check   # 改_chk_motion须同步核对这些文件
rule: T32 T39
why : IMPROVE__chk_motion.md
