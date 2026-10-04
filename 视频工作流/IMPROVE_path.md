# IMPROVE · path.py 改前必读

## 真坑（踩过，别重犯）

### 坑1：按 u 推进会让角色忽快忽慢（铁律77 的由来）
Catmull-Rom 的 u 参数**不是等速**的。控制点疏密不均时，同样 Δu 走过的距离差很多。
自检证伪实测：不等距控制点上按 u 采样，**间距相对离散 = 1.883**（最大间距是最小的近 3 倍）。
等速必须走 `arc_table` + `at_distance`（实测间距离散 = 0.0000）。

### 坑2：不要用"判断是否出界"来做路径约束
直觉做法是让角色自由移动，然后检查它在不在路上——这是事后补救，会抖、会卡边界。
业界（msell / Double Fine）做法是**位置本身由参数构成**：`位置 = 路径弧长 s + 横向偏移 offset`。
offset 经 `clamp_offset` 钳制，**天然不可能出界**，不需要任何判断。

### 坑3：弧长反查要二分，不要线性扫
`_u_of_s` 用二分查找。200 点的表线性扫在每个角色每帧都扫一遍，成本过高。

## 待办（还没接）

- `build_video.py` 仍在用 `x = sx - speed * t` 自由 xy，**未调用 path**
- `build_video.py` 的 `speed = 1.5 * px_per_m` 是手填，未与步态周期联算
  → 正确做法：`speed = stride_length / cycle_time`（业界公式）
- `pose.py` 的足端轨迹算出后，应与 `path.at_distance` 的弧长推进对齐（脚落点沿路径）
- 拐角 >45° 的过渡（Double Fine `SplinePrimitiveLookAhead` + cubic hermite）尚未实现

## 业界定律（可直接引用）

- `speed = stride_length / cycle_time`
- `cadence(步/分) = 120 / cycle_time`；步行 100–120，跑步 160–180
- 本项目曾硬编码 `T_MAN = 0.500` → cadence = 240 步/分，**超过跑步**，这是"脚跟瞬移"的量化根因

---

## 业界依据（真联网搜得，从契约移入）

| 来源 | 要点 |
|---|---|
| Double Fine《Psychonauts 2 Move Modes》 | spline-based move modes（Rail Slide / Tightrope / Ledge Hang）共用 `PhysSpline`：角色运动被约束在一条（可弯曲的）spline 上，函数负责保持正确 offset 与朝向 |
| 同上 | `SplinePrimitiveLookAhead` 检测 >45° 拐角时暂停 PhysSpline，改用 cubic hermite 插值过渡（指定起止位置/朝向/速度） |
| gamedev.stackexchange（AturSams） | 角色位置投影到最近 spline 得 p → 该处弧参 t_0 → 目标取 t_0+lookahead → seek 目标 → 到末端 clamp |
| 同上（msell） | "you are always on the path" —— 用可控 offset 表达，就不存在"是否还在路上"的判定问题 |
| 东北大学学报（改进双向 RRT*） | Catmull-Rom 分段三次：P(s)=c0+c1u+c2u²+c3u³，切线 τ 影响曲率，保证经过第二到倒数第二控制点 |
| Unity NavMesh / Off-Mesh Link | walkable area 之外不可达；Area Mask 可按角色类型限制可达区域 |

---

---

---
## Y-Statement（gen:why_apply 勿手改）

meta: path
处境: Double Fine《Psychonauts 2 Move Modes》 | spline-based move modes（Rail Slide / Tightrope / Ledge Hang）共用 `PhysSp
问题: 本项目曾硬编码 `T_MAN = 0.500` → cadence = 240 步/分，**超过跑步**，这是"脚跟瞬移"的量化根因
决定: 同上 | `SplinePrimitiveLookAhead` 检测 >45° 拐角时暂停 PhysSpline，改用 cubic hermite 插值过渡（指定起止位置/朝向/速度） |
否决方案: N/A 无记录（原文未记否决方案）
收益: offset 经 `clamp_offset` 钳制，**天然不可能出界**，不需要任何判断。
代价: Catmull-Rom 的 u 参数**不是等速**的。控制点疏密不均时，同样 Δu 走过的距离差很多。
依据出处: 自检证伪实测：不等距控制点上按 u 采样，**间距相对离散 = 1.883**（最大间距是最小的近 3 倍）。
