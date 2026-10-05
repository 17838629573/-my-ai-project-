# WHY film_assemble   (结构化·禁散文)

meta: tier=SHOT/assemble | 148行 | 上游5 下游2

## basis 依据（搜证值/公式出处；改常数前必看）
- ? 待补（改常数前必补）

## trap 坑（勿回退 / 已修 / 冲突）
- 【已修】__main__ 原位于 self_check/render_one 定义之前（L133），执行到入口时二者

## intent 意图（为何存在）
镜头装配层 —— 模型填 3 个字段，代码完成全部映射

## impact 改动影响（改本模块须回头验）
- 直接下游: film_assemble_render, render_v4
- 验证命令: python3 impact.py film_assemble
