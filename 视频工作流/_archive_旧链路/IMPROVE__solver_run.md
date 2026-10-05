# WHY _solver_run   (结构化·禁散文)

meta: tier=SOLVE/sheet | 59行 | 上游4 下游2

## basis 依据（搜证值/公式出处；改常数前必看）
- 【铁律39】风向全局唯一：scene 顶层 wind.dir_deg 广播给每个物体
- 【铁律41】素材张数与排布必须发给 AI，否则 AI 不知道
- 【铁律52】输出帧数时必须同时问 AI：哪些帧可复用

## trap 坑（勿回退 / 已修 / 冲突）
- ? 待补

## intent 意图（为何存在）
编排：读 scene_spec.json 走完整流程，出每物体答案包。

## impact 改动影响（改本模块须回头验）
- 直接下游: _chk_base, solver
- 验证命令: python3 impact.py _solver_run
