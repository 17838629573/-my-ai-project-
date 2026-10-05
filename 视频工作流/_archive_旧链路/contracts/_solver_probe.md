[S] _solver_probe @SOLVE/chain  d1  in=3  gen:contract_gen
does: 探针与容纳性校验：先 8 格验一致性再升级（铁律48）。
api: containment_check, probe_plan, probe_check
impl: 入口 _cell_policy；内部helper 2个
up: _solver_base
down: _chk_base,_chk_sheet,solver
edit: _chk_base,_chk_sheet,_solver_base,solver   # 改_solver_probe须同步核对这些文件
rule: T18 T31 T47 T48
why : IMPROVE__solver_probe.md
