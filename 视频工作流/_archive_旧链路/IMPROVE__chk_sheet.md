# WHY _chk_sheet   (结构化·禁散文)

meta: tier=SOLVE/check | 91行 | 上游1 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 34)【铁律47】容纳性：触边必须 FAIL（格内铺满 -> margin=0）
- 35)【铁律47】居中留边判 PASS
- 36)【铁律47】min_fill 拦稀疏（历史 bug：前景占比 0.6% 却放行）
- 37)【铁律31】缺 centroid_policy 必须报错，不静默默认
- 38)【铁律48】探针计划：先 8 格，全量网格 >= 探针网格
- 39)【铁律47】真实骨架图集逐格容纳性（端到端，不是合成用例）

## trap 坑（勿回退 / 已修 / 冲突）
- 36)【铁律47】min_fill 拦稀疏（历史 bug：前景占比 0.6% 却放行）
- 37)【铁律31】缺 centroid_policy 必须报错，不静默默认

## intent 意图（为何存在）
检查域7：容纳性/居中/min_fill/centroid/探针计划。

## impact 改动影响（改本模块须回头验）
- 直接下游: solver_check
- 验证命令: python3 impact.py _chk_sheet
