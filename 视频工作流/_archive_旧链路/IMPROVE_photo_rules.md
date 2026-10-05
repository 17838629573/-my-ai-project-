# WHY photo_rules   (结构化·禁散文)

meta: tier=ATOM/rule | 251行 | 上游0 下游3

## basis 依据（搜证值/公式出处；改常数前必看）
- 以身高为 1.0，从脚底起算。标准 7.5 头身。

## trap 坑（勿回退 / 已修 / 冲突）
- 关节（禁止在此切）—— 硬禁忌 ②
- 硬禁忌 ②：不能在关节切
- 硬禁忌 ①：不能顶天立地

## intent 意图（为何存在）
摄影规则确定性层

## impact 改动影响（改本模块须回头验）
- 直接下游: character_sheet, film_assemble, render_v4
- 验证命令: python3 impact.py photo_rules
