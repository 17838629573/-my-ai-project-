[S] _solver_geom @SOLVE/base  d2  in=2  gen:contract_gen
does: 骨架几何：把物理点变成归一化中心线。
api: skeleton_points
impl: 入口 skeleton_points
up: _solver_base,anchor
down: _solver_chain,solver
edit: _solver_base,_solver_chain,anchor,solver   # 改_solver_geom须同步核对这些文件
rule: T39
why : IMPROVE__solver_geom.md
