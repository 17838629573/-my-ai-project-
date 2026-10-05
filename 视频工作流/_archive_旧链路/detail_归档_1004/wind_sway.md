[FACT] wind_sway   248行   机器生成，勿手改
doc: 植物风摆：程序化三层叠加（trunk / branch / leaf），根部权重恒 0。
api:
  L43 layer_weight(t,layer,exponent)  # 归一化长度 t∈[0,1] → 该层权重。根部(0)恒为 0。
  L52 phase_of(world_xy,salt)  # 由世界坐标派生相位（铁律82：个体去同步）。
  L65 sway_offset(t,time_s,wind,layer,cfg,phase,L)  # 单层沿风向位移（米）。
  L93 wind_sway(t,time_s,wind,cfg,world_xy)  # 三层叠加。返回 {dx, dy, parts}。dx 沿风向，dy 为轻微垂向耦合。
  L112 self_check()
internal:
  L30 _cfg(cfg)
  L59 _gust(time_s,phase,cfg)
calls_in: sway_offset→_cfg, sway_offset→_gust, sway_offset→layer_weight, wind_sway→_cfg, wind_sway→phase_of, wind_sway→sway_offset, self_check→layer_weight, self_check→phase_of, self_check→sway_offset, self_check→wind_sway
calls_out: DEFAULT_CFG,cfg,d,fails,math,wind
guard: raise@L46
const: LAYERS[3], DEFAULT_CFG[3], DEFAULT_L
main: __main__@L246  self_check@L112
up: wind_response
down: build_util,build_video,shot_plan
