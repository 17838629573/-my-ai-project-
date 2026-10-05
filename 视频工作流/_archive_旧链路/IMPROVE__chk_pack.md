# WHY _chk_pack   (结构化·禁散文)

meta: tier=SOLVE/check | 53行 | 上游1 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 51)【铁律54】源码逻辑区不得出现 16 帧封顶（那是游戏值）
- 52)【铁律54】功能验：mat_frames 必须等于物理帧数，不被截
- 53)【铁律55/56】图集规划：多张合图、格数受限、尺寸不超 2048
- 54)【铁律57】长条物体走 strip

## trap 坑（勿回退 / 已修 / 冲突）
- ? 待补

## intent 意图（为何存在）
检查域9：16帧封顶/mat_frames/图集规划/strip。

## impact 改动影响（改本模块须回头验）
- 直接下游: solver_check
- 验证命令: python3 impact.py _chk_pack
