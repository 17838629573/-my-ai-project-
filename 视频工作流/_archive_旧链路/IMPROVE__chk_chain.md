# WHY _chk_chain   (结构化·禁散文)

meta: tier=SOLVE/check | 86行 | 上游1 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 7) B 含泊松比项（铁律20同类：同名符号不同义）
- 8) 缺 criteria 必须报错（铁律32：判据不许内置）
- 11) chain: 缺物性即报错（铁律31 覆盖新族）

## trap 坑（勿回退 / 已修 / 冲突）
- 8) 缺 criteria 必须报错（铁律32：判据不许内置）
- 11) chain: 缺物性即报错（铁律31 覆盖新族）
- 断言须用 5τ（e^-5≈0.67%）——仅 1.14τ 剩 32% 属正常，非代码错
- 不是绝对量。断言写绝对阈值会假 FAIL（本项已连错两次）。

## intent 意图（为何存在）
检查域2：chain 共振/逐级递推/transient 稳态与包络衰减。

## impact 改动影响（改本模块须回头验）
- 直接下游: solver_check
- 验证命令: python3 impact.py _chk_chain
