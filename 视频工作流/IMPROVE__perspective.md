# WHY _perspective   (结构化·禁散文)

meta: tier=ATOM/cam | 209行 | 上游0 下游2

## basis 依据（搜证值/公式出处；改常数前必看）
- 焦距与像高之比的经验值。唯一出处：Hoiem IJCV2008 正文

## trap 坑（勿回退 / 已修 / 冲突）
- 10 交点不足时报错而非静默

## intent 意图（为何存在）
透视几何：地平线 / 深度 / 缩放场（纯函数，禁硬编码坐标）

## impact 改动影响（改本模块须回头验）
- 直接下游: _camera, _surface
- 验证命令: python3 impact.py _perspective
