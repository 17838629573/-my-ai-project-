[S] chroma @ATOM/img  d1  in=9  gen:contract_gen
does: 角色层素材处理：色度键抠像 + 去溢色 + 边缘处理
api: chroma_key, trim_alpha, clean_mask, all_components, load_character, overlay, contact_shadow, self_check
impl: 入口 self_check；内部helper 1个
up: _despill,chroma_selfcheck,composite
down: _split_sheet,build_phase_asset,build_util,build_video,character_sheet,chroma_selfcheck (+3)
edit: _despill,_split_sheet,build_phase_asset,build_util,build_video,character_sheet,chroma_selfcheck,composite,enforce_cmds,film_assemble,film_assemble_render   # 改chroma须同步核对这些文件
rule: T44
why : IMPROVE_chroma.md
