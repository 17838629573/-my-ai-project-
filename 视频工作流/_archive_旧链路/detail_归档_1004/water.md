[FACT] water   294行   机器生成，勿手改
doc: water.py —— 降水与水体纯函数层（雨滴 / 溅射 / 涉水 / 水面波）
api:
  L34 drop_terminal_velocity(D_mm,model)  # 静止空气中雨滴终速 m/s。D_mm 直径 mm。
  L50 marshall_palmer_lambda(I_mm_h)  # Λ = 4.1 * I^-0.21  (1/mm)，I 降雨强度 mm/h
  L57 drop_count_above(D_mm,I_mm_h)  # 单位体积空气中直径 >= D_mm 的滴数 (1/m^3)
  L63 median_volume_diameter(I_mm_h)  # Best(1950) 中值体积直径 mm —— 控制液滴总体积的一半
  L68 rain_intensity_class(I_mm_h)  # US Fed. Meteor. Handbook No.1 分级
  L78 rain_inclination(v_wind,D_mm)  # 偏离垂直的倾角 rad。α = arctan(v_wind / U)
  L89 rain_velocity_vector(v_wind,D_mm)  # 雨滴速度矢量 (vx, vy) m/s，vy 向下为正
  L95 streak_length(v,t_exposure,D_mm)  # 雨线长度 m。L = V*t + 2R（V*t 为曝光位移，2R 为滴本身直径）
  L101 dimensionless(D_mm,V)  # 返回 We / Re / Oh / Fr / K，判据 K = We * Oh^-0.4
  L112 splash_regime(K)  # K < Kc 低 → 铺展合并；Kc 附近 → 冠状；远大于 → 完全飞溅（Worthington 射流）
  L122 body_volume(mass_kg)  # 人体体积 m^3。V_p = a2*m + b2
  L130 submerged_fraction(h_water,h_person)  # 相对淹没体积 Vb/Vp = a1*x^2 + b1*x, x = h_f/h_p（0<=x<=1）
  L137 buoyancy_force(h_water,h_person,mass_kg)  # 浮力 N
  L142 drag_force(v,area_m2,Cd)  # 拖曳力 F = 0.5*rho*Cd*S*v^2
  L147 stability_abt(height_m,mass_kg)  # Abt et al.(1989) 临界水深流速积 hv_c (m^2/s)
  L152 wading_state(depth_m,v_flow,height_m,mass_kg)  # 涉水状态：滑移/倾倒双判据（铁律98）
  L172 wave_omega(k,depth_m)  # ω = sqrt((g*k + σ*k^3/ρ) * tanh(k*h))
  L180 wave_speed(lambda_m,depth_m)  # 相速 cp = ω/k
  L188 wave_regime(lambda_m)  # λ < 1.7cm 毛细主导；否则重力主导
  L193 capillary_gravity_crossover()  # 最小相速对应波长 m（猫爪波 ~1.7cm）
  L198 ripple_from_rain(I_mm_h,depth_m)  # 雨滴击水产生的涟漪主波长 —— 取中值体积直径量级的毛细波
  L207 self_check()
calls_in: drop_count_above→marshall_palmer_lambda, rain_inclination→drop_terminal_velocity, rain_velocity_vector→drop_terminal_velocity, buoyancy_force→body_volume, buoyancy_force→submerged_fraction, wading_state→buoyancy_force, wading_state→drag_force, wading_state→stability_abt, wave_speed→wave_omega, ripple_from_rain→median_volume_diameter, ripple_from_rain→wave_regime, ripple_from_rain→wave_speed, self_check→dimensionless, self_check→drop_terminal_velocity, self_check→marshall_palmer_lambda, self_check→rain_inclination, self_check→rain_intensity_class, self_check→splash_regime, self_check→stability_abt, self_check→wading_state, self_check→wave_regime, self_check→wave_speed
calls_out: math,ok
guard: raise@L40, return@L42, return@L44, raise@L52, return@L70, return@L72, raise@L84, return@L114, return@L116, raise@L125, raise@L182
const: G=9.81, SIGMA_W=0.0728, RHO_W=1000.0, MU_W=0.001002, RHO_A=1.204, MP_N0=8000.0, LAMBDA_CG=0.017
main: __main__@L293  self_check@L207
up: -
down: rain_layer
