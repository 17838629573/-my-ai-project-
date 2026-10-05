# FILL camera   缺 4 槽位   （模型只填 pick，勿写散文）

## 处境 (context)
已填: 无
  [IMPROVE:IMPROVE_camera.md:L4] 旧链路：`生背景图 → 从图反推 h_cam → 算落点`
  [IMPROVE:IMPROVE_camera.md:L45] - `v_h` 目前由 `solve` 输出；素材清空后重出背景图时，须用
  pick: IMPROVE_camera.md:4

## 否决方案 (neglected)
已填: 无
  [IMPROVE:IMPROVE_camera.md:L4] 旧链路：`生背景图 → 从图反推 h_cam → 算落点`
  [IMPROVE:IMPROVE_camera.md:L35] **地面 z=25 在画面外（y=1093 > 960）—— 这就是旧版树悬空/消失的真因。**
  [IMPROVE:IMPROVE_camera.md:L39] 1. 证伪构造错：以为"极远树 z=5 永不可见"，但退远能救任何有限深度物体。
  pick: IMPROVE_camera.md:4

## 收益 (achieve)
已填: 无
  [IMPROVE:IMPROVE_camera.md:L5] 反推出的 h_cam=3.366m 只能描述**一个平面**，装不下"墙顶 12m 马道 + 地面"，
  [IMPROVE:IMPROVE_camera.md:L24] 僧人 底v=549 顶v=507  可见
  [IMPROVE:IMPROVE_camera.md:L25] 柳树 底v=890 顶v=717  可见
  [IMPROVE:IMPROVE_camera.md:L30] ## 关键新发现：可放置深度区间
  [IMPROVE:IMPROVE_camera.md:L32] 地面   可放置 z ∈ [33.3, 400] m
  pick: IMPROVE_camera.md:30

## 代价 (accepting)
已填: 无
  [IMPROVE:IMPROVE_camera.md:L39] 1. 证伪构造错：以为"极远树 z=5 永不可见"，但退远能救任何有限深度物体。
  pick: IMPROVE_camera.md:39
