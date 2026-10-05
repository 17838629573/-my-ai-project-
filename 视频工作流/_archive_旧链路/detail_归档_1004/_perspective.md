[FACT] _perspective   209行   机器生成，勿手改
doc: 透视几何：地平线 / 深度 / 缩放场（纯函数，禁硬编码坐标）
api:
  L27 focal_px(image_h,ratio)  # 焦距（px）。ratio 缺省取 Hoiem 经验值 1.4。
  L34 horizon_from_vanishing(segs,image_h)  # 由线段组求地平线 y。
  L73 camera_height_from_ref(y_world,v_t,v_b,v_h)  # 由已知真实高度的参照物反解相机高度。依据[1] Eq.(6) 变形。
  L85 scale_field(y,v_h,h_cam)  # 缩放场 SF(y)：该屏幕行上 1 米对应多少像素。依据[2]。
  L94 depth_at(y,v_h,f_px,h_cam)  # 屏幕行 y 对应的地面深度 Z(m)。依据[3]。
  L100 y_at_depth(z,v_h,f_px,h_cam)  # 深度 Z(m) 对应的屏幕行 y。depth_at 的反函数。
  L107 path_along_depth(z0,z1,n,v_h,f_px,h_cam,x_of)  # 沿纵深生成路径点（远 → 近 或 近 → 远）。
  L128 path_lateral(y,x0,x1,n,v_h,h_cam)  # 横向（平行画面）路径：y 恒定 → scale 恒定（铁律100 前段）。
  L134 object_px_height(y_world,y_base,v_h,h_cam)  # 真实高 y_world(m) 的物体立于屏幕行 y_base 时的像素高。依据[1]。
  L139 self_check()
internal:
  L62 _seg_intersect(a,b)
calls_in: horizon_from_vanishing→_seg_intersect, depth_at→scale_field, path_along_depth→scale_field, path_along_depth→y_at_depth, path_lateral→scale_field, object_px_height→scale_field, self_check→_seg_intersect, self_check→camera_height_from_ref, self_check→depth_at, self_check→focal_px, self_check→horizon_from_vanishing, self_check→object_px_height, self_check→path_along_depth, self_check→path_lateral, self_check→scale_field, self_check→y_at_depth
calls_out: ck,out,pts,segs
guard: raise@L29, raise@L53, return@L67, raise@L78, raise@L80, raise@L87, raise@L89, raise@L102, raise@L115
const: F_OVER_IMAGE_H=1.4
main: __main__@L207  self_check@L139
up: -
down: _camera,_surface
