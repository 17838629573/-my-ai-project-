# WHY path_align   (结构化·禁散文)

meta: tier=ATOM/path | 127行 | 上游1 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- ? 待补（改常数前必补）

## trap 坑（勿回退 / 已修 / 冲突）
- 1 越界必须报错

## intent 意图（为何存在）
路径—路面对齐（契约 contracts/path_align.md，铁律95-98）

## impact 改动影响（改本模块须回头验）
- 直接下游: build_phase_setup
- 验证命令: python3 impact.py path_align
