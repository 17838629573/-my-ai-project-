[S] _surface @ATOM/cam  d2  in=1  gen:contract_gen
does: 规则驱动放置（rule-based placement）—— 禁硬编码坐标。
api: surface_at, ground_y_at_depth, offset_outside_path, place, self_check, anchors_from_scene
const: SURFACE_CLASSES, NORMAL, RULES
impl: self_check → _rule → ground_y_at_depth → offset_outside_path；内部helper 4个
up: _perspective,_wall_geom,param_decl
down: build_video
edit: _perspective,_wall_geom,build_video,param_decl   # 改_surface须同步核对这些文件
rule: T31
why : IMPROVE__surface.md
