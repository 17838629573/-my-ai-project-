[S] driver @SOLVE/spec  d4  in=1  gen:contract_gen
does: driver —— 先判族，再选驱动器（铁律77-80）
api: classify, plan, briefing, self_check
const: FAMILIES, EXAMPLES, HARDCODE_BAN
impl: self_check → _chk → _scan_hardcode → _scan_targets；内部helper 4个
up: genqueue
down: solver_survey
edit: genqueue,solver_survey   # 改driver须同步核对这些文件
rule: T29 T36 T37 T73 T77 T78 T79 T80 T81 T82 T83 T95 T96
why : IMPROVE_driver.md
