[S] build_util @BUILD/util  d4  in=5  gen:contract_gen
does: build_video 的自检/检查逻辑（由 _extract_tool.py 从 build_video.py 抽出）
api: load_sheet, resize_h, sway_image, over, place_at, apply_garment_wind
const: KEYJOINTS
impl: 入口 load_sheet；内部helper 3个
up: _common,chroma,cloth_wire,composite,framerate,genqueue,groundline,path,placement,pose,scale_map,shot_plan,wind_sway
down: build_phase_asset,build_phase_gen,build_phase_render,build_phase_setup,build_video
edit: _common,build_phase_asset,build_phase_gen,build_phase_render,build_phase_setup,build_video,chroma,cloth_wire,composite,framerate,genqueue,groundline,path,placement,pose,scale_map,shot_plan,wind_sway   # 改build_util须同步核对这些文件
rule: T31 T79 T80 T84 T91
why : IMPROVE_build_util.md
