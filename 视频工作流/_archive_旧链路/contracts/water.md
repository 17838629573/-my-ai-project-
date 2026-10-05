[S] water @ATOM/water  d0  in=1  gen:contract_gen
does: water.py —— 降水与水体纯函数层（雨滴 / 溅射 / 涉水 / 水面波）
api: drop_terminal_velocity, marshall_palmer_lambda, drop_count_above, median_volume_diameter, rain_intensity_class, rain_inclination, rain_velocity_vector, streak_length, dimensionless, splash_regime, body_volume, submerged_fraction (+10)
const: G, SIGMA_W, RHO_W, MU_W, RHO_A, MP_N0, LAMBDA_CG
impl: self_check → dimensionless → drop_terminal_velocity → marshall_palmer_lambda
down: rain_layer
edit: rain_layer   # 改water须同步核对这些文件
rule: T98
why : IMPROVE_water.md
