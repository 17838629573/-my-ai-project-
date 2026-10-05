# IMPROVE · oneshot.py 改前必读

Status: Accepted（2026-10-04）· Supersedes: 无

## 真坑（踩过，别重犯）

### 坑1：一次性动作被 stop 后必须真的停下
实测：挥手播放中途调用 stop → `completed=False`、且**不再继续推进**。
旧实现 stop 只置标志位不复位时间轴，导致动作"停了但还在走"。

### 坑2：duration<=0 / Notify 越界 必须报错，不能静默
第 9、10 项自检锁死。静默会让上层以为动作播完了，实际什么都没发生。

### 坑3：blend_in / blend_out 包络必须对称可验
第 11、12 项：中点权重 w=0.50。包络不对称会在起手/收手时看到速度突变。

## 依据
- UE / Unity 通行做法：Montage + Slot + AnimNotify
  - Montage：打断当前状态机、播一段、播完回原状态
  - Slot：把 Montage 姿态插入 AnimGraph，不打断底层 locomotion
- 本模块取路线 A；相位匹配（Motion Matching）留给后续

## 实测（self_check，12 项全过）
```
8 release 后无占用
9 duration<=0 报错      10 Notify 越界报错
11 blend_in 包络 w=0.50  12 blend_out 包络 w=0.50
```
