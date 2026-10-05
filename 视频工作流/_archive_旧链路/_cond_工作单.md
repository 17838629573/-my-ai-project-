# cond 工作单 —— 只填 pick，不要改原文

格式: `id | 维度 = 值`（值必须是枚举成员或 `任意`）
多值用逗号；不填 = 我来定。


## matte

### M_a chroma.chroma_key
  阶段: -
  plate: 无plate(命中1:未控制背景)
    pick: 
  edge: 简单硬边(命中4:纯色/绿幕)
    pick: 
  type: （无关键词命中，需人工 NEW）
    pick: 

### M_e chroma.flood_key
  阶段: -
  plate: 无plate(命中2:背景非单一色/四角色值不一致)
    pick: 
  edge: （无关键词命中，需人工 NEW）
    pick: 
  type: 人物(命中1:主体)
    pick: 

### M_j _matting.grabcut_alpha
  阶段: -
  plate: （无关键词命中，需人工 NEW）
    pick: 
  edge: 复杂边缘(命中3:混合像素/模糊)
    pick: 
  type: 人物(命中1:前景)
    pick: 

### M_i _matting.auto_trimap
  阶段: -
  plate: （无关键词命中，需人工 NEW）
    pick: 
  edge: （无关键词命中，需人工 NEW）
    pick: 
  type: 人物(命中2:主体/前景)
    pick: 

### M_k _matting.feather_alpha
  阶段: -
  plate: （无关键词命中，需人工 NEW）
    pick: 
  edge: 复杂边缘(命中3:混合像素/羽化)
    pick: 
  type: （无关键词命中，需人工 NEW）
    pick: 

### M_f composite.build_plate
  阶段: -
  plate: 有真实plate(命中4:plate/背景单独)
    pick: 
  edge: （无关键词命中，需人工 NEW）
    pick: 
  type: 人物(命中1:主体)
    pick: 

### M_g composite.difference_matte
  阶段: -
  plate: 有真实plate(命中2:plate/锁定机位)
    pick: 
  edge: （无关键词命中，需人工 NEW）
    pick: 
  type: 人物(命中1:主体)
    pick: 

### M_b chroma.trim_alpha
  阶段: -
  plate: （无关键词命中，需人工 NEW）
    pick: 
  edge: 复杂边缘(命中1:透明)
    pick: 
  type: （无关键词命中，需人工 NEW）
    pick: 

### M_c chroma.clean_mask
  阶段: -
  plate: （无关键词命中，需人工 NEW）
    pick: 
  edge: 复杂边缘(命中3:半透明/羽化)
    pick: 
  type: （无关键词命中，需人工 NEW）
    pick: 

### M_o physics.alpha_blend / composite.porter_duff_over
  阶段: -
  plate: （无关键词命中，需人工 NEW）
    pick: 
  edge: 复杂边缘(命中1:模糊)
    pick: 
  type: （无关键词命中，需人工 NEW）
    pick: 

### M_d contact_shadow（4 份同名，语义分三类）
  阶段: -
  plate: （无关键词命中，需人工 NEW）
    pick: 
  edge: （无关键词命中，需人工 NEW）
    pick: 
  type: 人物(命中4:人物/主体)
    pick: 

## motion

### T_a wind_response.wind_response
  阶段: -
  periodic: 周期(命中5:双频/低频)
    pick: 周期
  kind: 程序化可算(命中5:双频/风)
    pick: 程序化可算
  stochastic: （无关键词命中，需人工 NEW）
    pick: 确定性

### T_b build_phase_time.flag_period_s
  阶段: -
  periodic: 周期(命中2:周期/频率)
    pick: 周期
  kind: 程序化可算(命中5:公式/风)
    pick: 程序化可算
  stochastic: 确定性(命中3:公式/反推)
    pick: 确定性

### T_c build_util.sway_image
  阶段: -
  periodic: （无关键词命中，需人工 NEW）
    pick: 任意
  kind: 程序化可算(命中3:逐行/横向位移)
    pick: 程序化可算
  stochastic: （无关键词命中，需人工 NEW）
    pick: 确定性

### T_d build_util.apply_garment_wind
  阶段: -
  periodic: （无关键词命中，需人工 NEW）
    pick: 任意
  kind: 程序化可算(命中3:风/剪切), 骨架可驱动(命中1:人物)
    pick: 程序化可算
  stochastic: （无关键词命中，需人工 NEW）
    pick: 任意

