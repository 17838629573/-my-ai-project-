# pose — 姿态与步态求解（关节空间 + 笛卡尔空间）

## 依赖 / 被依赖
- 依赖：无（纯标准库 math）
- 被依赖：solver（骨架关节）、build_video（人物落位）

## 改前必读
- `/data/workspace/视频工作流/IMPROVE_pose.md`（四个真坑 + 待办）

## 接口（全部为函数，禁硬编码坐标表 — 铁律72）
| 函数 | 输入（AI 搜） | 算出 |
|---|---|---|
| `bone_lengths(spec)` | 身高 + 人体比例 anthro | 各骨长（米） |
| `fk(root, L, angles)` | 根位置 + 骨长 + 关节角 | COCO-17 关节坐标 |
| `two_bone_ik(hip, tgt, L1, L2)` | 髋位 + 足端目标 | 大腿/小腿角 |
| `hip_height(gait, L)` | 步幅 + 支撑比 + 腿长 | 髋高（反算，不手填） |
| `foot_target(t, side, gait)` | 时刻 + 左右 + 步态参数 | 足端世界坐标 + 相位 |
| `solve(spec, mode, t)` | 场景 spec + 姿势名 | joints + meta |
| `blend_poses(a,b,w)` | 两姿势 + 权重 | 过渡姿势 |

## 铁律
- 68 足端轨迹在**笛卡尔空间**定义（Girard & Maciejewski 1985）：关节空间插值无法保证脚落点
- 69 速度-步幅-周期联算：`speed = stride / cycle`，髋高由步幅+腿长反算
- 70 支撑期（duty≈60%）脚**世界坐标恒定**，灭 foot sliding
- 71 站/坐/躺/走/跑统一为「骨长 FK + 关节角」，同一坐标系
- 72 禁硬编码关节坐标表；示例区除外（铁律37）
