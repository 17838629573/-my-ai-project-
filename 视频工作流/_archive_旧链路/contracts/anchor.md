[S] anchor @ATOM/path  d1  in=3  gen:contract_gen
does: anchor.py —— 物理点锚点层
api: dimensionless, judge_regime, strouhal_freq, cantilever_points, pendulum2_points, build_anchor, self_check
const: RHO_F, NU, G, ST_TARGET, BETA1, R2_STRAIGHT, R2_DEFLECT, FAMILIES
impl: self_check → build_anchor → cantilever_points → dimensionless；内部helper 2个
up: framerate
down: _chk_base,_solver_chain,_solver_geom
edit: _chk_base,_solver_chain,_solver_geom,framerate   # 改anchor须同步核对这些文件
rule: T20 T29 T32 T45
why : IMPROVE_anchor.md
