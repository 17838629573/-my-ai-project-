# WHY loop_engine   (结构化·禁散文)

meta: tier=SHOT/loop | 328行 | 上游1 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 铁律26：无自检 = 不通过。契约见 contracts/loop_engine.md
- 5) 铁律28：fps 取 framerate.FPS，不写死

## trap 坑（勿回退 / 已修 / 冲突）
- 4) 禁用系统零调用（按需真的省了）

## intent 意图（为何存在）
按需调度引擎 —— 解决"全量跑"问题

## impact 改动影响（改本模块须回头验）
- 直接下游: render_v4
- 验证命令: python3 impact.py loop_engine
