[S] _solver_reuse @SOLVE/sheet  d0  in=4  gen:contract_gen
does: 复用规划：镜像/偏移/分层，减生图张数。
api: reuse_plan, layer_plan, additive_offset
impl: _reuse_for → reuse_plan；内部helper 1个
down: _chk_base,_chk_reuse,_solver_run,solver
edit: _chk_base,_chk_reuse,_solver_run,solver   # 改_solver_reuse须同步核对这些文件
rule: T18 T31 T32 T49 T51 T52 T53
why : IMPROVE__solver_reuse.md
