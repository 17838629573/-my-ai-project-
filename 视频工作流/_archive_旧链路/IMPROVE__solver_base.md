# WHY _solver_base   (结构化·禁散文)

meta: tier=SOLVE/base | 173行 | 上游0 下游8

## basis 依据（搜证值/公式出处；改常数前必看）
- 【铁律32 教训】A_OVER_L=1.6 是 Izawa 实测的 **flapping 态** 峰峰比，
- 现改为按风级查表，表由 AI 搜证后传入 criteria['amp_by_level']（铁律32）。
- 搜证来源：
- 【铁律47】业界搜证（contracts/sheet_cell.md）：
- 【诚实说明】我前几轮口头的"60–70% 安全区"未在本轮搜证中直接命中；命中的
- 故这里不硬编码单一百分比（铁律32），上下限均可由 AI 在 spec 中覆盖。

## trap 坑（勿回退 / 已修 / 冲突）
- 就该动。故由 AI 声明，缺失即报错（铁律31），不静默默认（铁律18）。
- 逐物体 solve 结果须携带同一 wind_dir，不一致即报错（禁各物体各吹各的）。
- AI 必填槽位（缺一即报错，铁律31）
- 兼容旧名

## intent 意图（为何存在）
基础层：共享常量 + 纯算术。零业务依赖。

## impact 改动影响（改本模块须回头验）
- 直接下游: _chk_base, _solver_chain, _solver_chain_aux, _solver_geom, _solver_probe, _solver_run, _solver_sheet, solver
- 验证命令: python3 impact.py _solver_base
