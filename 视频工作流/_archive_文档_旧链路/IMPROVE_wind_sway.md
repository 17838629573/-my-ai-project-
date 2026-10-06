# IMPROVE · wind_sway.py 改前必读

## 真坑（踩过，别重犯）

### 坑1：不能用"层间幅度差"来证伪频率分离
我第一版用 `max(parts) - min(parts)` 判断同频是否失去层次，**FAIL**。
因为这个差主要来自 `amp_ratio`（0.08/0.25/0.60），**与频率无关**。
正确度量是**归一化波形的相关系数**：
- 三层同频 → corr = **1.0000**（各层同时到极值，整树僵硬一起摆）
- 三层分离 → corr = **-0.0102**
（本项目第 7 次遇到"自检度量选错"。改断言前先问：这个量真的随被测因素变化吗？）

### 坑2：通道分配不是定律，别硬编码
两篇 salivity 文章对 RGB 通道分配**互相矛盾**（一篇 R=trunk，另一篇 R=leaf）。
故本模块不引入通道概念，只用层名 trunk/branch/leaf。符合铁律32（知识外置）。

### 坑3：根部权重必须为 0，否则整树在地上滑
业界原话："Black/Zero Values 施加于根部，确保其牢牢锚定地面"。
权重函数一律 `t^exponent`，t=0 时恒 0。

## 待办

- `build_video.py` **没有树**，未调用 wind_sway
- 树是连续体，与 `chain`（幡旗/发丝/衣摆这类离散链）分工不同，别混用
- 未实现：WPO 包围盒扩展（业界提醒风摆会把顶点推出包围盒导致弹跳剔除）——
  我们做离线图，影响是**裁切**，落位时需预留摆幅余量
- 未实现：树与风的相位应和全局风向一致（铁律：风向全局唯一）

## 参数从哪来

`freq_hz` 中 trunk=0.26Hz 是**实测值**（10m 悬铃木带叶），非普适常数：
- 带叶 ζ≈8.6%、f₀≈0.26Hz
- **去叶后 f₀ 升到 ≈1.0Hz**（频率升 3 倍、阻尼降 6 倍）
换树种/季节必须重搜，别复用。

---

## 业界依据（真联网搜得，三个独立来源一致，从 contracts/wind_sway.md 剥离）

| 来源 | 要点 |
|---|---|
| salivity《Dynamic Wind Deformation for Game Vegetation》 | 顶点色作权重图：R=主干刚度(根0→顶1)、G=枝(关节0→梢1)、B=叶颤动；Alpha 存局部 pivot，使枝绕基部旋转而非整体扭曲 |
| 同上 | 分层：Macro Sway(低频正弦+世界坐标+平移 Perlin 噪声) / Secondary Oscillation(中频，按 pivot 相位错开) / Micro Flutter(高频噪声或交叉三角函数) |
| 同上 | 根部零权重确保不离地；WPO 包围盒需扩展，避免风摆把顶点推出包围盒导致弹跳剔除 |
| salivity《Making Foliage React to Wind》 | `Final Offset=(Trunk Wind×Blue)+(Branch Wind×Green)+(Leaf Flutter×Red)`；底层黑色=不动 |
| 同上 | 平移灰度噪声纹理按世界坐标采样，制造穿越地表的行进阵风；改天气只需改风速/强度/湍流三个全局量 |
| Unity TreeIT cginc（aubergine） | `objPhase=dot(objectWorldPos,1.0)` 物体级相位；`branchPhase=objPhase+anim.x`；频率常数 1.975/0.793/0.375/0.193 |
| 菜鸟编程网《风力模拟与随机性控制》 | `trunkOffset=windDir·w_trunk·0.08`；`branchOffset=windDir·w_branch·0.25·sin(3t+y·0.5)`；`leafOffset=windDir·w_leaf·0.6·sin(7t+x·2.1+z·2.1)`；**三层用完全不同的频率与时间缩放** |

---

---

---
## Y-Statement（gen:why_apply 勿手改）

meta: wind_sway
处境: 故本模块不引入通道概念，只用层名 trunk/branch/leaf。符合铁律32（知识外置）。
问题: 同上 | 根部零权重确保不离地；WPO 包围盒需扩展，避免风摆把顶点推出包围盒导致弹跳剔除 |
决定: ### 坑3：根部权重必须为 0，否则整树在地上滑
否决方案: salivity《Dynamic Wind Deformation for Game Vegetation》 | 顶点色作权重图：R=主干刚度(根0→顶1)、G=枝(关节0→梢1)、B=叶颤动；Alpha 存局部 piv
收益: 业界原话："Black/Zero Values 施加于根部，确保其牢牢锚定地面"。
代价: `build_video.py` **没有树**，未调用 wind_sway
依据出处: 业界依据（真联网搜得，三个独立来源一致，从 contracts/wind_sway.md 剥离）
