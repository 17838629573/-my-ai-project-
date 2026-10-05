[S] _chk_pack @SOLVE/check  d7  in=1  gen:contract_gen
does: 检查域9：16帧封顶/mat_frames/图集规划/strip。
api: check
impl: 入口 check
up: _chk_base,_solver_chain,_solver_sheet
down: solver_check
edit: _chk_base,_solver_chain,_solver_sheet,solver_check   # 改_chk_pack须同步核对这些文件
rule: T54 T55 T57
why : IMPROVE__chk_pack.md
