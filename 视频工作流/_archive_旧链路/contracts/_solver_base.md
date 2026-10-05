[S] _solver_base @SOLVE/base  d0  in=10  gen:contract_gen
does: 基础层：共享常量 + 纯算术。零业务依赖。
api: wind_sign
const: CONSTANTS, AMP_BY_LEVEL_DEFAULT, CONTAINMENT, MAX_MAT_FRAMES, PROBE_MAX, WIND_DIR_DEFAULT, REQUIRED, DRAW_PARAM (+2)
impl: 入口 wind_sign；内部helper 2个
down: _chk_base,_chk_motion,_chk_physics,_solver_chain,_solver_chain_aux,_solver_geom (+4)
edit: _chk_base,_chk_motion,_chk_physics,_solver_chain,_solver_chain_aux,_solver_geom,_solver_probe,_solver_run,_solver_sheet,solver   # 改_solver_base须同步核对这些文件
rule: T18 T31 T32 T34 T39 T40 T47 T48 T88
why : IMPROVE__solver_base.md
