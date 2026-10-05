# FILL common   缺 4 槽位   （模型只填 pick，勿写散文）

## 处境 (context)
已填: 无
  [IMPROVE:IMPROVE_common.md:L5] 1. 写了 `_audit_dup.py`，**真实扫描**全部 22 个活跃模块：
  [IMPROVE:IMPROVE_common.md:L9] - 超 400 行软上限的模块
  [IMPROVE:IMPROVE_common.md:L11] 3. 建 `_common_selfcheck.py`（38 用例，ALL PASS），含**与旧内联实现的等价性验证**。
  [IMPROVE:IMPROVE_common.md:L18] 各模块手写 `px_per_m = 画布高 / 视场高`，但有的用**画布总高**、有的用**可见高**（未扣顶部留天）。
  [IMPROVE:IMPROVE_common.md:L44] - `px_per_m` 在 10 个**旧**模块仍是内联 —— 需按 `_migrate_common.py` 清单逐项改，
  pick: IMPROVE_common.md:18

## 否决方案 (neglected)
已填: 无
  [IMPROVE:IMPROVE_common.md:L10] 2. 建 `_common.py`（193 行），收拢 19 个原子。
  [IMPROVE:IMPROVE_common.md:L11] 3. 建 `_common_selfcheck.py`（38 用例，ALL PASS），含**与旧内联实现的等价性验证**。
  [IMPROVE:IMPROVE_common.md:L18] 各模块手写 `px_per_m = 画布高 / 视场高`，但有的用**画布总高**、有的用**可见高**（未扣顶部留天）。
  [IMPROVE:IMPROVE_common.md:L19] → 新增 `crop_top` 参数，并写入铁律 82：**改原子须跑审计确认归零**。
  [IMPROVE:IMPROVE_common.md:L27] 原表随手填，未归一化 → 骨长算错。
  pick: IMPROVE_common.md:18

## 收益 (achieve)
已填: 无
  [IMPROVE:IMPROVE_common.md:L18] 各模块手写 `px_per_m = 画布高 / 视场高`，但有的用**画布总高**、有的用**可见高**（未扣顶部留天）。
  [IMPROVE:IMPROVE_common.md:L45] **不能机械替换**（口径差异会改变行为），须人工确认 crop_top。
  pick: IMPROVE_common.md:11

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_common.md:L18] 各模块手写 `px_per_m = 画布高 / 视场高`，但有的用**画布总高**、有的用**可见高**（未扣顶部留天）。
  [IMPROVE:IMPROVE_common.md:L35] 绝大多数是**滑动窗口自匹配**（L211-216 与 L212-217 差一行），属误报；
  [IMPROVE:IMPROVE_common.md:L45] **不能机械替换**（口径差异会改变行为），须人工确认 crop_top。
  pick: IMPROVE_common.md:44
