# FILL pose   缺 5 槽位   （模型只填 pick，勿写散文）

## 处境 (context)
已填: 无
  (无候选 —— 若确无，填 `NEW: N/A 无记录`)
  pick: NEW: 行走姿态求解（相位/落脚/摆臂/侧倾），供骨架动画用

## 决定 (decided)
已填: 无
  [IMPROVE:IMPROVE_pose.md:L4] 1. **右脚相位不能用空间偏移 stride/2 平移** → 落脚点永远追不上髋（实测偏 2.07m）。
  [IMPROVE:IMPROVE_pose.md:L10] marker 用拼接 `_MA = "BEGIN EXA"+"MPLES"`。（第 5 次踩自检自指）
  [IMPROVE:IMPROVE_pose.md:L13] - pose 尚未接入 solver / build_video（骨架仍用旧绘制）
  [pose.py:L238] （用 stride/2 会把摆幅缩到 60%，业界实测手臂应与腿等幅反相）
  pick: IMPROVE_pose.md:5

## 否决方案 (neglected)
已填: 无
  [IMPROVE:IMPROVE_pose.md:L13] - pose 尚未接入 solver / build_video（骨架仍用旧绘制）
  [pose.py:L237] 归一化基准 = 支撑期脚相对髋的最大偏移 a，而非 stride/2
  pick: IMPROVE_pose.md:4

## 收益 (achieve)
已填: 无
  [IMPROVE:IMPROVE_pose.md:L4] 1. **右脚相位不能用空间偏移 stride/2 平移** → 落脚点永远追不上髋（实测偏 2.07m）。
  [IMPROVE:IMPROVE_pose.md:L6] 2. **触地瞬间浮点回绕**：`(t-t_start)/cycle % 1` 在 t≈t_start 时可能得 0.9999 → 判成 swing 末帧。
  [pose.py:L122] 铁律103：膝保持【落地屈膝角】，不可锁死 0°（业界 loading response 15~20°）
  [pose.py:L228] IK 起点 = 【实际髋点】（FK 中 l_hip/r_hip 的位置），不可再取骨盆中心
  pick: pose.py:238

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_pose.md:L5] 正确：左右脚**间隔都是一个完整 stride**，彼此差 half stride（side_off=step）。
  [IMPROVE:IMPROVE_pose.md:L9] 4. **扫描器自检自指**：`_scan_hardcode` 源码含示例区字面量，剔除逻辑会删掉自己 → 语法错误。
  [pose.py:L233] 手臂反相摆动（业界 counter-swing：手臂与同侧腿相位差半周期）
  [pose.py:L247] 躯干侧倾：向支撑侧倾（业界 3~5°），由双脚前后差驱动（铁律101）
  pick: IMPROVE_pose.md:6
