[S] _chk_physics @SOLVE/check  d7  in=1  gen:contract_gen
does: 检查域1：缺槽报错/物性换算/帧数/St/固定端/相位均匀性。
api: check
impl: 入口 check
up: _chk_base,_solver_base,_solver_chain,_solver_sheet,framerate
down: solver_check
edit: _chk_base,_solver_base,_solver_chain,_solver_sheet,framerate,solver_check   # 改_chk_physics须同步核对这些文件
rule: T20 T29 T31 T41
why : IMPROVE__chk_physics.md
