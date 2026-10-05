[FACT] systems_phys   150行   机器生成，勿手改
doc: systems 的自检/检查逻辑（由 _extract_tool.py 从 systems.py 抽出）
api:
  L17 init_physics(ctx)
  L51 update_physics(ctx,i,t)
  L111 update_movables(ctx,i,t)
calls_out: ctx,framerate,math,np,p,ph,seqs
guard: raise@L31
up: framerate,physics,physics_rules,skeleton_runtime,systems
down: systems
