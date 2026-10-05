[S] build_phase_asset @BUILD/phase  d5  in=1  gen:contract_gen
does: 出片前置：素材加载与预处理。
api: load_flag_sheet, load_man_sheet, load_tree
impl: 入口 _probe_grid；内部helper 1个
up: _px,build_util,chroma
down: build_video
edit: _px,build_util,build_video,chroma   # 改build_phase_asset须同步核对这些文件
rule: T31 T99
why : IMPROVE_build_phase_asset.md
