[S] _chk_sheet @SOLVE/check  d7  in=1  gen:contract_gen
does: 检查域7：容纳性/居中/min_fill/centroid/探针计划。
api: check
impl: 入口 check
up: _chk_base,_solver_chain,_solver_probe,_solver_sheet
down: solver_check
edit: _chk_base,_solver_chain,_solver_probe,_solver_sheet,solver_check   # 改_chk_sheet须同步核对这些文件
rule: T31 T47 T48
why : IMPROVE__chk_sheet.md