### T_e character_sheet.loop_closed
  阶段: -
  periodic: 周期(命中2:循环/首尾), 一次性(命中2:一次性/death)
    pick: 周期
  kind: （无关键词命中，需人工 NEW）
    pick: 任意
  stochastic: （无关键词命中，需人工 NEW）
    pick: 任意

### T_f framerate.frames_for_period
  阶段: -
  periodic: 周期(命中2:周期/帧数)
    pick: 周期
  kind: （无关键词命中，需人工 NEW）
    pick: 任意
  stochastic: 确定性(命中1:反推)
    pick: 任意

### T_g systems._walk_pose
  阶段: -
  periodic: 周期(命中3:周期/步距)
    pick: 周期
  kind: 骨架可驱动(命中4:姿态/插值)
    pick: 骨架可驱动
  stochastic: 确定性(命中2:锁相/步距)
    pick: 确定性

### T_h systems.update_animation
  阶段: -
  periodic: 周期(命中3:周期/循环)
    pick: 周期
  kind: 骨架可驱动(命中4:姿态/落脚)
    pick: 骨架可驱动
  stochastic: （无关键词命中，需人工 NEW）
    pick: 任意

### T_i skeleton_runtime.apply_animation + _interp
  阶段: -
  periodic: 一次性(命中2:序列帧/手绘), 周期(命中1:逐帧)
    pick: 任意
  kind: 骨架可驱动(命中3:骨骼/插值), 需生图(命中2:序列帧/手绘)
    pick: 骨架可驱动
  stochastic: 确定性(命中1:帧率)
    pick: 任意

### T_j pose.blend_poses
  阶段: -
  periodic: （无关键词命中，需人工 NEW）
    pick: 任意
  kind: （无关键词命中，需人工 NEW）
    pick: 骨架可驱动
  stochastic: （无关键词命中，需人工 NEW）
    pick: 任意

### T_k rain_layer.rain_drops + draw_rain
  阶段: -
  periodic: （无关键词命中，需人工 NEW）
    pick: 任意
  kind: 程序化可算(命中3:公式/终端速度)
    pick: 程序化可算
  stochastic: 随机非刚性(命中4:滴谱/抽样), 确定性(命中2:公式/终端速度)
    pick: 随机非刚性

### T_l wind_sway.phase_of + sway_offset + wind_sway
  阶段: -
  periodic: 周期(命中3:相位/频率)
    pick: 周期
  kind: 程序化可算(命中2:摆动/位移)
    pick: 程序化可算
  stochastic: 随机非刚性(命中2:各层频率/多层)
    pick: 确定性

### T_m 骨架_行走.solve_frame
  阶段: -
  periodic: （无关键词命中，需人工 NEW）
    pick: 任意
  kind: 骨架可驱动(命中2:身体坐标/人物)
    pick: 骨架可驱动
  stochastic: （无关键词命中，需人工 NEW）
    pick: 任意

### T_n systems.scroll_per_frame
  阶段: -
  periodic: 周期(命中2:步频/步距)
    pick: 周期
  kind: 程序化可算(命中1:位移)
    pick: 骨架可驱动
  stochastic: 确定性(命中2:帧率/步距)
    pick: 任意

### T_o cloth_aero.wind_force
  阶段: -
  periodic: （无关键词命中，需人工 NEW）
    pick: 任意
  kind: 程序化可算(命中3:气动/面元)
    pick: 程序化可算
  stochastic: 确定性(命中1:量纲)
    pick: 确定性

### T_p water.rain_intensity_class + rain_inclination + rain_velocity_vector
  阶段: -
  periodic: （无关键词命中，需人工 NEW）
    pick: 任意
  kind: 程序化可算(命中3:风/终端速度)
    pick: 程序化可算
  stochastic: 确定性(命中2:终端速度/风速), 随机非刚性(命中1:雨)
    pick: 随机非刚性

### T_q build_phase_gen._cloth_phys_points
  阶段: -
  periodic: 周期(命中3:周期/逐帧)
    pick: 周期
  kind: 程序化可算(命中3:物理/数值层)
    pick: 程序化可算
  stochastic: 确定性(命中1:数值层)
    pick: 确定性

### T_r systems.init_skeleton
  阶段: -
  periodic: （无关键词命中，需人工 NEW）
    pick: 任意
  kind: 骨架可驱动(命中2:骨架/对象池)
    pick: 骨架可驱动
  stochastic: （无关键词命中，需人工 NEW）
    pick: 任意