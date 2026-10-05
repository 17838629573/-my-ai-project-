# FILL sheet_cell   缺 2 槽位   （模型只填 pick，勿写散文）

## 否决方案 (neglected)
已填: 无
  [IMPROVE:IMPROVE_sheet_cell.md:L3] 本文件是 `contracts/sheet_cell.md` 的**详解层**：业界搜证原文 + 踩坑。
  [IMPROVE:IMPROVE_sheet_cell.md:L8] ## 一、本轮搜证（业界依据，逐条原文要点）
  [IMPROVE:IMPROVE_sheet_cell.md:L17] | AutoSprite FAQ | 中 | "Six to twelve frames covers most 2D loops"；更多帧=更平滑但纹理更大 |
  [IMPROVE:IMPROVE_sheet_cell.md:L44] `n_probe = min(8, N)` —— 业界原话："8 格能解决的事不要上 16 格"。
  [IMPROVE:IMPROVE_sheet_cell.md:L50] 1. **banner_f33 前景占比 0.6% 却放行** —— 当时只校验了上界没校验下界，
  pick: IMPROVE_sheet_cell.md:44

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_sheet_cell.md:L17] | AutoSprite FAQ | 中 | "Six to twelve frames covers most 2D loops"；更多帧=更平滑但纹理更大 |
  [IMPROVE:IMPROVE_sheet_cell.md:L52] 2. **质心校验误判摆动件** —— 幡旗质心本来就该动，一刀切校验等于把正确动画判违规。
  pick: IMPROVE_sheet_cell.md:52
