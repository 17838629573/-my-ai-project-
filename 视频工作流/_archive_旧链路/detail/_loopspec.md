[FACT] _loopspec   137行   机器生成，勿手改
doc: _loopspec.py — 循环资产规范（游戏业界 cycle animation 标准）
api:
  L20 frames_for_cycle(cycle_s,fps)  # 覆盖完整周期的帧数，且不含重复端点（铁律114）。
  L37 playrate_for(n_frames,cycle_s)  # 播放帧率 = 帧数 / 周期秒数。N 帧播完正好一个周期（铁律113）。
  L44 phase_map(n,include_endpoint)  # 每帧相位（弧度）。include_endpoint=False 保证循环闭合（铁律114）。
  L53 loop_closure_error(seq,tol)  # 循环闭合误差：末帧→首帧的跳变 与 典型单帧增量 的比值。
  L78 rain_tile_sheets(n_layers,tiles_per_layer)  # 雨的循环贴图规范（铁律116）。
  L100 self_check()
internal:
  L32 _default_fps(cycle_s)
calls_in: frames_for_cycle→_default_fps, self_check→frames_for_cycle, self_check→loop_closure_error, self_check→phase_map, self_check→playrate_for, self_check→rain_tile_sheets
calls_out: math
guard: raise@L39, raise@L46, raise@L61, return@L70, raise@L85, raise@L87
const: MIN_FRAMES_PER_CYCLE=24, MAX_FRAMES_PER_CYCLE=32
main: __main__@L136  self_check@L100
up: -
down: -
