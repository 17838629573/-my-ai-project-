[S] _chk_chain @SOLVE/check  d7  in=1  gen:contract_gen
does: 检查域2：chain 共振/逐级递推/transient 稳态与包络衰减。
api: check
impl: 入口 check
up: _chk_base,_solver_chain
down: solver_check
edit: _chk_base,_solver_chain,solver_check   # 改_chk_chain须同步核对这些文件
rule: T20 T31 T32
why : IMPROVE__chk_chain.md
