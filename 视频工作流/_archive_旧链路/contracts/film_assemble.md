[S] film_assemble @SHOT/assemble  d3  in=3  gen:contract_gen
does: 镜头装配层 —— 模型填 3 个字段，代码完成全部映射
api: sub_shift, scroll_bg, prep_native, prep_scaled, nose_offset_x, resolve_shot, plan_resolve, overlay_full, self_check, render_one
const: BASE, BG_DIR, NOSEROOM, META
impl: 入口 self_check；内部helper 1个
up: character_sheet,chroma,film_assemble_render,photo_rules,subtitle
down: film_assemble_render,render_v4,render_v4_main
edit: character_sheet,chroma,film_assemble_render,photo_rules,render_v4,render_v4_main,subtitle   # 改film_assemble须同步核对这些文件
why : IMPROVE_film_assemble.md
