# WHY shot_plan   (结构化·禁散文)

meta: tier=SHOT/gen | 230行 | 上游4 下游3

## basis 依据（搜证值/公式出处；改常数前必看）
- 4 证伪：手填落位（整体平移 50px）必须被 verify 判不一致（铁律84）
- 5 提示词含米制（铁律85）
- 6 偏移钳制生效（铁律76：不可能出界）

## trap 坑（勿回退 / 已修 / 冲突）
- ? 待补

## intent 意图（为何存在）
镜头规划 / 生图任务包：告诉 AI 路画在哪、物体多大、落在哪、提示词怎么写。

## impact 改动影响（改本模块须回头验）
- 直接下游: build_phase_gen, build_util, build_video
- 验证命令: python3 impact.py shot_plan
