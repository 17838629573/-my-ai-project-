# WHY _px   (结构化·禁散文)

meta: tier=ATOM/math | 178行 | 上游0 下游3

## basis 依据（搜证值/公式出处；改常数前必看）
- ? 待补（改常数前必补）

## trap 坑（勿回退 / 已修 / 冲突）
- 每一条都是"旧口径 → 新口径"的可执行补偿，不是"不能改"的借口。
- 4 边界拦截（禁静默兜底）
- 6 证伪：若口径被改成画布总高（旧bug），比值应被检测出来

## intent 意图（为何存在）
_px.py —— 像素/米 换算的**唯一**口径

## impact 改动影响（改本模块须回头验）
- 直接下游: build_phase_asset, build_phase_setup, physics
- 验证命令: python3 impact.py _px
