# IMPROVE_sheet_cell.md —— 改 sheet_cell 契约前必读

本文件是 `contracts/sheet_cell.md` 的**详解层**：业界搜证原文 + 踩坑。
契约只留阈值表与接口，依据全部在此。

---

## 一、本轮搜证（业界依据，逐条原文要点）

| 来源 | 权威 | 要点 |
|---|---|---|
| lobehub `agent-sprite-forge` generate2dsprite | 中 | 明列四条硬要求：exact sheet shape / solid magenta background / **frame containment** / same scale across frames |
| SummerEngine STRICT atlas 提示词 | 较低（可复现实产提示词） | **每个精灵必须完整留在自己格内**，不得溢到上下行、不得渗进邻列；**格顶留净边距（头不碰上边）**；放不下就把主体缩小；**PLANTED FRAMING：各格身体落在同一足迹，绝不整体平移滑动** |
| AutoSprite《How to make a sprite sheet》 | 中 | 一格尺寸按**最大姿态**定，避免挥剑被裁；格间留 1–2px padding，否则纹理过滤会采到邻格产生接缝 |
| Seele AI sprite 指南 | 较高 | "Lock character height at **90% of frame height** across all frames"；帧大小不一致会导致 jitter |
| 元域费曼《16格精灵图》 | 极低（自媒体，与多条互证） | **先做 8 格 4×2 起步 → 检查一致性（脸/衣服/配色）→ 再升 16 格 4×4**；"第7格开始人物就开始变异" |
| AutoSprite FAQ | 中 | "Six to twelve frames covers most 2D loops"；更多帧=更平滑但纹理更大 |

---

## 二、关于 "60–70% 安全区" 的诚实说明

我前几轮口头说的「主体占格 60–70%」**未在本轮搜证中直接命中**。
命中的是可量化更强的三条：

- **containment**（完整在格内、留边距）
- **same scale across frames**（各帧同尺度）
- **planted framing**（各帧同一足迹，不整体漂移）

百分比各源不一（有说 90% 锁高、有说留净边距不触边）。
因此本契约**不硬编码单一百分比**，改为 `CONTAINMENT` 参数字典，
上/下限都由 AI 按物体声明，代码只做比较（铁律32）。

**这条要记住**：未命中搜证就别装作有依据，宁可用参数字典 + AI 声明。

---

## 三、为什么探针必须两步

业界实测"第7格开始人物就开始变异"。
若直接出 N=35 格，变异发生在第 30 格才发现，整张图集报废；
探针 8 格能在最便宜的时候暴露问题。

`n_probe = min(8, N)` —— 业界原话："8 格能解决的事不要上 16 格"。

---

## 四、历史踩坑

1. **banner_f33 前景占比 0.6% 却放行** —— 当时只校验了上界没校验下界，
   于是补了 `min_fill = 0.25`。凡"容纳性"校验必须**双向**（太大/太小都抓）。
2. **质心校验误判摆动件** —— 幡旗质心本来就该动，一刀切校验等于把正确动画判违规。
   故引入 `centroid_policy = planted | free`，由 AI 声明（语义判断，不是算术）。
3. **格间 padding 缺失导致接缝** —— 纹理过滤会采到邻格。留 1–2px。

---

## 五、与既有契约的关系

- `sheet_split.md`（铁律44 网格定序 + 连通域定界）：本契约是其**上游**——
  先保证每格内容合格，切分才有意义；切分端 `touches_edge` 与本契约 `margin_px` 互为双保险。
- 铁律41（素材张数代码算）：`n_probe` 同样由代码算，不是 AI 填。
- 铁律40（修订：一物体=一组图集，共用同一身份参考图）：探针也是一张图集，不拆多张。
