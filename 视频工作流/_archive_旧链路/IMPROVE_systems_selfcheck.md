# WHY systems_selfcheck   (结构化·禁散文)

meta: tier=SHOT/sys | 129行 | 上游5 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 1) 铁律11：不得内联物理公式
- 2) 铁律14：气动力换算禁魔法系数

## trap 坑（勿回退 / 已修 / 冲突）
- 2) 铁律14：气动力换算禁魔法系数

## intent 意图（为何存在）
systems 的自检/检查逻辑（由 _extract_tool.py 从 systems.py 抽出）

## impact 改动影响（改本模块须回头验）
- 直接下游: systems
- 验证命令: python3 impact.py systems_selfcheck
