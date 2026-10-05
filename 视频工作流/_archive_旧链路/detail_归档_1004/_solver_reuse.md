[FACT] _solver_reuse   181行   机器生成，勿手改
doc: 复用规划：镜像/偏移/分层，减生图张数。
api:
  L69 reuse_plan(series,criteria,anchor,axis)  # 复用规划：播放帧数（物理定） vs 需生成帧数（复用定）。
  L136 layer_plan(spec)  # 分层规划（铁律53）：base 生成一次，overlay 挂 anchor，摆动走 additive。
  L172 additive_offset(base_curve,drive_curve,weight)  # additive offset curve（铁律53）：base 一次生成，摆动算出来叠上去。
internal:
  L14 _reuse_for(obj,spec,ans)
calls_in: _reuse_for→reuse_plan
calls_out: base,crit,lys,o,obj,out,spec
guard: return@L39, raise@L77, raise@L80, raise@L88, raise@L143, raise@L178
up: -
down: _chk_base,_chk_reuse,_solver_run,solver
