[FACT] _solver_geom   44行   机器生成，勿手改
doc: 骨架几何：把物理点变成归一化中心线。
api:
  L17 skeleton_points(pts,N,L,W,mean,vfactor,tip_pp,samples,lift_deg,dir_deg)  # 返回 N 个相位，每个相位一条归一化中心线 [(x,y)]（单位：L）
calls_out: anchor,cur,math,out
up: _solver_base,anchor
down: _solver_chain,solver
