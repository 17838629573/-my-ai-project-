[S] _camera @ATOM/cam  d1  in=1  gen:contract_gen
does: 镜头意图 → 机位求解（纯函数层，零硬编码）
api: focal_px, distance_for_tau, horizon_y, pitch_for_framing, camera_height_for_angle, project_point, solve, placeable_depth_range, solve_coappear, visibility_report
const: SHOT_SIZE, ANGLE, F_OVER_IMAGE_H
impl: 入口 focal_px
up: _perspective
down: _camera_selfcheck
edit: _camera_selfcheck,_perspective   # 改_camera须同步核对这些文件
why : IMPROVE__camera.md
