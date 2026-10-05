# WHY physics_rules   (结构化·禁散文)

meta: tier=ATOM/phys | 163行 | 上游1 下游5

## basis 依据（搜证值/公式出处；改常数前必看）
- A = k · V^(2/3)。k = 细长度(长径比)，实测反推见 notes/physics.md

## trap 坑（勿回退 / 已修 / 冲突）
- ? 待补

## intent 意图（为何存在）
physics_rules.py —— 物性推导与风力计算

## impact 改动影响（改本模块须回头验）
- 直接下游: environment, systems, systems_phys, systems_selfcheck, systems_view
- 验证命令: python3 impact.py physics_rules
