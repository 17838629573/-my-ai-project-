# IMPROVE · contact_ik.py 改前必读

Status: Accepted（2026-10-04）· Supersedes: 无

## 真坑（踩过，别重犯）

### 坑1：我写错了断言，差点误判实现有问题（工具抓出来的）
第 5 项断言我最初写 `d <= (L1+L2)*MAX_EXT`。
但 exponential soft clamp 的**渐近上限是 L1+L2**，不是 (L1+L2)*MAX_EXT。
**是断言错，不是实现错** —— 不改会永久误报 FAIL。
现断言：`max=0.8200 <= 0.8200`（即 L1+L2）。

### 坑2：依赖被我画错了（依赖图工具抓出来的）
我最初把 X_h（末端 IK）写成依赖 X_a（足锁）。实际两者无关。
手到物体的 IK 不需要足部接触状态。错误依赖会让改动传播面无谓扩大。

### 坑3：两骨 IK 用余弦定理，不要引入 pole vector
theorangeduck 明确：用关节侧向量定旋转轴，避免极点翻转（pole flip）。
引入 pole vector 会在目标越过极点时整条肢体翻转 180°。

## 依据
- theorangeduck / InterControl：两骨 IK（hip-knee-heel、shoulder-elbow-wrist）余弦定理求解
- maxExtension + 指数 soft clamp 防超伸：目标不可达时停在略小于极限处，不硬拉伸

## 实测（self_check，7 项全过）
```
3 不可达标记为不可达 ok=False
4 soft clamp 单调不减 d=[0.5, 0.8193, 0.8198, 0.82]
5 soft clamp 渐近不超伸 max=0.8200 <= 0.8200
6 角度有限且为正 a1=0.884 a2=1.831
7 退化输入不崩 d=0.0200
```
