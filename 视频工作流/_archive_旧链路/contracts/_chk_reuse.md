[S] _chk_reuse @SOLVE/check  d7  in=1  gen:contract_gen
does: 检查域8：复用规划/镜像/layer_plan/overlay/additive_offset。
api: check
impl: 入口 check
up: _chk_base,_solver_reuse
down: solver_check
edit: _chk_base,_solver_reuse,solver_check   # 改_chk_reuse须同步核对这些文件
rule: T31 T49 T50 T51
why : IMPROVE__chk_reuse.md
