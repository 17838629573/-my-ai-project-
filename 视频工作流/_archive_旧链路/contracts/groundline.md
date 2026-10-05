[S] groundline @ATOM/path  d0  in=3  gen:contract_gen
does: 地基线探测：从背景图自动找出"人能站在哪条水平线上"。
api: probe, detect, self_check
const: MULTI_SCALE
impl: self_check → _multiscale_contrast → _row_strength → detect；内部helper 2个
down: build_phase_setup,build_util,build_video
edit: build_phase_setup,build_util,build_video   # 改groundline须同步核对这些文件
why : IMPROVE_groundline.md
