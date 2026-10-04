# WHY actors   (结构化·禁散文)

meta: tier=ATOM/rule | 199行 | 上游1 下游4

## basis 依据（搜证值/公式出处；改常数前必看）
- 【修正】mass 曾手填 1.0kg，实测应为 0.0257kg（面密度95g/m² × 0.9×0.3m）
- 依铁律16：dynamic actor 必须有 <name>_fNN.png 循环序列

## trap 坑（勿回退 / 已修 / 冲突）
- 【修正】mass 曾手填 1.0kg，实测应为 0.0257kg（面密度95g/m² × 0.9×0.3m）
- 只允许"动不了"的东西。可动件禁止烘焙进背景图。

## intent 意图（为何存在）
actors.py —— 可动者登记 + 动作能力白名单 + 硬报错

## impact 改动影响（改本模块须回头验）
- 直接下游: environment, render_desert_banner, render_gate_banner, render_v4
- 验证命令: python3 impact.py actors
