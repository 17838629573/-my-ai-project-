[FACT] pose_prompt   286行   机器生成，勿手改
doc: pose_prompt —— 轨迹 → 结构性提示词（铁律73：骨架图永不进画面）
api:
  L68 leg_state(joints,side,meta,gait,p)  # 单腿状态：全部由关节坐标算出（铁律74）。
  L107 arm_state(joints,side,p)  # 手臂前后摆：用【肘】相对肩的水平偏移判定（业界 counter-swing）。
  L122 describe(joints,meta,gait,facing,p)  # 把一帧姿态翻译成结构性英文提示词片段（不含身份段）。
  L155 frame_prompt(spec,mode,t,i,n,facing,p)  # 单帧完整提示词 = 身份段 + 姿态段 + 通用约束段。
  L170 sheet_prompts(spec,mode,n,facing,p)  # 一个完整周期的 n 帧提示词（等相位采样，含 contact 帧优先）。
  L187 self_check()
internal:
  L43 _need(d,key,where)
  L49 _ang(a,b,c)
  L59 _bend_word(deg,p)
  L182 _chk(name,ok,info)
calls_in: leg_state→_ang, leg_state→_bend_word, leg_state→_need, describe→arm_state, describe→leg_state, frame_prompt→_need, frame_prompt→describe, sheet_prompts→_need, sheet_prompts→frame_prompt, self_check→_chk, self_check→describe, self_check→leg_state, self_check→sheet_prompts
calls_out: gait,math,meta,out,parts,per,pose,y
guard: raise@L44, return@L61, return@L63, return@L115, return@L117
const: PARAMS[8], SIDE[2], COMMON='full-body side view, the whole figure from head to feet visible, feet on a shared ground contact line at the bottom of the frame, standing in place without drifting sideways, fixed camera, locked identity, same outfit and proportions as the reference'
main: __main__@L285  self_check@L187
up: pose
down: -
