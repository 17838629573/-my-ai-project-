# IMPROVE_common —— 复用审计（2026-10-03）

## 本轮真实动作（不是思考，是做了）

1. 写了 `_audit_dup.py`，**真实扫描**全部 22 个活跃模块：
   - 内联数学原子
   - ≥6 行重复代码块（发现 **1443** 处）
   - 同名函数
   - 超 400 行软上限的模块
2. 建 `_common.py`（193 行），收拢 19 个原子。
3. 建 `_common_selfcheck.py`（38 用例，ALL PASS），含**与旧内联实现的等价性验证**。
4. 建 `contracts/reuse.md`（铁律 81-85）。
5. 建 `_migrate_common.py`，输出迁移清单（当前 0 处待迁，因本轮新建文件已直接调用）。

## 抓到的真问题（量化）

### ① px_per_m 出现 10 次，口径不一致 —— 旗帜大 2.3 倍的根因
各模块手写 `px_per_m = 画布高 / 视场高`，但有的用**画布总高**、有的用**可见高**（未扣顶部留天）。
→ 新增 `crop_top` 参数，并写入铁律 82：**改原子须跑审计确认归零**。

### ② T_MAN 硬编码 0.5s → cadence = 240 步/分
步行业界区间 100-120，跑步 160-180。**240 超过跑步，逼近极限**。
→ 新增 `gait_cycle_from_speed(speed, stride)`：由速度反推周期，废掉硬编码。
  验证：`gait_cycle_from_speed(1.5, 1.5) = 1.0s` → cadence=120 ✅

### ③ 人体比例表加起来 ≠ 1（1.318）
原表随手填，未归一化 → 骨长算错。
→ 改为归一化，`LEG_RATIO = 腿长 / 全身`（0.345，业界 0.33-0.36）。

### ④ 扫描器自指污染（第 7 次踩）
`_audit_dup.py` 初版用 `split("BEGIN EXAMPLES")` 切自身源码，扫到自己的示例 → 假 PASS。
→ 铁律 85：扫描器不得自指，须用 AST / 外部 fixture。

### ⑤ 重复块 1443 处
绝大多数是**滑动窗口自匹配**（L211-216 与 L212-217 差一行），属误报；
真重复集中在：`_bak_solver_pre2.py` vs `solver.py` **整段复制**（约 12 处 4 次重复）。
→ **_bak 必须归档或删除**，它是重复源。

## 遗留（不掩盖）

- `solver.py` 1172 行、`systems.py` 669 行、`solver_check.py` 612 行 —— 未拆
- 同名函数债务仍在：`beaufort`(3) `ck`(4) `contact_shadow`(2) `describe`(2) `accel`(2)
  （已在契约点名，待逐项抽 `_common`）
- `px_per_m` 在 10 个**旧**模块仍是内联 —— 需按 `_migrate_common.py` 清单逐项改，
  **不能机械替换**（口径差异会改变行为），须人工确认 crop_top。

## 给 AI 的必做提示词（已写入契约）

> 写"算一下"的逻辑前，先问：`_common.py` 里有没有？
> 有 → import，禁止重写。
> 没有 → 先在 `_common` 建纯函数 + 加自检用例，再调用。
> 禁止在业务模块写 `def clamp`、写 `x % 360`、写 `180 / math.pi`。

## 给程序员的门禁（CI）

```
python _audit_dup.py           # 内联/重复块/同名/超长
python _common_selfcheck.py    # 原子正确性 + 等价性
```
全绿才许合入。

---

---

---
## Y-Statement（gen:why_apply 勿手改）

meta: common
处境: 各模块手写 `px_per_m = 画布高 / 视场高`，但有的用**画布总高**、有的用**可见高**（未扣顶部留天）。
问题: → 新增 `gait_cycle_from_speed(speed, stride)`：由速度反推周期，废掉硬编码。
决定: → 改为归一化，`LEG_RATIO = 腿长 / 全身`（0.345，业界 0.33-0.36）。
否决方案: 各模块手写 `px_per_m = 画布高 / 视场高`，但有的用**画布总高**、有的用**可见高**（未扣顶部留天）。
收益: 3. 建 `_common_selfcheck.py`（38 用例，ALL PASS），含**与旧内联实现的等价性验证**。
代价: `px_per_m` 在 10 个**旧**模块仍是内联 —— 需按 `_migrate_common.py` 清单逐项改，
依据出处: IMPROVE_common —— 复用审计（2026-10-03）
