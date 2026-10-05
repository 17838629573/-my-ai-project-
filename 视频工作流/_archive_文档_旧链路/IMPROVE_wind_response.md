# WHY wind_response   (结构化·禁散文)

meta: tier=ATOM/aero | 277行 | 上游1 下游5

## basis 依据（搜证值/公式出处；改常数前必看）
- a_pow : 幅度随风速的指数（气动力正比动压 -> 理论 2.0，柔性体实测偏小）
- 幅度取较小（保守，铁律93）；周期取较长（保守=更慢）
- （2 帧/周期 = 高频抖动闪烁，正是"叶片抖成一片"的观感来源）
- 3 铁律92：L 越大频率越低（AR 效应）
- 4 铁律92：u 越大频率略升
- 7 铁律93：幅度不超过族上限

## trap 坑（勿回退 / 已修 / 冲突）
- 2 未知族报错
- 6 旧 bug 证伪：St=3.0 会算出 ~6Hz（急速抖动）
- 16 证伪：若频率写死（旧做法），2m/s 与 15m/s 频率完全相同

## intent 意图（为何存在）
风响应统一数值层：所有受风物体的频率/幅度，一律由族+尺寸+风速算出。

## impact 改动影响（改本模块须回头验）
- 直接下游: build_phase_gen, build_phase_setup, build_phase_time, cloth_wire, wind_sway
- 验证命令: python3 impact.py wind_response
