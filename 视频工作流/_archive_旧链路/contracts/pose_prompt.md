[S] pose_prompt @SHOT/skel  d3  in=0  gen:contract_gen
does: pose_prompt —— 轨迹 → 结构性提示词（铁律73：骨架图永不进画面）
api: leg_state, arm_state, describe, frame_prompt, sheet_prompts, self_check
const: PARAMS, SIDE, COMMON
impl: self_check → _chk → describe → leg_state；内部helper 4个
up: pose
edit: pose   # 改pose_prompt须同步核对这些文件
rule: T32 T73 T74 T75 T76
why : IMPROVE_pose_prompt.md
