# FILL surface   缺 3 槽位   （模型只填 pick，勿写散文）

## 决定 (decided)
已填: 无
  [IMPROVE:IMPROVE_surface.md:L1] # IMPROVE_surface.md 表面与放置：业界方案与踩坑
  [IMPROVE:IMPROVE_surface.md:L3] ## 业界方案（本轮搜证）
  [IMPROVE:IMPROVE_surface.md:L4] 1. **Bao CVPR2010**：物体必须躺在支撑面上，且**物体法线平行支撑面法线**（n_obj // n_support）。
  [IMPROVE:IMPROVE_surface.md:L9] 4. **rule-based placement**（业界通用）：slope filter / height band / density mask /
  [IMPROVE:IMPROVE_surface.md:L19] ## 相机高不是手填，用参照物反解
  pick: IMPROVE_surface.md:4

## 收益 (achieve)
已填: 无
  [IMPROVE:IMPROVE_surface.md:L6] 2. **Footprints CVPR2020**：可行走面 = 语义类 mask + 深度图反投影。
  [IMPROVE:IMPROVE_surface.md:L7] → 树等不得落在可行走面上（RULES 的 exclusion）。
  [IMPROVE:IMPROVE_surface.md:L55] 放置任何物体前：先问 `_surface.place(kind)` 能不能算；不能算就补 RULES 或落盘物理量，
  pick: IMPROVE_surface.md:7

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_surface.md:L39] 但 v_h、参照物 y 目前仍来自外部——**须接背景图算**（见下）。
  pick: IMPROVE_surface.md:39
