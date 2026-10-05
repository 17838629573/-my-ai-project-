# WHY render_v4   (结构化·禁散文)

meta: tier=SHOT/_top | 123行 | 上游8 下游3

## basis 依据（搜证值/公式出处；改常数前必看）
- ? 待补（改常数前必补）

## trap 坑（勿回退 / 已修 / 冲突）
- 【已修】__main__ 原位于 self_check/main 定义之前（L105），执行到入口时二者尚未

## intent 意图（为何存在）
渲染 v4 —— 按需调度版

## impact 改动影响（改本模块须回头验）
- 直接下游: render_desert_banner, render_gate_banner, render_v4_main
- 验证命令: python3 impact.py render_v4
