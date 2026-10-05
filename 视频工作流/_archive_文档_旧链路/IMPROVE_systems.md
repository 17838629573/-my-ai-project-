# WHY systems   (结构化·禁散文)

meta: tier=SHOT/sys | 206行 | 上游7 下游5

## basis 依据（搜证值/公式出处；改常数前必看）
- 手臂与腿反向摆动（行业标准）

## trap 坑（勿回退 / 已修 / 冲突）
- 【已修】__main__ 原位于本函数定义之前（L195），执行到入口时 self_check 尚未定义

## intent 意图（为何存在）
systems：常量与编排。已拆出 systems_selfcheck / systems_phys / systems_view（见 IMPROVE_systems.md）

## impact 改动影响（改本模块须回头验）
- 直接下游: render_desert_banner, render_gate_banner, render_v4, systems_phys, systems_selfcheck
- 验证命令: python3 impact.py systems
