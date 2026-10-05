[TOP] solver @SOLVE/_top  d9  in=1  gen:contract_gen
does: solver.py —— facade（对外 API 不变，实现已按职责拆到 _solver_*.py）
api: self_check
impl: 入口 self_check
up: _solver_base,_solver_chain,_solver_geom,_solver_probe,_solver_reuse,_solver_run,_solver_sheet,solver_check,solver_survey
down: _问卷
edit: _solver_base,_solver_chain,_solver_geom,_solver_probe,_solver_reuse,_solver_run,_solver_sheet,_问卷,solver_check,solver_survey   # 改solver须同步核对这些文件
why : IMPROVE_solver.md
