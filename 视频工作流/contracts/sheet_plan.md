# sheet_plan — 图集规划（视频帧率 + 多帧合图）

状态：黄（有契约、有自检；无实图渲染证据）

## 定位

`solver.sheet_plan(spec, ans)` 把「生成张数」翻译成「要画几张图、每张几格」。
**AI 只负责按图集规格生图，不负责决定帧数、网格、格尺寸。**

- 代码：素材张数（物理定）→ 生成张数（复用定）→ **图集规格（网格/格像素/张数）**
- AI：搜物性填槽 + 按图集规格生图 + 提供身份参考图

## 铁律

- **铁律54**：视频帧率不做 16 帧封顶。`mat_frames = round(T·FPS)` 全量，
  禁 `min(N,16)`（`MAX_MAT_FRAMES=16` 是游戏值）。
- **铁律55**：多帧必须合图，禁逐帧单图。同一张图内模型只做一次构图决策。
- **铁律56**：单张图集格数上限由 AI 声明，默认 16（模型能力，非代码常量）。
  超限拆多张图集，**共用同一张身份参考图**。
- **铁律57**：长宽比 > 2 的物体走 strip（1 行 N 列），禁塞方形格。

（业界依据与历史反例见 `IMPROVE_sheet_plan.md`）

## 接口

```python
sheet_plan(ans, spec, max_cells=None, cell_px=None) -> {
  "gen_frames": int,        # 需生成的张数（复用后）
  "mat_frames": int,        # 素材张数 = round(T·FPS)，视频不封顶
  "play_frames": int,       # 播放帧数 = round(T·FPS)
  "max_cells": int,         # 单张图集格数上限（AI 可覆盖，默认 16）
  "n_sheets": int,
  "sheets": [
    {"idx":0, "rows":R, "cols":C, "cells":R*C,
     "cell_px":[w,h], "sheet_px":[W,H], "padding":2,
     "frame_range":[start,end], "layout":"grid"|"strip",
     "bg":"#FF00FF"}, ...
  ],
  "shared_reference": "所有图集共用同一张身份参考图（铁律55）",
}
```

## 尺寸约束

- 单张 sheet ≤ 2048×2048；超了降 cell_px，不许超上限
- 格间 padding = 2 px（防 texture bleeding）
- sheet_px = cols*cell_px[0] + (cols-1)*padding（行同理）

## 自检项

- mat_frames == round(T·FPS)，且**未被 16 封顶**（注入 T=0.585 验得 35）
- gen_frames <= mat_frames；每张 sheet cells <= max_cells
- sum(sheet cells) >= gen_frames；sheet_px 单边 <= 2048
- 长宽比 > 2 → layout == "strip"
- 证伪：注入 MAX_MAT_FRAMES=16 封顶 → 必须 FAIL

## 依赖 / 被依赖

- 依赖: `_common`、`framerate`
- 被依赖: `solver`、`build_video`、`pipeline/sheet_pack`

## 改前必读

`IMPROVE_sheet_plan.md` ← 业界依据、16 帧封顶历史 bug、格数上限来源
