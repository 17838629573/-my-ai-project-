[S] prompt_tpl @SHOT/gen  d0  in=2  gen:contract_gen
does: prompt_tpl —— 按族抽象的生图提示词模板（铁律81-85）
api: scale_slots, families, build, structural_pose, self_check
const: EXAMPLES, TPL, DISCIPLINE, HARDCODE_BAN, SCALE_SLOT
impl: self_check → _chk → _scan → _scan_targets；内部helper 4个
down: build_phase_gen,genqueue
edit: build_phase_gen,genqueue   # 改prompt_tpl须同步核对这些文件
rule: T31 T37 T81 T82 T83 T84 T85 T113
why : IMPROVE_prompt_tpl.md
