# 复用契约 reuse（铁律 81-85）

## 背景（为什么有这份）

审计发现：**同一段逻辑在 10+ 个模块被手写内联**。改一处要改 N 处，且各模块口径不一致。
典型病例：`px_per_m`（像素/米换算）出现 **10 次**，其中有的用"画布高"、有的用"可见高"，
导致同一物体在不同模块算出不同像素尺寸——**这就是旗帜比人大 2.3 倍的真实根因**。

## 铁律

### 铁律 81 —— 原子库单一定义
数学/几何/单位换算/运动学原子，**只允许在 `_common.py` 定义一次**。
业务模块 `from _common import X`，**禁止复制实现、禁止手写内联**。

已收拢原子（新增须登记）：
`clamp / lerp / smoothstep / catmull_rom / rad2deg / deg2rad / normalize_deg /
pixels_per_meter / meters_to_px / px_to_meters / beaufort_scale /
flag_undulation_period / gait_cycle_from_speed / cadence_bpm /
uniform_accel / projectile / phase_of / contact_shadow / require`

### 铁律 82 —— 改原子 = 改全局口径
`_common.py` 是全局口径源。**改它必须跑 `_audit_dup.py`**，确认内联归零、
行为与旧实现等价（自检含"等价性"用例）。

### 铁律 83 —— 模块长度软上限 400 行
超 400 行的模块必须拆分或抽取原子。
当前超上限（实测）：`solver.py` 1172、`systems.py` 669、`solver_check.py` 612、
`enforce.py` 448、`pose.py` 419、`chroma.py` 406。

### 铁律 84 —— 同名函数 = 债务
跨模块同名函数（除 `__` / `test` / `_` 前缀）视为重复债务，必须：
(a) 抽到 `_common`；(b) 或改名加模块前缀（如 `physics_accel`）。
当前债务清单（审计产出）：`accel`(2) `beaufort`(3) `describe`(2) `ck`(4) `contact_shadow`(2)
`add`(2) `detect`(2) `build_ctx`(2) `check_actors`(2)。

### 铁律 85 —— 扫描器不得自指
自检/扫描器**不得用自身源码的字符串字面量作为判定依据**（会扫到自己的示例而假 PASS）。
必须用 AST 或外部 fixture。已踩 7 次。

## 给 AI 的提示词（程序员交给 AI 的必做项）

> 新增任何"算一下"的逻辑前，先问：**这事 `_common.py` 里有没有？**
> 若有，import 它，不许重写。
> 若没有，先在 `_common.py` 建纯函数 + 在 `_common_selfcheck.py` 加用例，
> 再在业务模块调用。
> 禁止在业务模块里写 `def clamp`、写 `x % 360`、写 `180 / math.pi`。

## 给程序员的门禁（CI 必跑）

```
python _audit_dup.py      # 扫描内联原子 / 重复块 / 同名函数 / 超长模块
python _common_selfcheck.py
```
两项全绿才许合入。
