[S] systems_phys @SHOT/sys  d3  in=1  gen:contract_gen
does: systems 的自检/检查逻辑（由 _extract_tool.py 从 systems.py 抽出）
api: init_physics, update_physics, update_movables
impl: 入口 init_physics
up: framerate,physics,physics_rules,skeleton_runtime,systems
down: systems
edit: framerate,physics,physics_rules,skeleton_runtime,systems   # 改systems_phys须同步核对这些文件
rule: T14 T23 T28 T46
why : IMPROVE_systems_phys.md
