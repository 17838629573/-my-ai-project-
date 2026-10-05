[FACT] wind_response   277行   机器生成，勿手改
doc: 风响应统一数值层：所有受风物体的频率/幅度，一律由族+尺寸+风速算出。
api:
  L42 family_freq(family,L,u)  # 频率(Hz)：f = St * u / L，再乘弱风调制 (u/u_ref)^f_pow。
  L61 family_amp(family,L,u)  # 幅度(m)：气动力正比动压 -> 随 u^a_pow 增长，到 U_SAT 饱和。
  L75 wind_response(family,L,u,regime)  # 统一入口：给定族、特征长度、风速 -> 完整风响应参数。
  L123 clamp_render_freq(f_hz,fps)  # 把频率钳制到可渲染范围，返回 (钳制后频率, 是否发生钳制)。
  L136 tree_layers(H_m,u,crown_ratio)  # 树三层风响应：trunk / branch / leaf。
  L152 self_check()
calls_in: wind_response→clamp_render_freq, wind_response→family_amp, wind_response→family_freq, tree_layers→wind_response, self_check→family_amp, self_check→family_freq, self_check→tree_layers, self_check→wind_response
calls_out: FAMILY_CALIB,fails,fm
guard: raise@L48, raise@L52, return@L54, return@L67, raise@L80, return@L129, return@L131
const: FAMILY_CALIB[6], U_SAT=18.0, RENDER_FPS=60.0, MIN_FRAMES_PER_CYCLE=4.0, F_MAX_RENDER
main: __main__@L275  self_check@L152
up: _common
down: build_phase_gen,build_phase_setup,build_phase_time,cloth_wire,wind_sway
