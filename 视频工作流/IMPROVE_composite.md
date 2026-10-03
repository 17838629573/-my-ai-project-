# IMPROVE_composite — 合成层详解

契约 `contracts/composite.md` 只留铁律与接口；本文存放**业界依据、历史 bug**。

## 业界依据（禁自己造轮子）

| 结论 | 来源 |
|---|---|
| **Porter-Duff "Over"**：`C_out = C_s·α_s + C_d·(1-α_s)`，预乘 alpha、线性空间；**alpha 混合非交换**，多层必须从远到近 (back-to-front) 依次合成 | Porter & Duff, SIGGRAPH 1984 |
| **AI 资产禁色键**：扩散模型把背景色当上下文扩散进边缘，产生不规律溢色，固定阈值抠不净 | AI 抠图失效复盘 / 绿幕溢色分析 |
| **进阶抠像**：RVM / Background Matting v2 / MODNet —— 无绿幕、循环记忆跨帧平滑、发丝级 alpha | RVM, WACV 2022（字节） |
| **背景可控时最优**：Clean Plate + **Difference Matting**，保留接触阴影/烟雾/半透明 | Aximetry 工业级合成管线 |
| **位移意图**：Root Motion（横穿）vs In-Place（跟拍+背景滚动），二者不可混用 | Unity Root Motion 官方定义 |
| **接触阴影**由 alpha 腐蚀/位移生成，避免前景"浮空" | Unity/UE Contact Shadow 实践 |

## 历史 bug（真实踩过）

1. **在 sRGB 编码值上直接做加权平均**
   半黑半白 50% 光，正确 sRGB 值应是 **188**，旧做法给 **128**，差 60 级。
   半透明边缘发灰发暗的根源。修正：解码→预乘→Over→回编码。

2. **缩放一律走线性光**
   ImageMagick 官方：**放大不要走线性光**，负瓣 halo 会更严重；只有缩小需要。
   修正：分方向处理。

3. **编码器用 mp4v**（MPEG-4 Part2 古董）
   改为 avc1（H.264/libx264，CRF 18-28），失败回退。

4. **`chroma_key` 用四个单像素取背景色**
   实测生成图是玫红 (219,49,128) 而非指定品红，四像素采样取错。
   修正：从帧边采样众数 `build_plate`。

## 待办

- RVM / MODNet 未接入（当前走 difference matting + 色键兜底）
