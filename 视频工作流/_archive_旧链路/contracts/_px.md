[S] _px @ATOM/math  d0  in=3  gen:contract_gen
does: _px.py —— 像素/米 换算的**唯一**口径
api: px_per_m, canvas_px_per_m, to_px, to_m, world_y_from_canvas, canvas_y_from_world, self_check
const: CANVAS_W, CANVAS_H, CROP_TOP_DEFAULT, VISIBLE_H_DEFAULT
impl: self_check → canvas_px_per_m → canvas_y_from_world → px_per_m
down: build_phase_asset,build_phase_setup,physics
edit: build_phase_asset,build_phase_setup,physics   # 改_px须同步核对这些文件
rule: T86
why : IMPROVE__px.md
