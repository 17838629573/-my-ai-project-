# contract: 侧面行走骨架图集（gait_sheet）

## 依赖 / 被依赖
- 依赖: `pose.py`（FK/IK/足端轨迹）、`constants`
- 被依赖: `build_video.py`（消费人像素材帧）

## 业界依据（本轮搜证）
- Winter 1990 / Drillis & Contini 1966：人体环节长度占身高比，生物力学标准
  trunk 0.288H, head 0.130H, neck 0.052H, upperarm 0.186H, lowerarm 0.146H,
  hand 0.108H, thigh 0.245H, shank 0.246H, foot_height 0.039H
- 支撑相占步态周期 60%，摆动相 40%（业界一致）
- speed = stride / cycle，cadence = 120 / cycle（步行 100–120 步/分）
- Girard & Maciejewski 1985：足端轨迹必须在笛卡尔空间定义

## 铁律
- 73 行走素材必须是**侧视**（正面姿态配横向位移 = 倒着走的观感）
- 74 支撑期脚世界坐标恒定，foot_sliding 必须 = 0
- 75 半周期镜像复用：走路前后半周期姿态互为水平镜像，只需生半周期

## 接口
```python
build_gait_sheet(spec, n_half, grid) -> (图集路径, 帧数, 诊断dict)
```

## 改前必读
`IMPROVE_pose.md`（足端轨迹的 4 个真坑）
