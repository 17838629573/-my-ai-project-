[S] pose @SHOT/skel  d2  in=7  gen:contract_gen
does: pose —— 统一姿态求解器：FK 引擎 + 解析 IK + 笛卡尔足端轨迹
api: bone_lengths, fk, two_bone_ik, leg_of, hip_height, foot_target, blend_poses, solve, self_check
const: NAMES, BONES, SEGS, FACE_KEYS, _MA, _MB
impl: 入口 self_check；内部helper 4个
up: foot_lock,pose_selfcheck
down: build_phase_gen,build_util,genqueue,pose_prompt,pose_selfcheck,puppet (+1)
edit: build_phase_gen,build_util,foot_lock,genqueue,pose_prompt,pose_selfcheck,puppet,骨架_行走   # 改pose须同步核对这些文件
rule: T67 T68 T69 T70 T72 T99 T100 T101 T102 T103
why : IMPROVE_pose.md
