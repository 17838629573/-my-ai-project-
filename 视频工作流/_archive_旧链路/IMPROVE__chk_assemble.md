# WHY _chk_assemble   (结构化·禁散文)

meta: tier=SOLVE/check | 66行 | 上游1 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- ? 待补（改常数前必补）

## trap 坑（勿回退 / 已修 / 冲突）
- 15) inventory: 空清单必须报错（禁静默空包）
- 16) inventory: 未知大类必须报错
- 17) assemble: 未划分动静必须报错（核心：代码要逼 AI 回答）
- 20) 驱动源非法必须报错

## intent 意图（为何存在）
检查域3：inventory/assemble/动静划分/anchor/驱动源。

## impact 改动影响（改本模块须回头验）
- 直接下游: solver_check
- 验证命令: python3 impact.py _chk_assemble
