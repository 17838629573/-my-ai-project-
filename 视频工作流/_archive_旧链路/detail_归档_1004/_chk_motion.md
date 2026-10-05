[FACT] _chk_motion   88行   机器生成，勿手改
doc: 检查域5：run_spec 契约/扬角/振幅比/风向全局一致。
api:
  L18 check(ctx)
calls_out: _os,_os2,json,physics,tempfile,tf,tf2
up: _chk_base,_solver_base,_solver_chain,_solver_run,physics
down: solver_check
