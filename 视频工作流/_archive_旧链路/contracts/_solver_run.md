[S] _solver_run @SOLVE/sheet  d4  in=3  gen:contract_gen
does: 编排：读 scene_spec.json 走完整流程，出每物体答案包。
api: run_spec
impl: 入口 run_spec
up: _solver_base,_solver_chain,_solver_reuse,_solver_sheet
down: _chk_base,_chk_motion,solver
edit: _chk_base,_chk_motion,_solver_base,_solver_chain,_solver_reuse,_solver_sheet,solver   # 改_solver_run须同步核对这些文件
rule: T39 T41 T52
why : IMPROVE__solver_run.md
