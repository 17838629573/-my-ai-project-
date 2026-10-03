# sheet_cell — 图集每格「容纳性 + 先探针后升级」契约

## 铁律47：每格必须「容纳 + 留边 + 同尺度」，缺一即报错

| 项 | 默认 | 判据 | 抓什么 |
|---|---|---|---|
| `max_fill_w/h` | 0.80 | 主体 bbox 宽/高 ≤ 格宽/高 × 该值 | 溢出、触边 |
| `min_fill` | 0.25 | 主体 bbox 面积 ≥ 格面积 × 该值 | **历史 bug：banner_f33 前景占比 0.6% 却放行** |
| `margin_px` | 8 | 四边净边距 ≥ 该值 | 邻格渗透、抗锯齿接缝 |
| `centroid_policy` | "planted" | 见下 | 整体漂移抖动 |
| `area_spread`/`scale_spread`/`color_maxdist` | 0.35/0.25/60 | 探针一致性阈值，可被 spec 覆盖 | 帧间变异 |

### centroid_policy（AI 按物体声明，代码不猜）

- `planted`：质心漂移 ≤ `centroid_max`（格宽比例）。适用**角色/立足物**——
  动的是姿态，不是位置。
- `free`：不校验质心。适用**摆动件**（幡旗、枝条）——质心本来就该动，
  校验它等于把动画判违规。

**"质心动不动"是语义判断，不是算术**（铁律18）。缺 `centroid_policy` 即报错（铁律31）。

## 铁律48：先生探针图集，验过一致性才升级到全量帧数

```
probe 阶段：  n_probe = min(8, N)
             出图 → probe_check() → 一致性验 4 项
             任一 FAIL → 不许升级，重出探针
escalate：    通过后才按 N = round(T×FPS) 出全量图集
```

### probe_check 的 4 项一致性

| 项 | 度量 | 阈值 |
|---|---|---|
| 面积一致性 | 各格前景像素数 | 极差/均值 ≤ `area_spread`(0.35) |
| 尺度一致性 | 各格 bbox 宽高 | 极差/均值 ≤ `scale_spread`(0.25) |
| 配色一致性 | 各格前景主色(BGR 均值) | 两两距离 max ≤ `color_maxdist`(60) |
| 足迹一致性 | 各格质心 | planted 时 ≤ `centroid_max` |

## 代码接口

```python
CONTAINMENT = {...}                       # 默认值，可被 spec['containment'] 覆盖
containment_check(cell_bgra, cw, ch, pol) -> (ok, detail)
probe_plan(ans, probe_max=8) -> {"n_probe","n_full","probe_grid","full_grid","phase_map","order","rule"}
probe_check(sheet_path, cols, rows, n, pol) -> (ok, detail)
```

## 依赖

`_common`、`chroma`

## 被依赖

`solver`、`pipeline/sheet_pack`、`build_video`

## 改前必读

**`IMPROVE_sheet_cell.md`** —— 六条业界搜证原文、"60–70% 安全区"为何不硬编码、
探针两步法的实测依据。改本契约前必读。

## 相关契约

- `sheet_split.md`（铁律44）：本契约是其上游；`touches_edge` 与 `margin_px` 双保险。
- 铁律41：素材张数代码算；铁律40：一物体=一组图集，共用同一身份参考图。
