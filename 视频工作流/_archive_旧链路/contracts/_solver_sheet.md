[S] _solver_sheet @SOLVE/sheet  d1  in=6  gen:contract_gen
does: 图集规划与绘制：网格选择、布局、骨架图集渲染。
api: sheet_layout, sheet_plan, draw_sheet
impl: 入口 sheet_layout；内部helper 1个
up: _solver_base
down: _chk_base,_chk_pack,_chk_physics,_chk_sheet,_solver_run,solver
edit: _chk_base,_chk_pack,_chk_physics,_chk_sheet,_solver_base,_solver_run,solver   # 改_solver_sheet须同步核对这些文件
rule: T1 T17 T39 T40 T41 T47 T54 T55 T56 T57
why : IMPROVE__solver_sheet.md
