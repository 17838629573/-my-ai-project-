[FACT] _common   238行   机器生成，勿手改
doc: _common.py —— 跨模块原子复用库（单一定义，全局调用）
api:
  L47 clamp(x,lo,hi)  # 数值钳制。
  L51 lerp(a,b,t)  # 线性插值。t 在 [0,1]，越界按 clamp 处理。
  L55 smoothstep(edge0,edge1,x)  # Smoothstep 平滑插值（Ken Perlin 定义）。
  L60 catmull_rom(p0,p1,p2,p3,t)  # Catmull-Rom 样条，过 p1,p2 两点。t∈[0,1]。
  L73 rad2deg(r)
  L76 deg2rad(d)
  L79 normalize_deg(d)  # 角度归一化到 [0, 360)。
  L83 normalize_rad(r)  # 弧度归一化到 [0, 2π)。
  L88 pixels_per_meter(view_h_px,view_h_m,crop_top)  # 像素/米 换算。全局唯一实现，禁止各模块手写。
  L104 meters_to_px(m,px_per_m)  # 米 -> 像素，四舍五入取整。
  L108 px_to_meters(px,px_per_m)
  L129 beaufort_scale(u)  # 由风速 u(m/s) 得蒲福等级与旗帜 regime。
  L139 flag_undulation_period(L,u,c)  # 【已废弃·铁律89】保留仅为兼容旧调用，新代码一律用 flag_motion()。
  L172 flag_motion(regime,u)  # 旗帜整体运动：按 regime 查表得 (周期s, 幅度比A/L, 颤动Hz)。
  L194 uniform_accel(v0,a,t)  # 匀加速：返回 (位移, 末速度)。s = v0*t + 0.5*a*t^2
  L198 projectile(v0,angle_deg,g,t)  # 抛体：返回 (x, y)，y 向上为正。
  L203 gait_cycle_from_speed(speed_mps,stride_m)  # 由速度与步幅反推步态周期。铁律：speed = stride / cycle 必须成立。
  L213 cadence_bpm(cycle_s)  # 步频（步/分）。步行 100-120，慢跑 160-180；>200 视为异常须告警。
  L220 require(cond,msg)  # 断言：条件不成立即抛 ValueError。替代 4 处手写 ck()。
  L225 contact_shadow(xy,ground_y,tol)  # 支撑脚是否与地面接触。过去 chroma / composite 各写一份。
  L230 phase_of(t,period,phase_shift)  # 归一化相位 φ∈[0,1)。period<=0 视为静止（返回 0）。
  L236 nearest_frame(t,fps)  # 时间 -> 帧序号。
calls_in: lerp→clamp, smoothstep→clamp, flag_motion→beaufort_scale, projectile→deg2rad
calls_out: math
guard: raise@L100, return@L146, raise@L178, return@L181, raise@L207, return@L209, return@L215, raise@L222, return@L232
const: PI, DEG, RAD, HUMAN_PROPORTION[9], LEG_RATIO, BEAUFORT[13], FLAG_MOTION[13]
up: -
down: _common_selfcheck,build_phase_gen,build_util,physics,physics_rules,rain_layer,wind_response
