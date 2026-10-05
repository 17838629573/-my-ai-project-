# skeleton_runtime 改动史

## 缺失骨骼静默失效（实测，最严重）

`world_matrix` 对**不存在的骨骼**返回单位矩阵，**不报错**：

```python
b = self.bones.get(name)
if b is None:
    return [1.0, 0.0, 0.0, 0.0, 1.0, 0.0]   # 静默
```

后果：`systems.py` 写了摆臂代码

```python
pose["armL"] = {"rot": -leg_amp * amp * 0.6}
pose["armR"] = {"rot":  leg_amp * amp * 0.6}
```

但骨架只有 6 根骨，**没有 armL/armR** → 死代码，摆臂从未生效，无报错。

实测：

| 状态 | rot=+40 | rot=-40 |
|---|---|---|
| 缺失 | `[1,0,x, 0,1,y]` | `[1,0,x, 0,1,y]` ← 完全相同 |
| 补全 | `[0.8,-0.6, 235,780]` | `[0.8,0.6, 235,780]` ← 生效 |

修法三处：
1. 补 armL/armR（挂 torso，依 COCO 上肢链）
2. 槽位序改 `leg→arm→torso→head`，头盖躯干、躯干盖肩根
3. 加 `self.unknown` 记录 + `check_driven(sk, names)`，改骨架后必跑

## 骨骼集限制

8 根：root/hip/torso/head/legL/legR/armL/armR。
**无膝、无踝** → CoM-driven 的 IK 反解闭合不了，只能关节驱动。
