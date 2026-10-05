# FILL perspective   缺 1 槽位   （模型只填 pick，勿写散文）

## 收益 (achieve)
已填: 无
  [IMPROVE:IMPROVE_perspective.md:L5] 用户指出：路径不能硬编码两点坐标（如 `(474,482)→(23,732)`）。
  [IMPROVE:IMPROVE_perspective.md:L17] 已知一个真实高度 y_c（相机高）与地平线 y_0，可反推物体真实高：
  [IMPROVE:IMPROVE_perspective.md:L23] **关键用途：变形后即可由已知参照物反解相机高度**（不需手填）：
  [IMPROVE:IMPROVE_perspective.md:L76] 不能凭直觉摆几条线再猜结果。**
  [IMPROVE:IMPROVE_perspective.md:L82] - `_px.py` 的画布坐标转换可保留（那是裁剪/画布层面，与此正交）
  pick: NEW: 由已知参照物反解相机高度，避免手填坐标；路径按深度自动生成远小近大
