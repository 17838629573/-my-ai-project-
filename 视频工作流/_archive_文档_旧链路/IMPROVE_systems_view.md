# WHY systems_view   (结构化·禁散文)

meta: tier=SHOT/sys | 149行 | 上游5 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 预裁剪到字幕实际包围盒 —— 实测整帧 float 混合要 37ms/帧，

## trap 坑（勿回退 / 已修 / 冲突）
- ? 待补

## intent 意图（为何存在）
systems 的自检/检查逻辑（由 _extract_tool.py 从 systems.py 抽出）

## impact 改动影响（改本模块须回头验）
- 直接下游: systems
- 验证命令: python3 impact.py systems_view
