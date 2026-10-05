# IMPROVE · puppet.py 改前必读

Status: Accepted（2026-10-04）· Supersedes: 无

## 真坑（踩过，别重犯）

### 坑1：图像域补帧必然重影，别再试
Unity URP 序列帧教程原话：**两帧线性混合本质上就是叠加，运动剧烈的帧之间会产生重影**。
所以 cross-dissolve 的重影是【业界已知固有缺陷】，不是实现问题。想靠调混合权重解决是死路。

### 坑2：pose.solve 只返回 17 个末端关节，没有 pelvis/neck
实测 `solve()["joints"]` 键只有 NAMES 那 17 个。
`PARTS` 里写 `("torso_lower","pelvis","neck")` 会直接 KeyError。
必须走 `with_derived()`：pelvis = 双髋中点，neck = 双肩中点（业界 Spine/Unity 2D rig 做法）。

### 坑3：pspec 必须和 _joint_seq 同构
直接传 `spec["biped_rig"]` 会报「缺必填槽位 spec.height_m」（铁律70）。
正确构造见 build_util.py:197：`{"height_m","anthro","face","poses","gait"}`，
且 gait 必须有 `cycle_s`（用 `_common.gait_cycle_from_speed` 算，禁手填）。

## 依据
- Spine/Unity 2D：角色拆 15~20 件，锚点放解剖关节（上臂锚=肩、前臂锚=肘、大腿锚=髋、小腿锚=膝）
- 2d-character-rig-animation：draw order 必须与 transform hierarchy 分离
- Animating a 2-D Zombie：相邻部件中立姿态下锚点必须重合，否则旋转时肢体滑动

## 实测
```
相邻视频帧最大角差  0.0529 rad = 3.03°
肘部锚点重合偏差     0.0000 px
16格离散=16个角度  vs  部件化480帧=480个连续角度
```
