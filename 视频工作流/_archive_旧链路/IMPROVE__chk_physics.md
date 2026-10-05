# WHY _chk_physics   (结构化·禁散文)

meta: tier=SOLVE/check | 78行 | 上游1 下游1

## basis 依据（搜证值/公式出处；改常数前必看）
- 1) 缺槽必须报错（铁律31：禁静默填默认）
- 2) 物性换算：唐绢 62 g/m2（AI 搜证值）
- 3) 帧数 = round(T*FPS)（铁律29）
- 4) St 定义自洽（铁律20）
- 4b)【铁律41】素材张数/排布/相位必须能发给 AI

## trap 坑（勿回退 / 已修 / 冲突）
- 1) 缺槽必须报错（铁律31：禁静默填默认）

## intent 意图（为何存在）
检查域1：缺槽报错/物性换算/帧数/St/固定端/相位均匀性。

## impact 改动影响（改本模块须回头验）
- 直接下游: solver_check
- 验证命令: python3 impact.py _chk_physics
