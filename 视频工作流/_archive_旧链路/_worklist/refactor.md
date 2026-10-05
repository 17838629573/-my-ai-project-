# FILL refactor   缺 5 槽位   （模型只填 pick，勿写散文）

## 处境 (context)
已填: 无
  [IMPROVE:IMPROVE_refactor.md:L1] # 复用抽取 + 超大模块拆分（本轮实做）
  [IMPROVE:IMPROVE_refactor.md:L11] | 旧模块 | 旧口径 | crop_top | 后果 |
  [IMPROVE:IMPROVE_refactor.md:L28] ### Q2：超 400 行是"聚合度太高"还是"模块混放"？
  [IMPROVE:IMPROVE_refactor.md:L30] **是模块混放，不是聚合度太高拆不出。** 证据（ast 实测）：
  [IMPROVE:IMPROVE_refactor.md:L32] | 模块 | 行数 | 最大函数 | 根因 |
  pick: IMPROVE_refactor.md:1

## 决定 (decided)
已填: 无
  [IMPROVE:IMPROVE_refactor.md:L1] # 复用抽取 + 超大模块拆分（本轮实做）
  [IMPROVE:IMPROVE_refactor.md:L3] ## 一、回答用户的两个问题
  [IMPROVE:IMPROVE_refactor.md:L7] **正确做法：抽成纯函数 + 把口径差异写成数据。**
  [IMPROVE:IMPROVE_refactor.md:L37] | solver_check.py | 613 | — | 应并入 _solver_selfcheck |
  [IMPROVE:IMPROVE_refactor.md:L46] 3. `_split_plan.py` —— 拆分方案（数据驱动，非口头）
  pick: IMPROVE_refactor.md:7

## 否决方案 (neglected)
已填: 无
  [IMPROVE:IMPROVE_refactor.md:L11] | 旧模块 | 旧口径 | crop_top | 后果 |
  [IMPROVE:IMPROVE_refactor.md:L40] **共性：自检/断言类代码占了 1/6 ~ 1/3，却和主算法同文件。**
  [IMPROVE:IMPROVE_refactor.md:L63] - solver.py **仍是 1173 行**：facade 已写好，但函数体尚未搬入 5 个 `_solver_*`。
  [IMPROVE:IMPROVE_refactor.md:L64] 原因：搬函数体需处理 29 个 def 的引用关系，本轮先立边界（桩+契约），避免边搬边改引入回归。
  pick: IMPROVE_refactor.md:5

## 收益 (achieve)
已填: 无
  [IMPROVE:IMPROVE_refactor.md:L5] ### Q1："10 处内联 px_per_m 不能机械替换"——这个说法是错的
  [IMPROVE:IMPROVE_refactor.md:L16] | scale_map.py | **可见高** | 196 | 正确 |
  [IMPROVE:IMPROVE_refactor.md:L17] | shot_plan.py | **可见高** | 196 | 正确 |
  [IMPROVE:IMPROVE_refactor.md:L73] > 差异几乎总是"画布总高 vs 可见高"口径不同。
  pick: IMPROVE_refactor.md:20

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_refactor.md:L7] **正确做法：抽成纯函数 + 把口径差异写成数据。**
  [IMPROVE:IMPROVE_refactor.md:L9] 实测量化出的口径差异：
  [IMPROVE:IMPROVE_refactor.md:L20] - 旗 2.5m：错误 2700px → 正确 **297px**
  [IMPROVE:IMPROVE_refactor.md:L21] - 人 1.70m：错误 1836px → 正确 **202px**
  [IMPROVE:IMPROVE_refactor.md:L25] 已建 `_px.py`：`px_per_m(ref_px, ref_m, crop_top)` 唯一入口 + `MIGRATE` 表（口径差异数据化）+ `to_px / to_m / world_y_from_canvas / canva
  pick: IMPROVE_refactor.md:63
