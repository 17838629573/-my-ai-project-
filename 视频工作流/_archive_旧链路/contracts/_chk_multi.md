[S] _chk_multi @SOLVE/check  d7  in=1  gen:contract_gen
does: 检查域6：多驱动叠加（位移域）/循环闭合。
api: check
impl: 入口 check
up: _chk_base,_solver_chain
down: solver_check
edit: _chk_base,_solver_chain,solver_check   # 改_chk_multi须同步核对这些文件
rule: T42 T43
why : IMPROVE__chk_multi.md
