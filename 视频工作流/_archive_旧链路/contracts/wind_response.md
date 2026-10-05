[S] wind_response @ATOM/aero  d1  in=5  gen:contract_gen
does: 风响应统一数值层：所有受风物体的频率/幅度，一律由族+尺寸+风速算出。
api: family_freq, family_amp, wind_response, clamp_render_freq, tree_layers, self_check
const: FAMILY_CALIB, U_SAT, RENDER_FPS, MIN_FRAMES_PER_CYCLE, F_MAX_RENDER
impl: self_check → family_amp → family_freq → tree_layers
up: _common
down: build_phase_gen,build_phase_setup,build_phase_time,cloth_wire,wind_sway
edit: _common,build_phase_gen,build_phase_setup,build_phase_time,cloth_wire,wind_sway   # 改wind_response须同步核对这些文件
rule: T91 T92 T93 T94
why : IMPROVE_wind_response.md
