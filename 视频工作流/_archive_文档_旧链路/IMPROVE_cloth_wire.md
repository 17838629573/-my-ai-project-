# WHY cloth_wire   (结构化·禁散文)

meta: tier=ATOM/aero | 213行 | 上游3 下游3

## basis 依据（搜证值/公式出处；改常数前必看）
- 铁律99：反问，不兜底（返回值必须接住，否则参数机制形同虚设）

## trap 坑（勿回退 / 已修 / 冲突）
- 【已修】两处 bug：① require() 返回值被丢弃 → v 仍是 None，float 崩；

## intent 意图（为何存在）
cloth_wire — 布料（衣摆/幡/旗）的气动受力接线层

## impact 改动影响（改本模块须回头验）
- 直接下游: build_phase_setup, build_util, build_video
- 验证命令: python3 impact.py cloth_wire
