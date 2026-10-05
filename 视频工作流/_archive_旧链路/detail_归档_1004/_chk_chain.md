[FACT] _chk_chain   91行   机器生成，勿手改
doc: 检查域2：chain 共振/逐级递推/transient 稳态与包络衰减。
api:
  L16 check(ctx)
calls_out: math,spec
up: _chk_base,_solver_chain
down: solver_check
