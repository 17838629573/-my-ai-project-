[FACT] solver   94行   机器生成，勿手改
doc: solver.py —— facade（对外 API 不变，实现已按职责拆到 _solver_*.py）
api:
  L39 self_check()  # facade：保留对外 API。实现在 solver_check.py，懒加载破环。
calls_out: solver_check
main: __main__@L59  self_check@L39
up: _solver_base,_solver_chain,_solver_geom,_solver_probe,_solver_reuse,_solver_run,_solver_sheet,solver_check,solver_survey
down: _问卷
