[FACT] _solver_run   59行   机器生成，勿手改
doc: 编排：读 scene_spec.json 走完整流程，出每物体答案包。
api:
  L20 run_spec(path)  # AI 把物性填进 scene_spec.json 后，跑这个：逐物体 solve + 出骨架图集。
calls_out: data,json,o,out,spec
guard: raise@L25
up: _solver_base,_solver_chain,_solver_reuse,_solver_sheet
down: _chk_base,_chk_motion,solver
