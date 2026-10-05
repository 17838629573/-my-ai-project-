[S] path_align @ATOM/path  d1  in=1  gen:contract_gen
does: 路径—路面对齐（契约 contracts/path_align.md，铁律95-98）
api: normalize_pts, walkable_band, is_ground_patch, validate_path, visible_path_prompt, self_check
impl: self_check → normalize_pts → validate_path；内部helper 2个
up: path
down: build_phase_setup
edit: build_phase_setup,path   # 改path_align须同步核对这些文件
rule: T95 T96 T97 T98
why : IMPROVE_path_align.md
