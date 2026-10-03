# placement · 语义定位点（Registration Point）

**状态**: 黄（新模块）

## 职责一句话

把「一个语义点」→「世界坐标落位」。不画像素，只算坐标。

## 依赖 / 被依赖

- 依赖: (无本地依赖，只用 math)
- 被依赖: build_video, composite, scale_map

## 改前必读

`IMPROVE_placement.md` ← 业界搜证原文 + 真坑与待办，改这块前必读

## 接口（真实签名）

```python
SEMANTIC_KINDS  -> tuple
semantic_point(kind, canvas_w, canvas_h, shape=None) -> (u, v)
    # kind 不在 SEMANTIC_KINDS 内 -> ValueError
place(regpoint, target_xy, scale=None) -> dict
    # regpoint = {"kind","canvas_w","canvas_h","trim":(tx,ty,tw,th)|None}
    # 返回 {"x0","y0","w","h"} 落位矩形左上角 + 尺寸
attach_point(kind, canvas_w, canvas_h, ratio=None) -> (u, v)
    # 附着类语义点（旗杆底、轮胎接地、根部），ratio 由 AI 声明
self_check() -> int
```

## 语义点类型

| kind | 含义 | 适用 | 源坐标 (u,v) |
|---|---|---|---|
| `ground_contact` | 底部中心接地点 | 人、兽、车 | `(w/2, h)` |
| `base` | 基座/杆底中心 | 旗杆、灯柱 | `(w/2, h)` |
| `root` | 根部中心 | 树、草 | `(w/2, h)` |
| `center_mass` | 质心 | 悬浮物、飞鸟 | `(w/2, h/2)` |
| `attach` | 附着点（AI 给比例） | 挂件、背包、武器 | `(w*rx, h*ry)` |

`ground_contact` 与 `base` 源坐标公式相同但语义不同：前者"被重力压在地面"，
后者"被固定在支撑物顶面"；渲染都对齐支撑面，但 `attach` 校验规则不同。

## 铁律

- **铁律73**：先命名语义点类型再转坐标，禁止逐帧自动居中（归一化 0.5 在不同裁剪矩形上指向不同源位置）。
- **铁律74**：语义点从未裁剪源画布测量，裁剪后保留 trim offset。
- **铁律75**：接地点 ≠ 最低 alpha 像素；它是设计出来的接触点（跑步有双脚离地帧）。

## 反例（本模块要防的）

修"跨帧漂移 269px"时用过**逐帧居中对齐**——那正是业界禁止的 auto-centering。
正确做法：固定源画布 + 单一语义点 + 逐帧复用同一 regpoint。
