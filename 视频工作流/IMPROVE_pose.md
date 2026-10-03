# IMPROVE_pose — 改这块前必读

## 真坑（都是踩过的）
1. **右脚相位不能用空间偏移 stride/2 平移** → 落脚点永远追不上髋（实测偏 2.07m）。
   正确：左右脚**间隔都是一个完整 stride**，彼此差 half stride（side_off=step）。
2. **触地瞬间浮点回绕**：`(t-t_start)/cycle % 1` 在 t≈t_start 时可能得 0.9999 → 判成 swing 末帧。
   已加 `if u > 1-1e-9: u = 0`。
3. **floor 边界**：`floor(0.0)` 遇 -1e-16 落到上一步。k 计算加 `+1e-9`。
4. **扫描器自检自指**：`_scan_hardcode` 源码含示例区字面量，剔除逻辑会删掉自己 → 语法错误。
   marker 用拼接 `_MA = "BEGIN EXA"+"MPLES"`。（第 5 次踩自检自指）

## 待办
- pose 尚未接入 solver / build_video（骨架仍用旧绘制）
- 站/坐/躺的 anthropometric 比例待 AI 搜证替换示例值
- 上肢（手臂摆动）未建模，仅下肢 IK
