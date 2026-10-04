# WHY _surface   (结构化·禁散文)

meta: tier=ATOM/cam | 311行 | 上游2 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- ? 待补（改常数前必补）

## trap 坑（勿回退 / 已修 / 冲突）
- 仅当该种类「禁止落在路径上」（树类）时才需要排除区；
- 8 未知种类必须报错，不静默
- 10 缺 clear_m 必须报错（不静默给默认）

## intent 意图（为何存在）
规则驱动放置（rule-based placement）—— 禁硬编码坐标。

## impact 改动影响（改本模块须回头验）
- 直接下游: build_video
- 验证命令: python3 impact.py _surface
