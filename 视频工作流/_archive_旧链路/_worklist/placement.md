# FILL placement   缺 3 槽位   （模型只填 pick，勿写散文）

## 决定 (decided)
已填: 无
  [IMPROVE:IMPROVE_placement.md:L6] 此前 `build_video.py` 直接 `baseline_y - rgb.shape[0]`，等价于**用图像顶部当锚**，
  [IMPROVE:IMPROVE_placement.md:L13] 上一轮为修「跨帧漂移 269px」，用了**逐帧居中对齐**。
  [IMPROVE:IMPROVE_placement.md:L21] 而固定语义点做法是 0.00e+00。
  [IMPROVE:IMPROVE_placement.md:L23] **修法**：固定源画布尺寸 + 每帧复用同一 regpoint + 记录 trim offset。
  [IMPROVE:IMPROVE_placement.md:L29] 所以 `ground_contact` 用画布底边中心，不做图像测量。
  pick: IMPROVE_placement.md:23

## 否决方案 (neglected)
已填: 无
  [IMPROVE:IMPROVE_placement.md:L14] 那是 auto-centering。framesprite.com 原话：
  [IMPROVE:IMPROVE_placement.md:L27] gamedev.stackexchange 原话：跑步序列有帧双脚离地；角色也可能与地面相交。
  [IMPROVE:IMPROVE_placement.md:L41] - [ ] `groundline.detect()` 已存在但 `build_video` 零调用 —— baseline 仍手填
  [IMPROVE:IMPROVE_placement.md:L62] | gamedev.stackexchange | 逻辑原点 = 精灵触地处 + 水平中心，对所有精灵恒定；不必是最低像素，也不必是实际中心（长矛骑士的水平中心可偏左） |
  [IMPROVE:IMPROVE_placement.md:L63] | 同上 | 视觉原点应与碰撞/事件坐标分开记录 |
  pick: IMPROVE_placement.md:13

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_placement.md:L33] 第 7b 项初版写成 `ck("对照:auto-centering有定义差", True, ...)` ——
  [IMPROVE:IMPROVE_placement.md:L41] - [ ] `groundline.detect()` 已存在但 `build_video` 零调用 —— baseline 仍手填
  [placement.py:L174] 8 base 与 ground_contact 语义不同但同源公式
  pick: IMPROVE_placement.md:41
