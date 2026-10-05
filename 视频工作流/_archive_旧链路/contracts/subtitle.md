[S] subtitle @SHOT/sub  d1  in=3  gen:contract_gen
does: 字幕渲染层 —— 修一个真 bug
api: get_font, wrap, draw_subtitle, subtitle_alpha, check_timing, self_check
const: _FONT_CANDIDATES, _FONT_CACHE, FADE_FRAMES, MIN_GAP_FRAMES, MIN_DURATION_S, MAX_DURATION_S
impl: self_check → check_timing → draw_subtitle → get_font
up: framerate
down: film_assemble,film_assemble_render,systems_view
edit: film_assemble,film_assemble_render,framerate,systems_view   # 改subtitle须同步核对这些文件
rule: T26 T28
why : IMPROVE_subtitle.md
