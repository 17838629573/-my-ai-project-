[S] wind_sway @ATOM/aero  d2  in=3  gen:contract_gen
does: 植物风摆：程序化三层叠加（trunk / branch / leaf），根部权重恒 0。
api: layer_weight, phase_of, sway_offset, wind_sway, self_check
const: LAYERS, DEFAULT_CFG, DEFAULT_L
impl: self_check → layer_weight → phase_of → sway_offset；内部helper 2个
up: wind_response
down: build_util,build_video,shot_plan
edit: build_util,build_video,shot_plan,wind_response   # 改wind_sway须同步核对这些文件
rule: T80 T81 T82 T91 T94
why : IMPROVE_wind_sway.md
