# IMPROVE_driver —— 改 driver.py 前必读

## 本模块解决的问题
之前对树、马车也生成骨架/序列帧 —— 因为代码没有"先判族、再选驱动器"这一层，
看什么都当 biped/chain 处理。

## 业界依据（本轮搜证）
- 3D 管线：armature 驱动网格顶点（skinning），**骨架自身永不渲染**
- 2D/AI 管线：ControlNet OpenPose 中骨架是 **conditioning（控制条件）**，
  不是被临摹的图像；"骨架决定姿态，提示词决定身份/服装/风格"
- SpeedTree 风：Global → Branch → Leaf 三级顶点位移，**植被无骨骼**
- 马车：车体刚体 + 车轮自转，与拉车动物靠 attachment point 挂接
- 定位：sprite 的 **registration point / pivot** 决定放置与旋转中心

## 踩过的坑（改前必看）
1. **骨架图当参考图喂入图生图 → 骨架被画进画面**
   根因：把 conditioning 当成了 reference image。
   本工具未确认支持 control map，故一律按不支持处理：姿态走结构性文本。
2. **证伪项连错两次**
   第一次：只校验"族是否登记"，假 classify 补 biped 即绕过。
   第二次：补了①还不够，必须①族字段存在 + ②族已登记 双层。
   → 教训：单点抛错不算防御，改完必须跑证伪看它会不会真的报错。
3. **自检自指误报（第 5 次遇到同类）**
   扫描"逻辑区禁物体名"会扫到自己的 HARDCODE_BAN 列表。
   解法：只扫 `# BEGIN EXAMPLES` 之前的源码。

## 待办（程序做不到，必须提醒 AI）
- [ ] 确认生图工具是否支持 control map；不支持则永久走文本姿态
- [ ] quadruped 的 pose 四足扩展尚未实现（族已登记，驱动器缺失）
- [ ] rigid 的刚体位移+轮转尚未实现
- [ ] px_per_m 无深度维度，远近 LOD 未做
