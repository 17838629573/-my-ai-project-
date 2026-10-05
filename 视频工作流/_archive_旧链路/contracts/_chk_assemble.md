[S] _chk_assemble @SOLVE/check  d7  in=1  gen:contract_gen
does: 检查域3：inventory/assemble/动静划分/anchor/驱动源。
api: check
impl: 入口 check
up: _chk_base,solver_survey
down: solver_check
edit: _chk_base,solver_check,solver_survey   # 改_chk_assemble须同步核对这些文件
why : IMPROVE__chk_assemble.md
