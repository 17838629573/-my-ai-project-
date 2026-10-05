# FILL groundline   缺 4 槽位   （模型只填 pick，勿写散文）

## 问题 (facing)
已填: 无
  [IMPROVE:IMPROVE_groundline.md:L6] 本文件写**改的时候要躲的坑 + 没做完的事**。
  [IMPROVE:IMPROVE_groundline.md:L8] ## 真坑（踩过的）
  [IMPROVE:IMPROVE_groundline.md:L10] ### 坑1：纯边缘强度会把砖缝当成地线
  [IMPROVE:IMPROVE_groundline.md:L17] ### 坑2：相邻行会同时入选候选
  [IMPROVE:IMPROVE_groundline.md:L23] ### 坑3：背景图 resize 前后 y 不一致
  pick: IMPROVE_groundline.md:10

## 决定 (decided)
已填: 无
  [IMPROVE:IMPROVE_groundline.md:L15] **解**：候选评分必须乘"双侧窄带颜色对比度"。已在 `detect()` 中实现。
  [IMPROVE:IMPROVE_groundline.md:L25] 背景原图 2048×1152，画布 540×960，**探测必须在画布尺寸上做**，
  [IMPROVE:IMPROVE_groundline.md:L32] - [ ] **透视地面**：目前只支持水平地面线。斜地面（城墙走道带透视）应返回 `y(x)` 直线而非常数
  [IMPROVE:IMPROVE_groundline.md:L33] - [ ] **多候选交 AI 复核**：当前自动取最高分，未实现"置信度低时回问 AI"
  pick: IMPROVE_groundline.md:15

## 收益 (achieve)
已填: 无
  [IMPROVE:IMPROVE_groundline.md:L26] 否则 baseline_y 是原图坐标系，落位会错 2 倍以上。
  [groundline.py:L113] 1 基本功能：上浅下深分界在 y=480
  pick: IMPROVE_groundline.md:26

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_groundline.md:L12] 城墙背景有大量砖缝，Sobel 强度很高，但**两侧颜色几乎一致**。
  pick: IMPROVE_groundline.md:32
