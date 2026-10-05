# WHY _solver_geom   (结构化·禁散文)

meta: tier=SOLVE/base | 44行 | 上游2 下游2

## basis 依据（搜证值/公式出处；改常数前必看）
- ? 待补（改常数前必补）

## trap 坑（勿回退 / 已修 / 冲突）
- ? 待补

## intent 意图（为何存在）
骨架几何：把物理点变成归一化中心线。

## impact 改动影响（改本模块须回头验）
- 直接下游: _solver_chain, solver
- 验证命令: python3 impact.py _solver_geom
