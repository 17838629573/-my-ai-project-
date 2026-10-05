# FILL path   缺 3 槽位   （模型只填 pick，勿写散文）

## 否决方案 (neglected)
已填: 无
  (无候选 —— 若确无，填 `NEW: N/A 无记录`)
  pick: NEW: N/A 无记录（原文未记否决方案）

## 收益 (achieve)
已填: 无
  [IMPROVE:IMPROVE_path.md:L13] offset 经 `clamp_offset` 钳制，**天然不可能出界**，不需要任何判断。
  [IMPROVE:IMPROVE_path.md:L26] ## 业界定律（可直接引用）
  [IMPROVE:IMPROVE_path.md:L38] | Double Fine《Psychonauts 2 Move Modes》 | spline-based move modes（Rail Slide / Tightrope / Ledge Hang）共用 `PhysSpline`：角色
  [IMPROVE:IMPROVE_path.md:L41] | 同上（msell） | "you are always on the path" —— 用可控 offset 表达，就不存在"是否还在路上"的判定问题 |
  [IMPROVE:IMPROVE_path.md:L42] | 东北大学学报（改进双向 RRT*） | Catmull-Rom 分段三次：P(s)=c0+c1u+c2u²+c3u³，切线 τ 影响曲率，保证经过第二到倒数第二控制点 |
  pick: IMPROVE_path.md:13

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_path.md:L6] Catmull-Rom 的 u 参数**不是等速**的。控制点疏密不均时，同样 Δu 走过的距离差很多。
  [path.py:L158] 3b 证伪：按 u 推进（错误做法）在不等距控制点上不等速
  pick: IMPROVE_path.md:6
