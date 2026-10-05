[FACT] _solver_base   173行   机器生成，勿手改
doc: 基础层：共享常量 + 纯算术。零业务依赖。
api:
  L140 wind_sign(dir_deg)  # 风向在骨架 x 轴上的投影符号（+1 向右 / -1 向左）。
internal:
  L149 _interp(pts,s,col)
  L165 _grid_for(n)
calls_out: _m,math
guard: return@L150, return@L152
const: CONSTANTS[6], AMP_BY_LEVEL_DEFAULT[9], CONTAINMENT[9], MAX_MAT_FRAMES=16, PROBE_MAX=8, WIND_DIR_DEFAULT=0.0, REQUIRED[5], DRAW_PARAM[6], CHAIN_REQUIRED[3], CHAIN_REQUIRED_SPEC[2]
up: -
down: _chk_base,_chk_motion,_chk_physics,_solver_chain,_solver_chain_aux,_solver_geom,_solver_probe,_solver_run,_solver_sheet,solver
