#### 契约块（改代码前只读对应块 + 该文件本身）
红=行业本体(改须批准) 黄=业务(改须回归) 绿=工具(可重建)
**本文件只放"现在该怎么做"。改动史一律放 notes/<模块>.md，不放这里。**

## L0
**chroma**·绿 抠像/贴合｜调:character_sheet,film_assemble｜依:无｜史:notes/chroma.md
接口: chroma_key(bgr), flood_key(bgr,tol=10)*多色背景首选, clean_mask, contact_shadow, overlay, load_character, trim_alpha
参数: shrink=2(1px contract)｜feather=0.5｜load_character 默认 method="flood"
注意: flood_key 的 alpha 是 0-1 float，阈值用 0.5 不是 128

**subtitle**·绿 字幕｜调:systems,film_assemble｜依:无｜史:notes/subtitle.md
接口: draw_subtitle(bgr,text,alpha,margin_bottom=0.25,max_chars=14,stroke=4), subtitle_alpha(i,n,fade_frames=6), check_timing(seconds,chars), get_font(size)
规范: 字号=画面高5%±1%(GY/T357-2021)｜白字+黑边宽4不透明｜底距0.25｜每行≤14字｜CPS17-20
避头尾: 行首禁=。，！？、；：）」』】》….,!?;:)]}｜行尾禁=（「『【《([{

**photo_rules**·红 景别/角度/运动三轴+人体比例+关节禁忌+剪辑梯度｜调:film_assemble,render_v4｜依:无｜史:notes/photo_rules.md
接口: BODY, JOINTS, SHOT_TYPES(EWS/WS/FS/MFS/MS/MCU/CU/ECU), ANGLES, MOVEMENTS, body_pixels(shot,H)->(px,in_frame), ground_y, validate_shot, validate_sequence
headroom: EWS15-22｜WS15-20｜FS10-15｜MFS/MS10-12｜MCU8-12｜CU5-8｜ECU0-5
守恒: headroom+body_frac+footroom=1.0，footroom由前两者派生，禁止三者各自手填

**motion_lib**·红 运动原子函数集(短名≤4字母)｜调:systems｜依:无
接口: mj,fs,ip,w_ip,cadence_spm,L_EFF,slip,lipm,cp,mos,verlet,aero,spr,dmp,pnoise,add,walk_hip,HIP_FS
分族(选错会崩): 周期→fs/ip/slip｜点到点→mj｜被动物理→verlet/aero/pnoise
叠加用 add(加法非对冲)；动量层才是对冲(人体主动把净角动量压到0)

**skeleton_runtime**·黄 Spine解析+FK+slot排序防穿模｜调:systems｜依:无｜史:notes/skeleton_runtime.md
接口: mat_mul/mat_local/mat_apply/mat_inverse, Skeleton(data,img_loader).world_matrix/.draw/.pose/.unknown, apply_animation, check_driven
槽位序: legL→legR→armL→armR→torso→head（索引大者在上）
骨骼: root/hip/torso/head/legL/legR/armL/armR（8根；无膝踝，CoM-driven IK暂不可行）
必跑: 改骨架后 check_driven(sk, 驱动名列表)，返回空才通过

## L1
**character_sheet**·黄 角色图集+native/scaled两路径｜调:film_assemble｜依:chroma,photo_rules｜史:notes/character_sheet.md
接口: SHEET, CHAR_DIR, SUPPORTING, EXPRESSION, PROP, WALK_8FRAME, missing_assets, load_native, load_scaled, resolve, measure_native_composition, check_naming, tier_target_h, loop_closed
约束: native 禁止裁剪(会摧毁烘焙的头顶留白)
命名: char_anim_NN.png 全小写+下划线+帧号两位补零（不补零会静默重排动画）
分级: 占屏0.6+→1400｜0.4→1000｜0.2→700｜<0.2→420（按占屏非按重要性）

## L2
**systems**·黄 可启停系统(骨架/动画/物理/合成/字幕)｜调:render_v4｜依:skeleton_runtime,subtitle｜史:notes/systems.md
接口: Ctx(W,H), init_skeleton, update_animation, init_physics, update_physics, update_composite, update_subtitle
走路: REAL_HEIGHT_M, STRIDE_RATIO, STEP_LENGTH_M, CADENCE_SPM, WALK_PERIOD, WALK_FRAMES, PLAYRATE_CLAMP, step_px, scroll_per_frame, matched_playrate, WALK_POSE_TABLE, _walk_pose, com_vertical_amp, COM_V_RATIO, HEAD_STEADY
常量: 4姿态×2镜像｜循环1.0s(12帧/步@24fps)｜步幅身高×0.45=0.765m｜步频120/分｜钳制±15%
起伏: COM_V_RATIO=0.012(峰峰4.1cm，文献2-5cm)｜HEAD_STEADY=0.35
插值: 腿部必须线性，加缓动会让脚"犹豫"

**loop_engine**·黄 按需调度+tag依赖闭包+拓扑序+耗时统计｜调:render_v4｜依:无｜史:notes/loop_engine.md
接口: System(name,init_fn,update_fn,deps).enable/disable, LoopEngine.register/bind_tag/set_always/resolve/configure/run/order/report/reset_stats
约束: composite/subtitle 必须 set_always，否则 canvas 为 None
约束: init 状态绑定 ctx 身份(id)，换 ctx 必须重新 init

## L3
**film_assemble**·黄 镜头装配(3字段→选资产/定比例/算落点)｜调:render_v4｜依:character_sheet,photo_rules,chroma,subtitle｜史:notes/film_assemble.md
接口: META, resolve_shot(st,H,W,look)->{char_px,foot_y,in_frame,char_w,x}, plan_resolve, _pick_asset, render_one, prep_native, prep_scaled, overlay_full, scroll_bg, sub_shift, NOSEROOM, nose_offset_x
构图: NOSEROOM EWS0.0｜WS0.10｜FS0.15｜MFS0.25｜MS/MCU0.30｜CU0.17｜ECU0.10
注: 半身景别 char_w 可达画面宽2-7倍，x为负属正常，可见宽度恒>0

**render_v4**·黄 主入口 全片编排｜调:用户｜依:film_assemble,loop_engine,systems,photo_rules
接口: make_parts, SHOTS, build_engine, main
SHOTS字段: name/bg/shot_type/angle/movement/look/caption/seconds/has_walk/has_wind
**禁止手填 char_px / bg_speed** —— 一律由 photo_rules 反算

## 资产A
bg·绿 8张: gate,hall,office,yamen,river,desert,oasis,yiwu
char·黄 可用: kneel40.6 medium50.4 stand34.3 walk_a34.5
      弱: walk_b21.3 mcu24.2 hands23.6 cowboy17.2
      **禁引用: cu2.6(broken)**
待补: 配角4、表情6、道具5、走路8帧

## 待办（一次只做一个文件）
| Stage | 文件 | 状态 |
|---|---|---|
| 2 | enforce.py | ✓ |
| 3 | chroma/photo_rules/character_sheet | ✓ |
| 4 | systems.py | ✓ |
| 5 | render_v4.py | ✓（三轴接入+骨架落点） |
| 6 | 抽帧检测 | 待 |
| 7 | 补18项资产 | 待 |
