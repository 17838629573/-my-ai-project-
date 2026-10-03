# path · 路径约束（人只能在路上跑）

**状态**: 黄（新模块）

## 职责一句话

把角色位置表示为「路径弧长 s + 横向偏移 offset」，使其**永远在路径上**。

## 依赖 / 被依赖

- 依赖: (无本地依赖，只用 math)
- 被依赖: build_video, systems

## 改前必读

`IMPROVE_path.md` ← 业界搜证原文 + 真坑与待办，改这块前必读

## 接口（真实签名）

```python
catmull_rom(p0, p1, p2, p3, u) -> (x, y)
sample(pts, u) -> (x, y)
arc_table(pts, n=200) -> {"u":[...], "s":[...], "total":float}
at_distance(pts, s, table=None) -> {"xy","tangent","u","s"}
    # 等速移动必须用这个，不能用 sample(u)
project(pts, x, y, table=None) -> {"s","offset","xy","tangent"}
clamp_offset(offset, half_width) -> float
advance(s, ds, total) -> float
lookahead(pts, s, da, table=None) -> {"xy","tangent","s"}
self_check() -> int
```

## 铁律

- **铁律76**：角色位置用「路径弧长 s + 横向偏移 offset」表示，禁自由 (x,y)。
  不做"是否出界"的事后判断——位置由参数构成，天然不可能出界。
- **铁律77**：等速移动必须按**弧长**参数化，禁按 u（Catmull-Rom 的 u 非等速，
  按 u 推进会"远处快近处慢"）。
- **铁律78**：路径控制点由 AI 声明（背景图上哪条是路），代码不猜。

## 与 placement 的分工

- `placement`：语义点 → 世界落位（这东西放哪）
- `path`：路径参数 → 世界位置（这东西沿哪走、能偏离多少）

行走角色 = `placement.semantic_point` 定脚底语义点
         + `path.at_distance` 定该语义点该落在路径何处。
