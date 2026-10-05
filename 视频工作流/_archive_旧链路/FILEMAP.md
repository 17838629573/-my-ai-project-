# FILEMAP（机器生成，勿手改）

用途：不读全量代码即可定位。每行 = 一个文件做什么 + 改它必须同步核对哪些文件。
格式：文件  @层/组  | 用途  | edit: 改前须核对的文件

_actor_audit.py        @OPS/audit    | 审计：从 SHOTS 推导需要哪些 actor、什么动作，代码能否供给 | edit: character_sheet
_audit_dead.py         @OPS/audit    | （内部模块，无公开接口） | edit: （无）
_audit_dup.py          @OPS/audit    | 真实扫描：找出可复用却被重复实现的逻辑。 | edit: （无）
_build32.py            @OPS/demo     | 提供 key_color_of, key_alpha, prep, sh_of | edit: _layer_style
_camera.py             @ATOM/cam      | 镜头意图 → 机位求解（纯函数层，零硬编码） | edit: _camera_selfcheck,_perspective
_camera_selfcheck.py   @ATOM/cam      | _camera 自检（独立模块，避免撑大核心文件） | edit: _camera
_chk_assemble.py       @SOLVE/check    | 检查域3：inventory/assemble/动静划分/anchor/驱动源。 | edit: _chk_base,solver_check,solver_survey
_chk_base.py           @SOLVE/check    | solver 自检公共层：共享 import + _r 断言器。 | edit: _chk_assemble,_chk_chain,_chk_motion,_chk_multi,_chk_pack,_chk_physics,_chk_reuse,_chk_sheet,_chk_survey,_solver_base,_solver_chain,_solver_probe,_solver_reuse,_solver_run,_solver_sheet,anchor,framerate,physics,solver_check,solver_survey
_chk_chain.py          @SOLVE/check    | 检查域2：chain 共振/逐级递推/transient 稳态与包络衰减。 | edit: _chk_base,_solver_chain,solver_check
_chk_motion.py         @SOLVE/check    | 检查域5：run_spec 契约/扬角/振幅比/风向全局一致。 | edit: _chk_base,_solver_base,_solver_chain,_solver_run,physics,solver_check
_chk_multi.py          @SOLVE/check    | 检查域6：多驱动叠加（位移域）/循环闭合。 | edit: _chk_base,_solver_chain,solver_check
_chk_pack.py           @SOLVE/check    | 检查域9：16帧封顶/mat_frames/图集规划/strip。 | edit: _chk_base,_solver_chain,_solver_sheet,solver_check
_chk_physics.py        @SOLVE/check    | 检查域1：缺槽报错/物性换算/帧数/St/固定端/相位均匀性。 | edit: _chk_base,_solver_base,_solver_chain,_solver_sheet,framerate,solver_check
_chk_reuse.py          @SOLVE/check    | 检查域8：复用规划/镜像/layer_plan/overlay/additive_offset。 | edit: _chk_base,_solver_reuse,solver_check
_chk_sheet.py          @SOLVE/check    | 检查域7：容纳性/居中/min_fill/centroid/探针计划。 | edit: _chk_base,_solver_chain,_solver_probe,_solver_sheet,solver_check
_chk_survey.py         @SOLVE/check    | 检查域4：源码禁硬编码物体名/survey 只问不猜/示例覆盖。 | edit: _chk_base,solver_check,solver_survey
_common.py             @ATOM/math     | _common.py —— 跨模块原子复用库（单一定义，全局调用） | edit: _common_selfcheck,build_phase_gen,build_util,physics,physics_rules,puppet,rain_layer,wind_response
_common_selfcheck.py   @ATOM/math     | _common 自检：验证原子库数学正确 + 与旧内联实现等价。 | edit: _common
_despill.py            @ATOM/img      | flood_key —— 漫水填充分割抠图（从 chroma.py 拆出）。 | edit: chroma
_extract2.py           @OPS/tool     | 提供 extract | edit: （无）
_extract_tool.py       @OPS/tool     | 通用函数抽取工具：把源模块中指定函数搬到新模块，原模块留 wrapper 重导出。 | edit: （无）
_family_map.py         @ATOM/rule     | _family_map —— 五类 → 物理形态 唯一映射（铁律88） | edit: _solver_chain
_ground_arc.py         @ATOM/path     | 地面坐标反投影 + 世界弧长参数化。 | edit: build_phase_render,build_video
_import_sweep.py       @OPS/audit    | 全量导入体检：静默 import 所有活跃模块，报告失败。 | edit: （无）
_layer_style.py        @ATOM/img      | 分层合成四要素（铁律101）：投影/环境反光/正片叠底/全局色彩平衡 | edit: _build32,composite
_loopspec.py           @ATOM/frame    | _loopspec.py — 循环资产规范（游戏业界 cycle animation 标准） | edit: （无）
_matting.py            @ATOM/img      | 抠图/matting：从 sprite 单格提取软 alpha 前景。 | edit: composite
_migrate_common.py     @OPS/tool     | 迁移脚手架：把业务模块的内联实现改为调用 _common。 | edit: （无）
_perspective.py        @ATOM/cam      | 透视几何：地平线 / 深度 / 缩放场（纯函数，禁硬编码坐标） | edit: _camera,_surface,_wall_geom
_px.py                 @ATOM/math     | _px.py —— 像素/米 换算的**唯一**口径 | edit: build_phase_asset,build_phase_setup,physics
_solver_base.py        @SOLVE/base     | 基础层：共享常量 + 纯算术。零业务依赖。 | edit: _chk_base,_chk_motion,_chk_physics,_solver_chain,_solver_chain_aux,_solver_geom,_solver_probe,_solver_run,_solver_sheet,solver
_solver_chain.py       @SOLVE/chain    | 物理求解：受迫链响应、regime 判定、周期与帧时长。 | edit: _chk_base,_chk_chain,_chk_motion,_chk_multi,_chk_pack,_chk_physics,_chk_sheet,_family_map,_solver_base,_solver_chain_aux,_solver_geom,_solver_run,anchor,framerate,physics,solver
_solver_chain_aux.py   @SOLVE/base     | chain 求解子函数真身（自拆分前快照恢复） | edit: _solver_base,_solver_chain,framerate
_solver_geom.py        @SOLVE/base     | 骨架几何：把物理点变成归一化中心线。 | edit: _solver_base,_solver_chain,anchor,solver
_solver_probe.py       @SOLVE/chain    | 探针与容纳性校验：先 8 格验一致性再升级（铁律48）。 | edit: _chk_base,_chk_sheet,_solver_base,solver
_solver_reuse.py       @SOLVE/sheet    | 复用规划：镜像/偏移/分层，减生图张数。 | edit: _chk_base,_chk_reuse,_solver_run,solver
_solver_run.py         @SOLVE/sheet    | 编排：读 scene_spec.json 走完整流程，出每物体答案包。 | edit: _chk_base,_chk_motion,_solver_base,_solver_chain,_solver_reuse,_solver_sheet,solver
_solver_sheet.py       @SOLVE/sheet    | 图集规划与绘制：网格选择、布局、骨架图集渲染。 | edit: _chk_base,_chk_pack,_chk_physics,_chk_sheet,_solver_base,_solver_run,solver
_split_plan.py         @OPS/tool     | _split_plan.py —— 超大模块拆分方案（数据驱动） | edit: （无）
_split_sheet.py        @OPS/tool     | 合图切分：网格定序 + 连通域定界（铁律44） | edit: chroma
_split_tool.py         @OPS/tool     | 通用切分工具：把 solver.py 的一个行区间搬到新模块，并在 solver.py 留 facade。 | edit: （无）
_surface.py            @ATOM/cam      | 规则驱动放置（rule-based placement）—— 禁硬编码坐标。 | edit: _perspective,_wall_geom,build_video,param_decl
_wall_geom.py          @ATOM/cam      | wall geometry —— 墙体落点的透视几何（从 _surface.py 拆出）。 | edit: _perspective,_surface
_问卷.py                 @OPS/demo     | AI 填问卷：只做动静划分 + 驱动源判断。物性槽位留空，由代码告诉我要搜什么。 | edit: solver
actors.py              @ATOM/rule     | actors.py —— 可动者登记 + 动作能力白名单 + 硬报错 | edit: environment,physics,render_desert_banner,render_gate_banner,render_v4,render_v4_main
anchor.py              @ATOM/path     | anchor.py —— 物理点锚点层 | edit: _chk_base,_solver_chain,_solver_geom,framerate
build_phase_asset.py   @BUILD/phase    | 出片前置：素材加载与预处理。 | edit: _px,build_util,build_video,chroma
build_phase_gen.py     @BUILD/phase    | 出片前置：生图任务包 + 生图顺序队列。 | edit: _common,build_util,build_video,genqueue,pose,prompt_tpl,run_gen_queue,shot_plan,wind_response
build_phase_render.py  @BUILD/phase    | 出片：逐帧合成循环。 | edit: _ground_arc,build_util,build_video,framerate,path
build_phase_setup.py   @BUILD/phase    | 出片前置：基线探测 + 比例尺 + 路径校验。 | edit: _px,build_util,build_video,cloth_wire,groundline,path,path_align,scale_map,wind_response
build_phase_time.py    @BUILD/phase    | 出片前置：周期与步态时间参数。 | edit: build_video,wind_response
build_util.py          @BUILD/util     | build_video 的自检/检查逻辑（由 _extract_tool.py 从 build_video.py 抽出） | edit: _common,build_phase_asset,build_phase_gen,build_phase_render,build_phase_setup,build_video,chroma,cloth_wire,composite,framerate,genqueue,groundline,path,placement,pose,scale_map,shot_plan,wind_sway
build_video.py         @BUILD/_top     | 合成出片：探测基线 + 路径约束 + 语义落位 + 程序化风摆。 | edit: _ground_arc,_surface,build_phase_asset,build_phase_gen,build_phase_render,build_phase_setup,build_phase_time,build_util,chroma,cloth_wire,composite,framerate,genqueue,groundline,path,placement,scale_map,shot_plan,wind_sway
character_sheet.py     @SHOT/sheet    | 角色图集 + 映射层 | edit: _actor_audit,chroma,enforce_cmds,film_assemble,film_assemble_render,photo_rules,render_desert_banner,render_gate_banner,render_v4_main
chroma.py              @ATOM/img      | 角色层素材处理：色度键抠像 + 去溢色 + 边缘处理 | edit: _despill,_split_sheet,build_phase_asset,build_util,build_video,character_sheet,chroma_selfcheck,composite,enforce_cmds,film_assemble,film_assemble_render
chroma_selfcheck.py    @ATOM/img      | chroma 的自检/检查逻辑（由 _extract_tool.py 从 chroma.py 抽出） | edit: chroma
cloth_aero.py          @ATOM/aero     | cloth_aero — 布料/衣物气动受力（"衣服被风吹飞"这类需求） | edit: cloth_wire,param_decl
cloth_wire.py          @ATOM/aero     | cloth_wire — 布料（衣摆/幡/旗）的气动受力接线层 | edit: build_phase_setup,build_util,build_video,cloth_aero,param_decl,wind_response
composite.py           @ATOM/img      | 提供 build_plate, difference_matte, matte_auto, contact_shadow, porter_duff_over | edit: _layer_style,_matting,build_util,build_video,chroma,systems_view
contact_ik.py          @ATOM/phys     | X_h：末端执行器（手/脚）到物体接触点的 IK 约束。 | edit: （无）
contact_plan.py        @ATOM/phys     | X_g / X_e / X_f 双人与多人接触约束。 | edit: （无）
driver.py              @SOLVE/spec     | driver —— 先判族，再选驱动器（铁律77-80） | edit: genqueue,solver_survey
enforce.py             @GATE/core     | 执行门禁（契约强制性检查） | edit: enforce_cmds,run_batch
enforce_cmds.py        @GATE/core     | enforce 的自检/检查逻辑（由 _extract_tool.py 从 enforce.py 抽出） | edit: character_sheet,chroma,enforce
environment.py         @OPS/demo     | environment ·红 环境黑板（单一数据源）+ 地表材质 | edit: actors,physics,physics_rules
film_assemble.py       @SHOT/assemble | 镜头装配层 —— 模型填 3 个字段，代码完成全部映射 | edit: character_sheet,chroma,film_assemble_render,photo_rules,render_v4,render_v4_main,subtitle
film_assemble_render.py @SHOT/assemble | film_assemble 分镜渲染与自检（原 165 行抽出）。 | edit: character_sheet,chroma,film_assemble,framerate,photo_rules,subtitle
foot_lock.py           @SHOT/skel     | 足锁：接触时锁定脚的世界坐标，切换用三次惯性化平滑。 | edit: pose
framerate.py           @ATOM/frame    | framerate.py —— 帧率/时间基准（单一数据源） | edit: _chk_base,_chk_physics,_solver_chain,_solver_chain_aux,anchor,build_phase_render,build_util,build_video,film_assemble_render,loop_engine,render_desert_banner,render_gate_banner,render_v4,render_v4_main,subtitle,systems,systems_phys,systems_selfcheck,systems_view
gate_doc.py            @GATE/size     | 文档体积门禁：防止主干/契约无限膨胀（瘦身成果已回归两次） | edit: （无）
gate_module.py         @GATE/size     | 模块体积门禁：单模块 ≤400 行 且 ≤12000 字符（约 128K 上下文的 30%）。 | edit: （无）
gate_size.py           @GATE/size     | 产物体积门禁：防止媒体产物无上限增长（回归过两次） | edit: （无）
gen_chain.py           @SOLVE/spec     | 链式参考图生成调度：上一批输出 = 下一批参考图 | edit: （无）
genqueue.py            @SHOT/gen      | genqueue · 生图任务队列（铁律81-85） | edit: build_phase_gen,build_util,build_video,driver,pose,prompt_tpl
groundline.py          @ATOM/path     | 地基线探测：从背景图自动找出"人能站在哪条水平线上"。 | edit: build_phase_setup,build_util,build_video
loop_engine.py         @SHOT/loop     | 按需调度引擎 —— 解决"全量跑"问题 | edit: framerate,render_v4
motion_lib.py          @OPS/demo     | 运动原子函数集 Motion Atom Library | edit: （无）
oneshot.py             @ATOM/phys     | X_i：一次性动作（转身 / 停下 / 挥手 / 交互起手）的表示与播放。 | edit: （无）
param_decl.py          @ATOM/rule     | param_decl — 参数声明与反问接口 | edit: _surface,cloth_aero,cloth_wire
path.py                @ATOM/path     | 路径约束：把位置表示为「弧长 s + 横向偏移 offset」，使其永远在路径上。 | edit: build_phase_render,build_phase_setup,build_util,build_video,path_align,shot_plan
path_align.py          @ATOM/path     | 路径—路面对齐（契约 contracts/path_align.md，铁律95-98） | edit: build_phase_setup,path
photo_rules.py         @ATOM/rule     | 摄影规则确定性层 | edit: character_sheet,film_assemble,film_assemble_render,render_v4,render_v4_main
physics.py             @ATOM/phys     | physics.py —— 物理原子层（逻辑唯一实现，数值全外置） | edit: _chk_base,_chk_motion,_common,_px,_solver_chain,actors,environment,render_desert_banner,render_gate_banner,render_v4,render_v4_main,systems,systems_phys,systems_selfcheck,systems_view
physics_rules.py       @ATOM/phys     | physics_rules.py —— 物性推导与风力计算 | edit: _common,environment,systems,systems_phys,systems_selfcheck,systems_view
placement.py           @ATOM/path     | 语义定位点：把一个语义点 → 世界坐标落位。 | edit: build_util,build_video,shot_plan
pose.py                @SHOT/skel     | pose —— 统一姿态求解器：FK 引擎 + 解析 IK + 笛卡尔足端轨迹 | edit: build_phase_gen,build_util,foot_lock,genqueue,pose_prompt,pose_selfcheck,puppet,骨架_行走
pose_prompt.py         @SHOT/skel     | pose_prompt —— 轨迹 → 结构性提示词（铁律73：骨架图永不进画面） | edit: pose
pose_selfcheck.py      @SHOT/skel     | pose 的自检/检查逻辑（由 _extract_tool.py 从 pose.py 抽出） | edit: pose
prompt_tpl.py          @SHOT/gen      | prompt_tpl —— 按族抽象的生图提示词模板（铁律81-85） | edit: build_phase_gen,genqueue
puppet.py              @SHOT/skel     | 部件化木偶（cutout puppet）—— V6 补帧的正确解法。 | edit: _common,pose
rain_layer.py          @ATOM/water    | rain_layer.py — 雨层渲染（复用 water.py 全部公式，本模块不含任何物性常数） | edit: _common,water
render_desert_banner.py @OPS/demo     | 沙漠幡旗 —— 独立验证项目（不复用大唐偷渡客的任何分镜） | edit: actors,character_sheet,framerate,physics,render_v4,systems
render_gate_banner.py  @OPS/demo     | 沙漠幡旗 —— 独立验证项目（不复用大唐偷渡客的任何分镜） | edit: actors,character_sheet,framerate,physics,render_v4,systems
render_v4.py           @SHOT/_top     | 渲染 v4 —— 按需调度版 | edit: actors,film_assemble,framerate,loop_engine,photo_rules,physics,render_desert_banner,render_gate_banner,render_v4_main,systems
render_v4_main.py      @SHOT/_top     | render_v4 自检与出片主流程（原 182 行上帝函数抽出）。 | edit: actors,character_sheet,film_assemble,framerate,photo_rules,physics,render_v4,systems
run_batch.py           @OPS/demo     | run_batch.py —— 分批自检跑批器 | edit: enforce
run_gen_queue.py       @OPS/demo     | Stage 3.5：驱动生图队列，打印代码下发的参数与提示词。 | edit: build_phase_gen
scale_map.py           @ATOM/path     | scale_map.py — 比例尺层：把「米」换算成「像素」 | edit: build_phase_setup,build_util,build_video,shot_plan
shot_plan.py           @SHOT/gen      | 镜头规划 / 生图任务包：告诉 AI 路画在哪、物体多大、落在哪、提示词怎么写。 | edit: build_phase_gen,build_util,build_video,path,placement,scale_map,wind_sway
skeleton_runtime.py    @SHOT/skel     | Spine 格式骨架求解器 —— 不需要官方 runtime | edit: skeleton_runtime_selfcheck,systems,systems_phys,systems_selfcheck,systems_view
skeleton_runtime_selfcheck.py @SHOT/skel     | skeleton_runtime 自检（原 107 行 __main__ 块抽出）。 | edit: skeleton_runtime
solver.py              @SOLVE/_top     | solver.py —— facade（对外 API 不变，实现已按职责拆到 _solver_*.py） | edit: _solver_base,_solver_chain,_solver_geom,_solver_probe,_solver_reuse,_solver_run,_solver_sheet,_问卷,solver_check,solver_survey
solver_check.py        @SOLVE/check    | solver 自检编排器（从 solver.py 拆出，业界：preserve public exports）。 | edit: _chk_assemble,_chk_base,_chk_chain,_chk_motion,_chk_multi,_chk_pack,_chk_physics,_chk_reuse,_chk_sheet,_chk_survey,solver
solver_survey.py       @SOLVE/spec     | solver_survey —— 从 solver.py 切出（业界：文件 150-500 行最优）。 | edit: _chk_assemble,_chk_base,_chk_survey,driver,solver
subtitle.py            @SHOT/sub      | 字幕渲染层 —— 修一个真 bug | edit: film_assemble,film_assemble_render,framerate,systems_view
systems.py             @SHOT/sys      | systems：常量与编排。已拆出 systems_selfcheck / systems_phys / systems_view（见 IM | edit: framerate,physics,physics_rules,render_desert_banner,render_gate_banner,render_v4,render_v4_main,skeleton_runtime,systems_phys,systems_selfcheck,systems_view
systems_phys.py        @SHOT/sys      | systems 的自检/检查逻辑（由 _extract_tool.py 从 systems.py 抽出） | edit: framerate,physics,physics_rules,skeleton_runtime,systems
systems_selfcheck.py   @SHOT/sys      | systems 的自检/检查逻辑（由 _extract_tool.py 从 systems.py 抽出） | edit: framerate,physics,physics_rules,skeleton_runtime,systems
systems_view.py        @SHOT/sys      | systems 的自检/检查逻辑（由 _extract_tool.py 从 systems.py 抽出） | edit: composite,framerate,physics,physics_rules,skeleton_runtime,subtitle,systems
water.py               @ATOM/water    | water.py —— 降水与水体纯函数层（雨滴 / 溅射 / 涉水 / 水面波） | edit: rain_layer
wind_response.py       @ATOM/aero     | 风响应统一数值层：所有受风物体的频率/幅度，一律由族+尺寸+风速算出。 | edit: _common,build_phase_gen,build_phase_setup,build_phase_time,cloth_wire,wind_sway
wind_sway.py           @ATOM/aero     | 植物风摆：程序化三层叠加（trunk / branch / leaf），根部权重恒 0。 | edit: build_util,build_video,shot_plan,wind_response
zmp.py                 @ATOM/phys     | X_c 失衡判定：ZMP + 支撑多边形。 | edit: （无）
占位音轨.py                @OPS/demo     | 占位音轨生成器（业界称 scratch track / prelay） | edit: （无）
骨架_行走.py               @OPS/demo     | 骨架_行走 —— 侧面行走骨架图集（pose.py 驱动） | edit: pose

## 顶层入口（不在 HIER 分组内，独立成片/装配入口）
build_video.py         @TOP         | 合成出片：探测基线 + 路径约束 + 语义落位 + 程序化风摆。 | edit: _ground_arc,_surface,build_phase_asset,build_phase_gen,build_phase_render,build_phase_setup,build_phase_time,build_util,chroma,cloth_wire,composite,framerate,genqueue,groundline,path,placement,scale_map,shot_plan,wind_sway
render_v4.py           @TOP         | 渲染 v4 —— 按需调度版 | edit: actors,film_assemble,framerate,loop_engine,photo_rules,physics,render_desert_banner,render_gate_banner,render_v4_main,systems
render_v4_main.py      @TOP         | render_v4 自检与出片主流程（原 182 行上帝函数抽出）。 | edit: actors,character_sheet,film_assemble,framerate,photo_rules,physics,render_v4,systems
solver.py              @TOP         | solver.py —— facade（对外 API 不变，实现已按职责拆到 _solver_*.py） | edit: _solver_base,_solver_chain,_solver_geom,_solver_probe,_solver_reuse,_solver_run,_solver_sheet,_问卷,solver_check,solver_survey
