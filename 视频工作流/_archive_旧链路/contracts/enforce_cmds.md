[S] enforce_cmds @GATE/core  d3  in=1  gen:contract_gen
does: enforce 的自检/检查逻辑（由 _extract_tool.py 从 enforce.py 抽出）
api: cmd_status, cmd_validate, cmd_check_contract, cmd_check_deps, cmd_check_evidence, cmd_gate, cmd_check_assets
impl: 入口 cmd_status
up: character_sheet,chroma,enforce
down: enforce
edit: character_sheet,chroma,enforce   # 改enforce_cmds须同步核对这些文件
rule: T1 T12
why : IMPROVE_enforce_cmds.md
