[S] _perspective @ATOM/cam  d0  in=3  gen:contract_gen
does: 透视几何：地平线 / 深度 / 缩放场（纯函数，禁硬编码坐标）
api: focal_px, horizon_from_vanishing, camera_height_from_ref, scale_field, depth_at, y_at_depth, path_along_depth, path_lateral, object_px_height, self_check
const: F_OVER_IMAGE_H
impl: self_check → _seg_intersect → camera_height_from_ref → depth_at；内部helper 1个
down: _camera,_surface,_wall_geom
edit: _camera,_surface,_wall_geom   # 改_perspective须同步核对这些文件
rule: T31 T100
why : IMPROVE__perspective.md
