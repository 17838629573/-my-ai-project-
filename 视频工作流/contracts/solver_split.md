# 契约：solver 拆分（六个职责模块）

## 依赖（只写依赖/被依赖）
```
_solver_base   → 零业务依赖（常量 + 纯算术 wind_sign/_interp/_grid_for）
_solver_probe  → _solver_base
_solver_geom   → _solver_base, anchor
_solver_sheet  → _solver_base
_solver_reuse  → _solver_base, anchor
_solver_chain  → _solver_base, _solver_geom, physics, anchor, framerate
_solver_run    → _solver_base, _solver_chain, _solver_sheet, _solver_reuse
solver.py      → 全部（facade，对外 API 不变）
```
无环。被依赖方禁止反向 import（违反即门禁 FAIL）。

## 改前必读
- IMPROVE_solver_split.md（本轮真坑 + 待办）
- 改 `solve` 前先读 contracts/solver.md
- 新增族先登记 driver.py 的 FAMILY_REGISTRY
- 禁止在 solver 系写 px_per_m 内联，一律 `_common.to_px()`
