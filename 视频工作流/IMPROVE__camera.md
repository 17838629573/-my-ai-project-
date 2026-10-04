# WHY _camera   (结构化·禁散文)

meta: tier=ATOM/cam | 271行 | 上游1 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- LensCraft(2025): ELS 3.0 / LS 1.5 / FS 1.0 / MCU 0.7 / ECU 0.5 (scale)

## trap 坑（勿回退 / 已修 / 冲突）
- ? 待补

## intent 意图（为何存在）
镜头意图 → 机位求解（纯函数层，零硬编码）

## impact 改动影响（改本模块须回头验）
- 直接下游: _camera_selfcheck
- 验证命令: python3 impact.py _camera
