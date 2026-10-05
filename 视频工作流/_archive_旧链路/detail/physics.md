[FACT] physics   258行   机器生成，勿手改
doc: physics.py —— 物理原子层（逻辑唯一实现，数值全外置）
api:
  L39 volume(mass,rho)  # 体积 V = M / rho
  L44 area(mass,kind,k)  # 迎风面积 A = k * V^(2/3)。由质量反推，不手填。
  L53 force(v_rel,A,cd,b)  # 气动力 F = 0.5*rho*Cd*A*v^(2+B)*V_REF^(-B)。b<0 为柔性体 Vogel 修正。
  L63 force_per_area(v_rel,cd,b)  # 单位面积气动力（压力），供质点/无面积物体使用。
  L68 accel(F,mass)  # a = F / m
  L75 torque(F,r)  # 力矩 tau = F * r。r=0（pinned）时恒为 0 —— 旗杆锁死的物理根据。
  L80 px_per_m(char_px,real_height_m)  # 世界->像素换算：像素每米
  L91 beaufort(level)  # 蒲福风级 -> m/s
  L100 beaufort_level(v)  # m/s -> (风级, 形态描述)。蒲福表反查。
  L112 rel_wind(v_wind,v_actor)  # 相对风速。风阻取决于物体与空气的相对速度，不是绝对风速。
  L134 swing_angle(F,mass,max_deg)  # 悬臂摆角 theta = atan(F / (m*g))，钳制在视觉上限内。
  L146 swing_offset(theta,r)  # 摆角 -> 该点位移。r 为到根部（pinned）的归一化距离 0..1。
  L153 alpha_blend(dst,src,a)  # alpha 混合：out = src*a + dst*(1-a)。a 为 float32 HxWx1。
  L158 wave(t,freq,amp,phase)  # 正弦调制。行波靠 phase 沿空间递增，不靠各点同相。
  L163 clamp(v,lo,hi)
  L181 surface_effect(name)  # 地表 -> (mu, slow, sink, footprint)。未知地表回退 soil 并标记。
  L188 gait_speed(base,surface,slope_pct)  # 步速 = 基准 * (1-地表衰减) * (1-坡度衰减)。
calls_in: area→volume, force_per_area→force, gait_speed→surface_effect
calls_out: BEAUFORT_DESC,K_SHAPE,_common,_px,math
guard: return@L47, return@L55, return@L58, return@L70, return@L93, return@L95, return@L140, return@L183
const: RHO_AIR=1.225, G=9.81, RHO_BODY=1000.0, K_SHAPE[7], K_SHAPE_DEFAULT=4.0, BEAUFORT[13], V_REF=10.0, BEAUFORT_DESC[9], SWING_MAX_DEG=35.0, SURFACE[8]
main: __main__@L205
up: _common,_px
down: _chk_base,_chk_motion,_solver_chain,actors,environment,render_desert_banner,render_gate_banner,render_v4,render_v4_main,systems,systems_phys,systems_selfcheck,systems_view
