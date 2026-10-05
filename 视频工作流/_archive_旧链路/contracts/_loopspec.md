[S] _loopspec @ATOM/frame  d0  in=0  gen:contract_gen
does: _loopspec.py — 循环资产规范（游戏业界 cycle animation 标准）
api: frames_for_cycle, playrate_for, phase_map, loop_closure_error, rain_tile_sheets, self_check
const: MIN_FRAMES_PER_CYCLE, MAX_FRAMES_PER_CYCLE
impl: self_check → frames_for_cycle → loop_closure_error → phase_map；内部helper 1个
rule: T113 T114 T115 T116
why : IMPROVE__loopspec.md
