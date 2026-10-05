[S] path @ATOM/path  d0  in=6  gen:contract_gen
does: 路径约束：把位置表示为「弧长 s + 横向偏移 offset」，使其永远在路径上。
api: catmull_rom, sample, arc_table, at_distance, project, clamp_offset, advance, lookahead, self_check
impl: self_check → advance → arc_table → at_distance；内部helper 3个
down: build_phase_render,build_phase_setup,build_util,build_video,path_align,shot_plan
edit: build_phase_render,build_phase_setup,build_util,build_video,path_align,shot_plan   # 改path须同步核对这些文件
rule: T76 T77
why : IMPROVE_path.md
