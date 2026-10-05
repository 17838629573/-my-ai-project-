# WHY _chk_base   (结构化·禁散文)

meta: tier=SOLVE/check | 96行 | 上游10 下游10

## basis 依据（搜证值/公式出处；改常数前必看）
- 铁律89：自检直接依赖真实算法模块，不走 solver facade（破 solver<->selfcheck 环）
- 唐绢 62 g/m2、旗 0.90x0.30 m、U=12.3 m/s（AI 搜证值，勿随意改）

## trap 坑（勿回退 / 已修 / 冲突）
- 唐绢 62 g/m2、旗 0.90x0.30 m、U=12.3 m/s（AI 搜证值，勿随意改）

## intent 意图（为何存在）
solver 自检公共层：共享 import + _r 断言器。

## impact 改动影响（改本模块须回头验）
- 直接下游: _chk_assemble, _chk_chain, _chk_motion, _chk_multi, _chk_pack, _chk_physics, _chk_reuse, _chk_sheet, _chk_survey, solver_check
- 验证命令: python3 impact.py _chk_base
