# 契约：风响应统一数值层 wind_response.py

## 依赖/被依赖
- 依赖: `_common`(beaufort_scale, flag_motion)
- 被依赖: `wind_sway`, `build_video`, `solver_run`, `driver`

## 改前必读
- `IMPROVE_wind_response.md`（本轮实证：树频率写死、衣摆无风驱动）

## 业界依据（真实联网搜索）
1. arXiv 2609.17810《Wind on Trees》：树木摆动 = 受迫阻尼谐振子，
   固有频率遵循悬臂梁一阶模态标度 ω ∝ (r/L²)·sqrt(E/ρ)；
   阻尼比 Jackson 实测 8.6±2.2%（夏季有叶树）。
   → 树的**基频由几何尺寸定**，风速主要改变**幅度**，强风激发高阶模态使频率略升。
2. SpeedTree 官方文档（docs8.speedtree.com/modeler windunity）：
   Global Motion 频率 < Branch Motion < Leaf Motion；
   各层用 profile curve 控制"运动如何随风强度从低到高变化"。
   → **频率与幅度均随风强度调制**，非恒定常量。
3. Manchester 大学实测《On the Aerodynamic Drag of Streamers and Flags》：
   flutter 主频 5-30Hz；AR=10→44Hz, AR=20→15Hz, AR=30→13Hz；
   Taneda: AR≈1, u=15m/s → ~50Hz。
   → **长宽比 AR 越大频率越低**；两种拍打态：低幅-高频 / 高幅-低频。
4. Strouhal 校准：f = St·u/L，旗帜 St≈0.2 时
   L=2.5m,u=5.5 → 0.44Hz，与 flag_motion 表 3 级风 0.43Hz 吻合。
   （旧公式 c=0.33 相当于 St=3.0，快 13 倍，即"三级风急速抖动"根因）

## 铁律
- 铁律91：所有受风物体（旗/衣摆/发丝/树叶/草）一律走 wind_response，
  禁止在调用处写死频率或 amp_scale 魔法数。
- 铁律92：频率随尺寸 L 下降、随风速 u 上升（弱调制）；
  幅度随 u² 增长（气动力正比动压）但有饱和上限。
- 铁律93：幅度数值偏向保守，A/L 上限按族标定，禁止超过该族上限。
