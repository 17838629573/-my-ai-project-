[S] systems_selfcheck @SHOT/sys  d5  in=1  gen:contract_gen
does: systems 的自检/检查逻辑（由 _extract_tool.py 从 systems.py 抽出）
api: self_check
impl: 入口 self_check
up: framerate,physics,physics_rules,skeleton_runtime,systems
down: systems
edit: framerate,physics,physics_rules,skeleton_runtime,systems   # 改systems_selfcheck须同步核对这些文件
rule: T11 T14
why : IMPROVE_systems_selfcheck.md
