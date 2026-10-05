# IMPROVE_surface.md 表面与放置：业界方案与踩坑

## 业界方案（本轮搜证）
1. **Bao CVPR2010**：物体必须躺在支撑面上，且**物体法线平行支撑面法线**（n_obj // n_support）。
   → 落地成 NORMAL 表：wall_face 水平、wall_top/path/soil 朝上。
2. **Footprints CVPR2020**：可行走面 = 语义类 mask + 深度图反投影。
   → 树等不得落在可行走面上（RULES 的 exclusion）。
3. **GroundNet arXiv1811.07222**：单图估地平面法线 + 分割 + 深度。
4. **rule-based placement**（业界通用）：slope filter / height band / density mask /
   exclusion volume / clustering。→ 本模块的 RULES + offset_outside_path 即此路子。
5. **Projection 贴合表面**：物体落点投影到表面，而非浮空。

## 已落盘参数（搜证来源）
- `wall_height_m = 12.0 m`
  源：西安市地方志办公室《城墙鼓楼钟楼》"墙高12米、顶宽12~14米、底宽15~18米"
  区间 [8.5, 21.0]（襄阳8.5m；南京明城墙14~21m，最高26m）
- 此前已有：cloth_air_density / cloth_drag_coeff / cloth_lift_coeff / cloth_blowoff_ratio / area_m2

## 相机高不是手填，用参照物反解
camera_height_from_ref(1.70m, y_top=678, y_bot=878, v_h=300) → **H_cam = 4.913 m**
给一个已知高度的物体，代码自己算相机架在哪。

## 本轮实测
```
反解墙深：12m 墙顶要落 y=200 → 墙须在 z = 95.2 m
旗落点：('wall_top', x=270.0, y=200.0)   插墙顶 ✓
树落点：('soil',   x=210.7, y=369.3)     地面、退让路缘 3m ✓
```
墙顶 y 由「墙高12m × 该深度的 scale field」算出，**不是坐标常量**。

## 踩过的坑（改前必看）
### 坑1：墙顶算出负值，代码没拦
z=30m 处 12m 墙 → y_top = −17.5（跑出画面），**静默返回负值**。
修复：wall_top_y 加 image_h 校验，越界抛错并提示"增大墙深或降低墙高"。
**禁给负值、禁裁到边界了事**（铁律106）。

### 坑2：手填 z_m 仍是手填
`wall_depth_for_top(h_wall, y_top_target, ...)` 反解墙深，取代手填 z。
但 v_h、参照物 y 目前仍来自外部——**须接背景图算**（见下）。

### 坑3：硬编码锚点散落 4 文件（待替换）
- character_sheet.py:304 (0.20, 700)
- path_align.py:113/119 (0,700)(270,700)(539,700)
- scale_map.py:168 anchor_y_px=120；:224 anchor_y_px=5
- shot_plan.py:180 anchor_y_px=640；:181 path pts [(60,700),(240,690),(480,705)]

## 待办（按序）
1. 把 `_surface.place` 接进 shot_plan / scale_map / path_align，删上述硬编码。
2. v_h（地平线）与参照物须从背景图算（horizon_from_vanishing + 已知高度物体），
   目前素材已清空，重出背景图后接。
3. 旗物理点改正弦（线性爬升的问题未修，见 IMPROVE_wind_unified.md）。
4. 人物每帧追加足端语义（"左脚抬起13cm/摆动相"），目前只在末尾追加了 t=0 一行。

## 给 AI 的提示词
放置任何物体前：先问 `_surface.place(kind)` 能不能算；不能算就补 RULES 或落盘物理量，
**禁止直接写屏幕坐标**。缺物理量 → param_decl 会反问 → 必须联网搜证给来源+区间再落盘。

---

---

---
## Y-Statement（gen:why_apply 勿手改）

meta: surface
处境: exclusion volume / clustering。→ 本模块的 RULES + offset_outside_path 即此路子。
问题: 放置任何物体前：先问 `_surface.place(kind)` 能不能算；不能算就补 RULES 或落盘物理量，
决定: 1. **Bao CVPR2010**：物体必须躺在支撑面上，且**物体法线平行支撑面法线**（n_obj // n_support）。
否决方案: 5. **Projection 贴合表面**：物体落点投影到表面，而非浮空。
收益: → 树等不得落在可行走面上（RULES 的 exclusion）。
代价: 但 v_h、参照物 y 目前仍来自外部——**须接背景图算**（见下）。
依据出处: 禁止直接写屏幕坐标**。缺物理量 → param_decl 会反问 → 必须联网搜证给来源+区间再落盘。
