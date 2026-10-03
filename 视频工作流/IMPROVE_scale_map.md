# scale_map 改进措施（改前必读）

## 真坑
1. 问卷原不问真实尺寸 → AI 凭印象填像素 → 旗比城门大 2.3 倍
2. inventory 用 `name`、assemble 用 `物体` → 两阶段键名不一致，已用 `_qname()` 归一
3. composite 自检空 FAIL 也打印标题 → 误导为失败，已修

## 待办
- composite 落位仍收原始像素，未按 target_px resize（下一步）
