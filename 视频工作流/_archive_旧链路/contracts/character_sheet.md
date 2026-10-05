[S] character_sheet @SHOT/sheet  d2  in=7  gen:contract_gen
does: 角色图集 + 映射层
api: missing_assets, load_native, load_scaled, resolve, measure_native_composition, check_naming, tier_target_h, loop_closed
const: BASE, CHAR_DIR, SHEET, SUPPORTING, EXPRESSION, PROP, WALK_8FRAME, TIER_BY_SHARE
impl: 入口 missing_assets
up: chroma,photo_rules
down: _actor_audit,enforce_cmds,film_assemble,film_assemble_render,render_desert_banner,render_gate_banner (+1)
edit: _actor_audit,chroma,enforce_cmds,film_assemble,film_assemble_render,photo_rules,render_desert_banner,render_gate_banner,render_v4_main   # 改character_sheet须同步核对这些文件
why : IMPROVE_character_sheet.md
