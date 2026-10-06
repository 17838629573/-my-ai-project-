# WHY cloth_aero   (结构化·禁散文)

meta: tier=ATOM/aero | 176行 | 上游1 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- ? 待补（改常数前必补）

## trap 坑（勿回退 / 已修 / 冲突）
- 证伪：45° 时升力必须非零（若公式写错会退化成 0）

## intent 意图（为何存在）
cloth_aero — 布料/衣物气动受力（"衣服被风吹飞"这类需求）

## impact 改动影响（改本模块须回头验）
- 直接下游: cloth_wire
- 验证命令: python3 impact.py cloth_aero
