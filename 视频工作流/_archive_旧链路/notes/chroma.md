# chroma 改动史（契约块不放这些，避免污染每次读契约的上下文）

## 双色背景（实测 5 素材）

xz_cu / xz_hands / xz_mcu 是双色背景：上部紫蓝、下部浅灰 `(213,224,223)`。
`chroma_key` 单色采样 → bbox 返回全图 1151x2047，裁不掉。
`flood_key` 对全部 5 个有效。→ `load_character` 默认 `method="flood"`。

实测对比（bbox 宽高比）：

| 素材 | chroma_key | flood_key |
|---|---|---|
| xz_cu | 1151x2047(全图) | 445x1443 |
| xz_hands | 1151x2047(全图) | 1001x1339 |
| xz_mcu | 1151x2047(全图) | 1080x1849 |
| xz_cowboy | 598x1087 | 600x1089 |
| xz_kneel | 1045x1621 | 1045x1622 |

## shrink 默认值失效（实测）

初版 `shrink=1.0`，而代码里判断是 `if shrink > 1.0` → **永不触发 = 完全不收缩**。
改 `shrink=2`（业界 1px contract）后，bbox 从占全图 80%x93% 降到 52%x53%。

feather 初版 1.2 偏大 → 改 0.5（业界 0.5px feather）。
`clean_mask` / `flood_key` 的 feather 同步改 0.5。

## alpha 量纲（易错）

`flood_key` 返回的 alpha 是 **0-1 float**，不是 0-255。
阈值必须用 0.5；曾误用 `>128` 导致全部素材前景占比报 0%。
