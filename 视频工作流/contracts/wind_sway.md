# wind_sway · 植物风摆（程序化，不做序列帧）

**状态**: 黄（新模块）

## 职责一句话

把植物位移拆成 trunk / branch / leaf 三层，各层独立频率叠加，根部权重恒为 0。

## 依赖 / 被依赖

- 依赖: (无本地依赖，只用 math)
- 被依赖: build_video, systems

## 改前必读

`IMPROVE_wind_sway.md` ← 三层比例来源、通道分配争议、真坑，改这块前必读

## 接口（真实签名）

```python
layer_weight(t, layer, exponent) -> float
    # t=归一化长度∈[0,1]（0=根部 1=梢）；根部恒 0
phase_of(world_xy, salt=0.0) -> float
    # 由世界坐标派生相位，个体间去同步
sway_offset(t, time_s, wind, layer, cfg) -> float
wind_sway(t, time_s, wind, cfg, world_xy=None) -> {"dx","dy","parts"}
self_check() -> int
```

## 铁律

- **铁律79**：植物风摆用程序化三层叠加，**禁止生成序列帧**（形态连续变化、帧数爆炸）。
- **铁律80**：根部权重恒为 0，禁止整体平移（根部一动就是整棵树在地上滑）。
- **铁律81**：三层频率必须分离，禁同频。给定比例 trunk 低频 / branch ≈3× / leaf ≈7×。
- **铁律82**：个体相位由世界坐标派生，禁全局同相（所有树同步摆最刺眼）。

## 注意：通道分配不是定律

两篇 salivity 文章对 RGB 通道分配**互相矛盾**（一篇 R=trunk，另一篇 R=leaf）。
故本模块**不引入通道概念**，只用层名 trunk/branch/leaf——避免把约定当定律硬编码。

## 与 chain 的分工

- `chain`（solver 内）：离散刚体链，适合幡旗/发丝/衣摆（层级明确、数量少）
- `wind_sway`：连续体，适合树/草/灌木（顶点连续、数量多）
