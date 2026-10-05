[FACT] systems   206行   机器生成，勿手改
doc: systems：常量与编排。已拆出 systems_selfcheck / systems_phys / systems_view（见 IMPROVE_systems.md）
api:
  L41 init_skeleton(ctx)  # 惰性初始化骨架 —— 只有需要动画的镜头才付这个成本
  L89 step_px(char_px)  # 由人物像素高反算步距像素 —— 步距与人物大小必须同源
  L92 scroll_per_frame(char_px,fps)  # 每帧背景位移 = 步距像素 × 步频 / 输出帧率
  L103 matched_playrate(actual_speed_px_s,char_px,clamp)  # 【Distance Matching 业界实现】
  L149 com_vertical_amp(char_px)  # 重心垂直单侧振幅(像素) = 人物像素高 × 1.8%
  L152 update_animation(ctx,i,t)  # 走路动画：8 帧标准循环 + 步距锁相 + 双腿反相。
  L197 self_check(verbose)
internal:
  L131 _walk_pose(phase01)
calls_in: scroll_per_frame→step_px, matched_playrate→step_px, update_animation→_walk_pose, update_animation→com_vertical_amp, update_animation→scroll_per_frame
calls_out: ctx
guard: return@L112
const: REAL_HEIGHT_M=1.7, STRIDE_RATIO=0.45, STEP_LENGTH_M, CADENCE_SPM=120, STEPS_PER_SEC, WALK_PERIOD, PLAYRATE_CLAMP[2], WALK_POSE_TABLE[8], POSE_NAMES[8], COM_V_RATIO=0.012, HEAD_STEADY=0.35, _INLINE_PAT[4], _MAGIC_PAT='\\*\\s*(1e-[0-9]|0\\.00[0-9])\\b'
main: __main__@L204  self_check@L197
up: framerate,physics,physics_rules,skeleton_runtime,systems_phys,systems_selfcheck,systems_view
down: render_desert_banner,render_gate_banner,render_v4,render_v4_main,systems_phys,systems_selfcheck
