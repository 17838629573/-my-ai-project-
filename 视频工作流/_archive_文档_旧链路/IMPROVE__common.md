# WHY _common   (结构化·禁散文)

meta: tier=ATOM/math | 238行 | 上游0 下游7

## basis 依据（搜证值/公式出处；改常数前必看）
- 来源：Dr. Jackie Chappell 人体比例研究 + 达芬奇维特鲁威人
- 旗帜运动：按 regime 查表（铁律89）
- 依据：NWS 蒲福表逐风级旗帜描述 + MDPI 实测(inverted flag 6m/s≈2Hz, 8m/s≈1.5Hz)

## trap 坑（勿回退 / 已修 / 冲突）
- ? 待补

## intent 意图（为何存在）
_common.py —— 跨模块原子复用库（单一定义，全局调用）

## impact 改动影响（改本模块须回头验）
- 直接下游: _common_selfcheck, build_phase_gen, build_util, physics, physics_rules, rain_layer, wind_response
- 验证命令: python3 impact.py _common
