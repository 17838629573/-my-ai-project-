# WHY _chk_motion   (结构化·禁散文)

meta: tier=SOLVE/check | 81行 | 上游1 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 28) 扬角 Rule of 4（铁律32：形态由 U 决定，不是常数）
- 30) 风向全局一致（铁律39）

## trap 坑（勿回退 / 已修 / 冲突）
- 27) run_spec 的契约文件缺 '物体' 必须报错
- 29) 振幅比 A/L 随 U 变（回归旧 bug：A_OVER_L=1.6 常数导致小风也大摆）
- 31) run_spec 广播风向：物体自带不同 wind_dir 必须报错

## intent 意图（为何存在）
检查域5：run_spec 契约/扬角/振幅比/风向全局一致。

## impact 改动影响（改本模块须回头验）
- 直接下游: solver_check
- 验证命令: python3 impact.py _chk_motion
