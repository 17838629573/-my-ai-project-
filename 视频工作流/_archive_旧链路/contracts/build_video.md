[TOP] build_video @BUILD/_top  d6  in=0  gen:contract_gen
does: 合成出片：探测基线 + 路径约束 + 语义落位 + 程序化风摆。
api: load_sheet, resize_h, sway_image, over, place_at, apply_garment_wind, main
const: FPS, OUT, _ANCHORS_CACHE
impl: main → _anchors → _flag_xy → _tree_xy；内部helper 7个
up: _ground_arc,_surface,build_phase_asset,build_phase_gen,build_phase_render,build_phase_setup,build_phase_time,build_util,chroma,cloth_wire,composite,framerate,genqueue,groundline,path,placement,scale_map,shot_plan,wind_sway
edit: _ground_arc,_surface,build_phase_asset,build_phase_gen,build_phase_render,build_phase_setup,build_phase_time,build_util,chroma,cloth_wire,composite,framerate,genqueue,groundline,path,placement,scale_map,shot_plan,wind_sway   # 改build_video须同步核对这些文件
rule: T31 T76 T77 T79 T81 T84 T96
why : IMPROVE_build_video.md
