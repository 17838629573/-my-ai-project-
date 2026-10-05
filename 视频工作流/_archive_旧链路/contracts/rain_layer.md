[S] rain_layer @ATOM/water  d1  in=0  gen:contract_gen
does: rain_layer.py — 雨层渲染（复用 water.py 全部公式，本模块不含任何物性常数）
api: rain_drops, draw_rain, cv2_line, self_check
const: DEPTH_M
impl: self_check → draw_rain → rain_drops
up: _common,water
edit: _common,water   # 改rain_layer须同步核对这些文件
rule: T96
why : IMPROVE_rain_layer.md
