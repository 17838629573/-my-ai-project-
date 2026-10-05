[S] skeleton_runtime @SHOT/skel  d2  in=5  gen:contract_gen
does: Spine 格式骨架求解器 —— 不需要官方 runtime
api: mat_mul, mat_local, mat_apply, mat_inverse, apply_animation
impl: 入口 mat_mul；内部helper 1个
up: skeleton_runtime_selfcheck
down: skeleton_runtime_selfcheck,systems,systems_phys,systems_selfcheck,systems_view
edit: skeleton_runtime_selfcheck,systems,systems_phys,systems_selfcheck,systems_view   # 改skeleton_runtime须同步核对这些文件
why : IMPROVE_skeleton_runtime.md
