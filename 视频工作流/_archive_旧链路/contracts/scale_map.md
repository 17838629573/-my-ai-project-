[S] scale_map @ATOM/path  d0  in=4  gen:contract_gen
does: scale_map.py — 比例尺层：把「米」换算成「像素」
api: build_scale_map, verify, prompt_block, self_check
const: REQUIRED_CANVAS, REQUIRED_REF, PIVOTS, DEFAULT_TOL
impl: self_check → build_scale_map → prompt_block → verify；内部helper 1个
down: build_phase_setup,build_util,build_video,shot_plan
edit: build_phase_setup,build_util,build_video,shot_plan   # 改scale_map须同步核对这些文件
rule: T31 T32 T64 T65
why : IMPROVE_scale_map.md
