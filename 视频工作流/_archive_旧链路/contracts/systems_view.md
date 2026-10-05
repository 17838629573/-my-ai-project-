[S] systems_view @SHOT/sys  d3  in=1  gen:contract_gen
does: systems 的自检/检查逻辑（由 _extract_tool.py 从 systems.py 抽出）
api: update_composite, update_subtitle
impl: 入口 update_composite；内部helper 1个
up: composite,framerate,physics,physics_rules,skeleton_runtime,subtitle
down: systems
edit: composite,framerate,physics,physics_rules,skeleton_runtime,subtitle,systems   # 改systems_view须同步核对这些文件
why : IMPROVE_systems_view.md
