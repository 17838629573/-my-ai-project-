# FILL composite   缺 4 槽位   （模型只填 pick，勿写散文）

## 处境 (context)
已填: 无
  [IMPROVE:IMPROVE_composite.md:L10] | **AI 资产禁色键**：扩散模型把背景色当上下文扩散进边缘，产生不规律溢色，固定阈值抠不净 | AI 抠图失效复盘 / 绿幕溢色分析 |
  [IMPROVE:IMPROVE_composite.md:L12] | **背景可控时最优**：Clean Plate + **Difference Matting**，保留接触阴影/烟雾/半透明 | Aximetry 工业级合成管线 |
  [IMPROVE:IMPROVE_composite.md:L13] | **位移意图**：Root Motion（横穿）vs In-Place（跟拍+背景滚动），二者不可混用 | Unity Root Motion 官方定义 |
  [IMPROVE:IMPROVE_composite.md:L29] 4. **`chroma_key` 用四个单像素取背景色**
  [composite.py:L127] 素材已清空时降级为合成背景：自检只验算法，不验素材是否存在
  pick: IMPROVE_composite.md:13

## 问题 (facing)
已填: 无
  [IMPROVE:IMPROVE_composite.md:L3] 契约 `contracts/composite.md` 只留铁律与接口；本文存放**业界依据、历史 bug**。
  [IMPROVE:IMPROVE_composite.md:L10] | **AI 资产禁色键**：扩散模型把背景色当上下文扩散进边缘，产生不规律溢色，固定阈值抠不净 | AI 抠图失效复盘 / 绿幕溢色分析 |
  [IMPROVE:IMPROVE_composite.md:L13] | **位移意图**：Root Motion（横穿）vs In-Place（跟拍+背景滚动），二者不可混用 | Unity Root Motion 官方定义 |
  [IMPROVE:IMPROVE_composite.md:L16] ## 历史 bug（真实踩过）
  [IMPROVE:IMPROVE_composite.md:L19] 半黑半白 50% 光，正确 sRGB 值应是 **188**，旧做法给 **128**，差 60 级。
  pick: IMPROVE_composite.md:10

## 收益 (achieve)
已填: 无
  [IMPROVE:IMPROVE_composite.md:L12] | **背景可控时最优**：Clean Plate + **Difference Matting**，保留接触阴影/烟雾/半透明 | Aximetry 工业级合成管线 |
  [IMPROVE:IMPROVE_composite.md:L13] | **位移意图**：Root Motion（横穿）vs In-Place（跟拍+背景滚动），二者不可混用 | Unity Root Motion 官方定义 |
  pick: IMPROVE_composite.md:12

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_composite.md:L19] 半黑半白 50% 光，正确 sRGB 值应是 **188**，旧做法给 **128**，差 60 级。
  pick: IMPROVE_composite.md:19
