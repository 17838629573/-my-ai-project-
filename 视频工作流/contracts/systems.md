# systems ·黄 可启停系统(骨架/动画/物理/合成/字幕)
史:notes/systems.md

接口: Ctx(W,H), init_skeleton, update_animation, init_physics,
      update_physics, update_composite, update_subtitle, **self_check**

**self_check()（铁律26）**
`python3 systems.py` 默认自检，不渲染。检查项：
  1. 【铁律11】本文件不得内联物理公式
     静态扫描源码，禁止出现：0.5*rho*Cd*v**2 / k*V**(2/3) / 手写 G=9.8
     → 一律调用 physics.*
  2. 【铁律14】气动力换算禁魔法系数
     压力(Pa) -> 加速度 必须 经 (面积/质量)，禁止 *1e-3 之类凑数
  3. 走路锁相参数自洽（步幅×步频 -> 速度，落在文献区间）
  4. 各 update_* 在最小 Ctx 上可调用且不抛异常
  5. Verlet 积分能量不发散（无风时速度衰减）
走路: REAL_HEIGHT_M, STRIDE_RATIO, STEP_LENGTH_M, CADENCE_SPM,
      WALK_PERIOD, WALK_FRAMES, PLAYRATE_CLAMP, step_px,
      scroll_per_frame, matched_playrate, WALK_POSE_TABLE, _walk_pose,
      com_vertical_amp, COM_V_RATIO, HEAD_STEADY
常量: 4姿态×2镜像｜循环1.0s(12帧/步@24fps)｜步幅身高×0.45=0.765m
     步频120/分｜钳制±15%
起伏: COM_V_RATIO=0.012(峰峰4.1cm，文献2-5cm)｜HEAD_STEADY=0.35
插值: 腿部必须线性，加缓动会让脚"犹豫"

## 自检实测（已跑通，6 项全 PASS）
```
PASS 无内联物理公式（一律调 physics.*）
PASS 无魔法系数
PASS 步速 1.530 m/s 落在中性步速区间 1.2-1.7
PASS 重心起伏峰峰 4.08 cm 落文献 2-5cm
PASS 冒烟：init_physics + 4 个 update 跑 3 帧无异常
PASS Verlet 能量不发散（残余速度 5.0000 -> 0.0000）
```

## 自检抓出的历史 bug（补自检的实证价值）
1. **气动力魔法系数 1e-3**（铁律14）：`压力(Pa) -> 加速度` 凭空乘 1e-3 凑量纲
   → 改为 `a = press * (A/m) * px_per_m`，质点须带 area_m2/mass_kg
2. **相对速度量纲错**（漏 px/s -> m/s）：气动力大 `px_per_m^2` = **16.5 万倍**
   → Verlet 单帧位移 62799 px，直接 nan
   修后：位移 0.38 px/帧，残余速度 5.0000 -> 0.0000（收敛）
3. init_physics 缺物性即报错（铁律23：真实尺寸由 AI 传入，代码不含常量）
