# WHY pose_selfcheck   (结构化·禁散文)

meta: tier=SHOT/skel | 177行 | 上游1 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 3 支撑期脚世界坐标恒定（铁律68 核心）
- 5 speed/cadence 一致（铁律69）
- 9 铁律72 禁硬编码坐标表（含证伪）
- 10 缺物性槽位即报错（铁律70）
- 11 髋高由步幅反算且 IK 全周期可达（铁律69 联算）

## trap 坑（勿回退 / 已修 / 冲突）
- 9 铁律72 禁硬编码坐标表（含证伪）
- 10 缺物性槽位即报错（铁律70）

## intent 意图（为何存在）
pose 的自检/检查逻辑（由 _extract_tool.py 从 pose.py 抽出）

## impact 改动影响（改本模块须回头验）
- 直接下游: pose
- 验证命令: python3 impact.py pose_selfcheck
