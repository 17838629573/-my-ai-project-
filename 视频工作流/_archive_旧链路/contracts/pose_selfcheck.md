[S] pose_selfcheck @SHOT/skel  d1  in=1  gen:contract_gen
does: pose 的自检/检查逻辑（由 _extract_tool.py 从 pose.py 抽出）
api: self_check
impl: self_check → _scan_hardcode；内部helper 1个
up: pose
down: pose
edit: pose   # 改pose_selfcheck须同步核对这些文件
rule: T68 T69 T70 T72
why : IMPROVE_pose_selfcheck.md
