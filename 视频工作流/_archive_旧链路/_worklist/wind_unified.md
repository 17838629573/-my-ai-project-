# FILL wind_unified   缺 5 槽位   （模型只填 pick，勿写散文）

## 处境 (context)
已填: 无
  (无候选 —— 若确无，填 `NEW: N/A 无记录`)
  pick: NEW: 统一风场与步态口径，消除三套 beaufort / 旗帜频率 / 周期兜底三处逻辑打架

## 决定 (decided)
已填: 无
  [IMPROVE:IMPROVE_wind_unified.md:L8] - `physics.beaufort_level` 还有 off-by-one：u=0.1 被判 1 级（应为 0 级）。
  [IMPROVE:IMPROVE_wind_unified.md:L38] - `flag_motion` 尚无调用方接入（solver 系的 `period_s` 来源待核对）。
  [IMPROVE:IMPROVE_wind_unified.md:L39] - `_common_selfcheck.py:50` 仍用废弃的 `flag_undulation_period` 做自检。
  pick: IMPROVE_wind_unified.md:14

## 否决方案 (neglected)
已填: 无
  [IMPROVE:IMPROVE_wind_unified.md:L12] - 旧 `flag_undulation_period(L,u,c=0.33)` → T=c·L/u，相当 St=3.0；
  [IMPROVE:IMPROVE_wind_unified.md:L19] - `build_video` 读 `solver_out["T_flag"]`，但**全项目从不产出 T_flag**
  [IMPROVE:IMPROVE_wind_unified.md:L21] - 注释写着"从 solver 读，禁硬编码"却留兜底 —— 契约与代码不符。
  pick: IMPROVE_wind_unified.md:12

## 收益 (achieve)
已填: 无
  [IMPROVE:IMPROVE_wind_unified.md:L25] 已实测通过，改 gait 三元组即可：
  [IMPROVE:IMPROVE_wind_unified.md:L35] 越界由 `hip_height` 抛错，不会算出生理不可达的步幅。
  pick: IMPROVE_wind_unified.md:25

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_wind_unified.md:L5] ### 1. 三套 beaufort 并存，同风速最高差 1 级
  [IMPROVE:IMPROVE_wind_unified.md:L19] - `build_video` 读 `solver_out["T_flag"]`，但**全项目从不产出 T_flag**
  pick: IMPROVE_wind_unified.md:38
