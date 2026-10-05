[S] photo_rules @ATOM/rule  d0  in=5  gen:contract_gen
does: 摄影规则确定性层
api: body_pixels, ground_y, head_top_y, validate_shot, validate_sequence
const: BODY, JOINTS, SHOT_TYPES, ANGLES, MOVEMENTS
impl: 入口 body_pixels
down: character_sheet,film_assemble,film_assemble_render,render_v4,render_v4_main
edit: character_sheet,film_assemble,film_assemble_render,render_v4,render_v4_main   # 改photo_rules须同步核对这些文件
why : IMPROVE_photo_rules.md
