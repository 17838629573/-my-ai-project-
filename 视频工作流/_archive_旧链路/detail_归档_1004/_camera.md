[FACT] _camera   271行   机器生成，勿手改
doc: 镜头意图 → 机位求解（纯函数层，零硬编码）
api:
  L45 focal_px(image_h,ratio)  # 焦距(像素) = 画面高 × 比例。与 _perspective.focal_px 同口径。
  L50 distance_for_tau(h_subject_m,tau,image_h,f_px)  # 景别决定距离：rho = f_px * h_subject / (tau * H)
  L63 horizon_y(image_h,f_px,pitch_rad)  # 地平线在画面的 y = H/2 - f*tan(pitch)。pitch>0 为俯视(地平线上移)。
  L68 pitch_for_framing(y_target_m,h_cam_m,dist_m,v_target_px,image_h,f_px)  # 求俯仰角，使世界点(距相机 dist, 高 y_target)投影到画面 v_target。
  L94 camera_height_for_angle(y_base_m,h_subject_m,angle)  # 角度 → 相机高度：h_cam = y_base + ratio * h_subject
  L103 project_point(x_m,y_m,z_m,h_cam_m,z_cam_m,pitch_rad,image_w,image_h,f_px)  # 把世界点投影到画面。相机在 (0, h_cam, z_cam)，光轴俯仰 pitch。
  L122 solve(subject,must_include,shot_size,angle,image_w,image_h,v_target_ratio,f_ratio,dist_scale)  # 镜头意图 → 机位。
  L162 placeable_depth_range(cam,y_base_m,image_h,z_max)  # 机位定死后，给定平面高度上「仍在画面内」的深度区间 [z_near, z_far]。
  L185 solve_coappear(subject,must_include,image_w,image_h,v_target_ratio,prefer,max_scale)  # 自动搜索满足共现约束的机位 —— 机位不该由人选，应由意图解出。
  L238 visibility_report(cam,must_include,margin_px)  # 共现校验：must_include 每个物体的底/顶是否都在画面内。
calls_in: distance_for_tau→focal_px, solve→camera_height_for_angle, solve→distance_for_tau, solve→focal_px, solve→horizon_y, solve→pitch_for_framing, solve_coappear→solve, solve_coappear→visibility_report, visibility_report→project_point
calls_out: P,angles,issue,item,math,o,out,sizes,subject,tried
guard: raise@L58, raise@L97, return@L115, raise@L134, raise@L138, raise@L174, raise@L198, raise@L200, raise@L224
const: SHOT_SIZE[5], ANGLE[4], F_OVER_IMAGE_H=1.2
up: _perspective
down: _camera_selfcheck
