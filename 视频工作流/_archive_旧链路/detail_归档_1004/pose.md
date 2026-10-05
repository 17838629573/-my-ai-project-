[FACT] pose   289行   机器生成，勿手改
doc: pose —— 统一姿态求解器：FK 引擎 + 解析 IK + 笛卡尔足端轨迹
api:
  L68 bone_lengths(spec)  # 身高 × 环节比例 -> 骨长(米)。比例由 AI 搜证传入。
  L80 fk(root,lengths,angles)  # 正向运动学：层级递归 child = rotate(parent) * offset + parent（2D）。
  L91 two_bone_ik(hip,target,L1,L2,knee_sign)  # 解析两骨 IK（余弦定理），业界 Nicholls/Kyutech 同款闭式解。
  L108 leg_of(L)  # 腿长（髋->踝）= 大腿 + 小腿。
  L113 hip_height(gait,L)  # 髋高由【步幅+腿长】反算（不手填）——保证 IK 可达。
  L133 foot_target(t,side,gait)  # 笛卡尔足端轨迹（铁律68）。
  L161 blend_poses(a,b,w)  # 姿势过渡：余弦 (0~π) 加权（业界 STS 曲线）。
  L189 solve(spec,mode,t)  # 统一入口 -> COCO-17 米制坐标（原点=地面脚下，y 向上）。
  L283 self_check(*a,**k)
internal:
  L62 _need(d,key,where)
  L173 _face(pts,face)
  L269 _chk(name,ok,info)
  L278 _scan_hardcode(*a,**k)
calls_in: bone_lengths→_need, fk→_need, hip_height→_need, foot_target→_need, blend_poses→_need, _face→_need, solve→_face, solve→_need, solve→bone_lengths, solve→fk, solve→foot_target, solve→hip_height, solve→leg_of, solve→two_bone_ik
calls_out: gait,math,out
guard: raise@L63, raise@L127, return@L154, raise@L194
const: NAMES[17], BONES[18], SEGS[14], FACE_KEYS[3], _MA, _MB
main: __main__@L288  self_check@L283
up: pose_selfcheck
down: build_phase_gen,build_util,genqueue,pose_prompt,pose_selfcheck,骨架_行走
