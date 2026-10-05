[FACT] _surface   311行   机器生成，勿手改
doc: 规则驱动放置（rule-based placement）—— 禁硬编码坐标。
api:
  L64 surface_at(y,v_h)  # 屏幕行 y 属于哪个表面层（纯几何：地平线是硬分界）。
  L74 wall_top_y(h_wall_m,z_wall_m,v_h,f_px,h_cam,image_h)  # 墙顶屏幕行 y = 墙基底 y − 墙的像素高。透视算，非手填坐标。
  L93 wall_depth_for_top(h_wall_m,y_top_target,v_h,f_px,h_cam)  # 反解：要让墙顶落在屏幕行 y_top_target，墙须在多深的 Z(m)。
  L111 ground_y_at_depth(z_m,v_h,f_px,h_cam)  # 深度 z 处地面的屏幕行 y。地面是 Z 平面，直接由透视反解。
  L116 offset_outside_path(path_center_x_px,path_half_w_m,clear_m,side,px_per_m)  # 排除区（exclusion volume）：物体须离路径边缘 clear_m 以外。
  L128 place(kind,v_h,f_px,h_cam,*,z_m,h_wall_m,image_h,path_center_x_px,path_half_w_m,clear_m,side)  # 综合落点：按规则选表面 → 算落点 (x, y)。全程无手填坐标。
  L181 self_check()
  L252 anchors_from_scene(spec,bg_bgr,image_h)  # 场景级落点：旗→墙顶，树→地面且退让路径。全程无手填坐标。
internal:
  L56 _rule(kind)
  L302 _surface_kind(name,spec)
calls_in: place→_rule, place→ground_y_at_depth, place→offset_outside_path, place→wall_top_y, self_check→_rule, self_check→ground_y_at_depth, self_check→offset_outside_path, self_check→place, self_check→surface_at, self_check→wall_top_y, anchors_from_scene→_surface_kind, anchors_from_scene→place
calls_out: NORMAL,PD,_P,_cv,ck,fams,o,ref,spec
guard: raise@L57, raise@L69, raise@L81, raise@L85, raise@L98, raise@L105, raise@L122, raise@L141, return@L146, return@L157, raise@L262, raise@L281, return@L305, return@L307, return@L309
const: SURFACE_CLASSES[6], NORMAL[6], RULES[6]
main: __main__@L247  self_check@L181
up: _perspective,param_decl
down: build_video
