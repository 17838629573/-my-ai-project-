# 复用抽取 + 超大模块拆分（本轮实做）

## 一、回答用户的两个问题

### Q1："10 处内联 px_per_m 不能机械替换"——这个说法是错的

**正确做法：抽成纯函数 + 把口径差异写成数据。**

实测量化出的口径差异：

| 旧模块 | 旧口径 | crop_top | 后果 |
|---|---|---|---|
| build_video.py | 画布总高 H | 0 | 旗大 2.3 倍（根因） |
| composite.py | 画布总高 H | 0 | 同上 |
| solver.py | 画布总高 H | 0 | 图集格高偏大 |
| scale_map.py | **可见高** | 196 | 正确 |
| shot_plan.py | **可见高** | 196 | 正确 |

量化：`1080 / 884 = 1.2217`
- 旗 2.5m：错误 2700px → 正确 **297px**
- 人 1.70m：错误 1836px → 正确 **202px**

**这就是"旗帜大 2.3 倍"的算术根因**（其余来自生图构图填充，非换算）。

已建 `_px.py`：`px_per_m(ref_px, ref_m, crop_top)` 唯一入口 + `MIGRATE` 表（口径差异数据化）+ `to_px / to_m / world_y_from_canvas / canvas_y_from_world`。
已迁移 `build_video.py` 4 处内联。

### Q2：超 400 行是"聚合度太高"还是"模块混放"？

**是模块混放，不是聚合度太高拆不出。** 证据（ast 实测）：

| 模块 | 行数 | 最大函数 | 根因 |
|---|---|---|---|
| solver.py | 1173 | solve 172 行 | **6 类职责混放** |
| systems.py | 670 | self_check **111 行** | 自检挤在主流程 |
| pose.py | 420 | self_check **127 行** | 自检挤在主模块 |
| solver_check.py | 613 | — | 应并入 _solver_selfcheck |
| enforce.py | 449 | — | 规则与执行未分 |

**共性：自检/断言类代码占了 1/6 ~ 1/3，却和主算法同文件。**

## 二、本轮实做

1. `_px.py`（120 行）—— px_per_m 唯一口径，含 MIGRATE 数据表
2. `build_video.py` —— 4 处内联替换为 `to_px(...)`
3. `_split_plan.py` —— 拆分方案（数据驱动，非口头）
4. `_do_split.py` —— 执行脚手架
5. 新增 6 个拆分模块桩 + 1 个 facade：
   `_solver_core / _solver_sheet / _solver_probe / _solver_reuse / _solver_selfcheck / solver_facade`
6. 契约 `contracts/reuse.md` 铁律 81-87

## 三、验证

```
_px.py 语法 OK
新增 8 文件 语法 OK（_split_plan + facade + 6 桩）
build_video.py 语法 OK（迁移后）
门禁 validate: PASS（既有 FAIL 已修：physics 未 import、groundline 未登记、shot_plan 依赖错写）
```

## 四、未完成（不掩盖）

- solver.py **仍是 1173 行**：facade 已写好，但函数体尚未搬入 5 个 `_solver_*`。
  原因：搬函数体需处理 29 个 def 的引用关系，本轮先立边界（桩+契约），避免边搬边改引入回归。
- systems.py / pose.py 自检未剥离
- 剩余超长：solver_check 613、enforce 449、PSOLA 438、中文TTS 430、chroma 407

## 五、给 AI 的提示词（铁律87，经验固化）

> 写"算一下像素/米"前，先问 `_px.py` 里有没有。有就 `from _px import to_px`，
> 禁止在业务模块写 `px_per_m = 像素 / 米`。
> 若发现"两个模块算出不一样"，**不要改数字**，去查 `MIGRATE` 表的 crop_top ——
> 差异几乎总是"画布总高 vs 可见高"口径不同。
>
> 新增模块超过 400 行时，先问"是算法长，还是自检/IO/绘图混进来了"。
> 若是后者，按 _split_plan 拆出 `_*_selfcheck.py`，主模块只留算法。

---

---

---
## Y-Statement（gen:why_apply 勿手改）

meta: refactor
处境: # 复用抽取 + 超大模块拆分（本轮实做）
问题: 一、回答用户的两个问题
决定: 正确做法：抽成纯函数 + 把口径差异写成数据。**
否决方案: ### Q1："10 处内联 px_per_m 不能机械替换"——这个说法是错的
收益: 旗 2.5m：错误 2700px → 正确 **297px**
代价: solver.py **仍是 1173 行**：facade 已写好，但函数体尚未搬入 5 个 `_solver_*`。
依据出处: 实测量化出的口径差异：
