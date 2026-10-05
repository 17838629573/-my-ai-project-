# WHY _solver_chain_aux   (结构化·禁散文)

meta: tier=SOLVE/base | 207行 | 上游2 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 【铁律20】风驱动时 drive 由代码从 fluid.U 算出，不要求 AI 填

## trap 坑（勿回退 / 已修 / 冲突）
- ? 待补

## intent 意图（为何存在）
chain 求解子函数真身（自拆分前快照恢复）

## impact 改动影响（改本模块须回头验）
- 直接下游: _solver_chain
- 验证命令: python3 impact.py _solver_chain_aux
