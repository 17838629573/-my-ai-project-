[S] enforce @GATE/core  d4  in=2  gen:contract_gen
does: 执行门禁（契约强制性检查）
api: parse_deps, module_exists, static_deps, find_cycle, local_imports, cmd_status, cmd_validate, cmd_check_contract, cmd_check_deps, cmd_check_evidence, cmd_gate, cmd_check_assets (+1)
const: BASE, DEPS, WORKLOG, ACTIVE_SECTIONS, DORMANT_SECTIONS, MODULES
impl: main → cmd_check_assets → cmd_check_contract → cmd_check_deps
up: enforce_cmds
down: enforce_cmds,run_batch
edit: enforce_cmds,run_batch   # 改enforce须同步核对这些文件
rule: T1
why : IMPROVE_enforce.md
