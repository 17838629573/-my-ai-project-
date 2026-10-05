# 改进措施：风与步态统一（改前必读）

## 本轮实测抓到的三个"逻辑打架"

### 1. 三套 beaufort 并存，同风速最高差 1 级
- `_common.beaufort_scale` 区间表 / `physics.beaufort_level` 阈值数组 /
  `physics_rules.beaufort` (lo,hi,desc) 表，三套数值不同。
- `physics.beaufort_level` 还有 off-by-one：u=0.1 被判 1 级（应为 0 级）。
- 已修：后两者委托 `_common.beaufort_scale()`，14 档风速实测全一致。

### 2. 旗帜频率公式系数错约 13 倍（"抖成一片"根因）
- 旧 `flag_undulation_period(L,u,c=0.33)` → T=c·L/u，相当 St=3.0；
  文献 St_L≈0.23 → 快 13.2 倍。3 级风算出 5.33Hz。
- Strouhal 涡脱落给的是高频颤动 flutter(10-40Hz)，不是整体飘扬 flapping。
- 已修：`flag_motion(regime,u)` 按 regime 查表，
  3 级→0.43Hz、6 级→1.67Hz（MDPI 实测 6m/s≈2Hz 量级）。

### 3. 成片永远吃硬编码 0.585s（断链）
- `build_video` 读 `solver_out["T_flag"]`，但**全项目从不产出 T_flag**
  → 永远走兜底 0.585s(=1.71Hz，本属6级风)，套到3级风即"抖成一片"。
- 注释写着"从 solver 读，禁硬编码"却留兜底 —— 契约与代码不符。
- 已修：改读 `period_s`，缺失直接抛错（铁律18 禁静默兜底）。

## 走路/跑步：纯数值切换，不需要改代码
已实测通过，改 gait 三元组即可：
| 模式 | speed | stride | cycle | cadence |
|---|---|---|---|---|
| 慢走 | 1.0 | 1.20 | 1.200 | 100 |
| 常走 | 1.5 | 1.50 | 1.000 | 120 |
| 快走 | 2.0 | 1.70 | 0.850 | 141 |
| 慢跑 | 2.5 | 2.00 | 0.800 | 150 |
| 跑步 | 3.0 | 2.50 | 0.833 | 144 |
- 铁律69 强制 `cycle = stride / speed`。
- stride 上限 = 2·腿长/stance_ratio（1.70m 身高 → 2.782m），
  越界由 `hip_height` 抛错，不会算出生理不可达的步幅。

## 待办
- `flag_motion` 尚无调用方接入（solver 系的 `period_s` 来源待核对）。
- `_common_selfcheck.py:50` 仍用废弃的 `flag_undulation_period` 做自检。

---

---

---
## Y-Statement（gen:why_apply 勿手改）

meta: wind_unified
处境: 统一风场与步态口径，消除三套 beaufort / 旗帜频率 / 周期兜底三处逻辑打架
问题: 3. 成片永远吃硬编码 0.585s（断链）
决定: Strouhal 涡脱落给的是高频颤动 flutter(10-40Hz)，不是整体飘扬 flapping。
否决方案: 旧 `flag_undulation_period(L,u,c=0.33)` → T=c·L/u，相当 St=3.0；
收益: 已实测通过，改 gait 三元组即可：
代价: `flag_motion` 尚无调用方接入（solver 系的 `period_s` 来源待核对）。
依据出处: 已修：后两者委托 `_common.beaufort_scale()`，14 档风速实测全一致。
