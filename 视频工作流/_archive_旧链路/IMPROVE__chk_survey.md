# WHY _chk_survey   (结构化·禁散文)

meta: tier=SOLVE/check | 67行 | 上游1 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 21)【铁律36】源码禁硬编码具体物体名——代码不该知道本片有什么

## trap 坑（勿回退 / 已修 / 冲突）
- 21)【铁律36】源码禁硬编码具体物体名——代码不该知道本片有什么

## intent 意图（为何存在）
检查域4：源码禁硬编码物体名/survey 只问不猜/示例覆盖。

## impact 改动影响（改本模块须回头验）
- 直接下游: solver_check
- 验证命令: python3 impact.py _chk_survey
