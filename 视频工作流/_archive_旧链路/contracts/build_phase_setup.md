[S] build_phase_setup @BUILD/phase  d5  in=1  gen:contract_gen
does: 出片前置：基线探测 + 比例尺 + 路径校验。
api: setup_baseline, setup_scale, setup_path
const: W_DIR_DEFAULT
impl: 入口 setup_baseline
up: _px,build_util,cloth_wire,groundline,path,path_align,scale_map,wind_response
down: build_video
edit: _px,build_util,build_video,cloth_wire,groundline,path,path_align,scale_map,wind_response   # 改build_phase_setup须同步核对这些文件
rule: T84 T86 T96 T98 T102
why : IMPROVE_build_phase_setup.md
