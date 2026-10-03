# driver —— 族判定与驱动器分派（先判族，再选驱动器）

## 依赖 / 被依赖
- 依赖: pose（biped/quadruped）、wind_sway（植被）、placement（注册点）、path（路径）、scale_map
- 被依赖: solver_survey（问卷输出提醒）、build_video（成片编排）
- 改前必读: IMPROVE_driver.md

## 铁律
- 铁律77 先判族，再选驱动器；禁对无骨骼物体生成骨架
- 铁律78 骨架永不进画面；无 control map 接口时姿态只能走结构性文本（承铁律73）
- 铁律79 族由 AI 判定，代码只校验并分派；族缺失即报错，禁默认 biped
- 铁律80 每族必须输出"AI 必做清单"，程序做不到的必须提醒，不许静默降级

## 族表（业界依据见 IMPROVE_driver.md）
| 族 | 有骨骼 | 驱动器 | 序列帧 | 生图方式 |
|---|---|---|---|---|
| biped | 有 humanoid | pose.solve | 需要 | 文本姿态 + 足端轨迹 |
| quadruped | 有 quadruped | pose（四足扩展） | 需要 | 文本姿态，四腿相位交错 |
| vegetation | 无 | wind_sway 顶点位移 | **禁** | 单图 + 程序化风摆 |
| rigid | 无 | 刚体位移 + 轮转 | **禁** | 单图 + 注册点定位 |
| cloth | 无 | 受迫链 | 需要 | 骨架（control map）或文本 |
