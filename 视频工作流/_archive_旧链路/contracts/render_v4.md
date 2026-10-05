[TOP] render_v4 @SHOT/_top  d5  in=3  gen:contract_gen
does: 渲染 v4 —— 按需调度版
api: make_parts, build_engine, check_all_shots, self_check, main
const: BASE, BG_DIR, OUT, ENC_IN, ENC_OUT, SHOTS, LEGACY_OUT_NAMES
impl: 入口 main；内部helper 1个
up: actors,film_assemble,framerate,loop_engine,photo_rules,physics,render_v4_main,systems
down: render_desert_banner,render_gate_banner,render_v4_main
edit: actors,film_assemble,framerate,loop_engine,photo_rules,physics,render_desert_banner,render_gate_banner,render_v4_main,systems   # 改render_v4须同步核对这些文件
why : IMPROVE_render_v4.md
