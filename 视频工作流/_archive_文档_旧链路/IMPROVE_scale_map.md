# scale_map 改进措施（改前必读）

## 真坑
1. 问卷原不问真实尺寸 → AI 凭印象填像素 → 旗比城门大 2.3 倍
2. inventory 用 `name`、assemble 用 `物体` → 两阶段键名不一致，已用 `_qname()` 归一
3. composite 自检空 FAIL 也打印标题 → 误导为失败，已修

## 待办
- composite 落位仍收原始像素，未按 target_px resize（下一步）

---

---

---
## Y-Statement（gen:why_apply 勿手改）

meta: scale_map
处境: 统一各物体真实尺寸与像素的映射，防止比例失调
问题: 1. 问卷原不问真实尺寸 → AI 凭印象填像素 → 旗比城门大 2.3 倍
决定: 2. inventory 用 `name`、assemble 用 `物体` → 两阶段键名不一致，已用 `_qname()` 归一
否决方案: 1. 问卷原不问真实尺寸 → AI 凭印象填像素 → 旗比城门大 2.3 倍
收益: 5 verify 能拦住 2.3 倍失调（本轮真实 bug）
代价: composite 落位仍收原始像素未按 target_px resize（IMPROVE_scale_map.md:9 待办）
依据出处: 用 AI 搜证的唐代真实尺寸构造（非硬编码常量，仅自检用例）
