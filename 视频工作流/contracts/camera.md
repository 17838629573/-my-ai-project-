# 契约：_camera.py 镜头意图→机位求解

## 依赖
- `_perspective`（复用 `y_at_depth`，不另写透视式）

## 被依赖
- `_surface`（吃 `v_h` / `h_cam`）
- `shot_plan`、`build_video`（机位指导生图与落位）

## 铁律
- **107 机位正推，禁止反推**：叙事意图 → 解机位 → 透视 → 落点 → 生图。
  严禁"先生图、再从图反解 h_cam"。机位是 7 自由度，反解只能得 1 个，必然矛盾。
- **108 景别是期望、共现是硬约束**：冲突时共现优先，并显式报 `tau_eff`
  （主体实际占比），不得静默牺牲谁。
- **109 只能退远不能推近**：`dist_scale >= 1.0`，违反抛 ValueError。
- **110 无解必须抛错**：附各组合失败原因与越界量，绝不返回伪机位、不静默降级。

## 接口
- `solve(subject, shot_size, angle, ...)` → x_cam/h_cam/z_cam/pitch/v_h/f_px/tau
- `solve_coappear(subject, must_include, ..., max_scale=12.0)` → 自动搜可行机位
- `placeable_depth_range(cam, y_base_m)` → (z_near, z_far)，平面在画面内的深度区间

## 改前必读
`IMPROVE_camera.md`（景别/角度表依据、共现求解、可放置区间）
