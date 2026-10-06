# proc —— 程序化动画引擎（三层契约图）

本文件由 `python gen_index.py` **自动生成**，职责与行数据来自各文件顶部契约块，不会与代码脱节。

点开顺序：**本文件 → 中模块 `__init__.py` → 小模块**。每层只暴露下一层的一句话职责。

## 流水线

```
画线 shape → 填色 color → 装背景 scene → 跑起来 motion → mp4
```

## 三层树

### (根)/
  - `beat_demo.py` 78 行 — 入口脚本：走 beat 时间线出演示片
  - `check.py` 488 行 — Enforce architecture contracts: layer direction, size limits, public s
  - `formula.py` 123 行 — 公式注册表与 STUB 门禁：缺公式抛错并给搜索关键词，禁止凭记忆写近似值
  - `gen_index.py` 131 行 — 从各文件顶部契约块抽取职责，自动生成 INDEX.md（文档永不与代码脱节）
  - `jumpscan.py` 46 行 · — 跳帧扫描器：逐帧量化视频帧间差，定位硬跳帧
  - `prompt2spec.py` 211 行 — 提示词 → 规格对照：逐字段判能做/降级/不能，STUB 带搜索提示

### base/
  - `base/assertrun.py` 142 行 — 统一断言执行器——各模块 self_check 改写为"计算抽 helper + 数据表 chk"

### color/
  - `color/paint.py` 142 行 — 按胶囊 region 查色卡，配合 SDF 法线做明暗着色；颜色挂 region 不挂像素

### motion/
  - `motion/beat.py` 397 行 — 节拍时间线：prep→stroke→relax 三相位串多段动作，含跨段无跳变与互斥校验
  - `motion/camera.py` 196 行 — 相机：视高/焦距/px_per_m(Z)/反投影；人物与路必须共用同一台
  - `motion/capbridge.py` 249 行 — 能力表分类归一 —— 姿态/增量/物理/辅助四类分流，并把非标准签名适配成 (u,params)
  - `motion/constraint_ext.py` 184 行 — 约束扩展三能力：rope / hinge_door / toppling
  - `motion/crowd.py` 390 行 — 多主体：ORCA 互避 + 胶囊接触分离 + 击掌时序
  - `motion/layer.py` 233 行 — 动作分层合成与声明式求解
  - `motion/physics_ext.py` 438 行 — 物理扩展五能力：ccd/broadphase/gravity_off/friction/overlap_resolve
  - `motion/rigid.py` 257 行 — 刚体物理：半隐式欧拉定步长积分 + 冲量法碰撞响应 + 恢复系数衰减
  - `motion/run.py` 342 行 — 时间线与出片：逐帧渲染并写 mp4
  - `motion/stage.py` 372 行 — 场景合成：烘焙背景 + 人物 + 出片
  - `motion/wind.py` 137 行 — 风场：主弯曲 + 细节弯曲，相位纳入世界坐标使异株不同步

### motion/character/
  - `motion/character/ball.py` 134 行 — 球体与碰撞（B10/C18/C20 通用）
  - `motion/character/carry.py` 442 行 — 搬运箱子（E26）：抱起 → 走 → 放下
  - `motion/character/catch.py` 170 行 — 接球（B11 / D22 通用）
  - `motion/character/climb.py` 199 行 — 爬梯：五效应器三态循环上升，肘膝由两骨IK反解保证骨长守恒
  - `motion/character/crouch.py` 176 行 — 下蹲（A7）
  - `motion/character/gesture.py` 316 行 — 注视转移 / 手指敲击 / 翻页 —— 头部与手部的短促动作
  - `motion/character/jump.py` 169 行 — 原地跳跃（A3）
  - `motion/character/kick.py` 215 行 — 踢球（A6/B10 通用）
  - `motion/character/pass_ball.py` 257 行 — D22 两人传球：A 投 → 飞行 → B 接 → 缓冲 → B 投回 → A 接
  - `motion/character/prop.py` 477 行 — 道具交接 —— pickup→held→release→recovery 四相位，所有权 world↔hand 显式切换
  - `motion/character/push.py` 116 行 — 推动箱体（B12）：掌为运动学驱动，箱受地面摩擦与接触约束
  - `motion/character/roll.py` 105 行 — 纯滚动（E25/球体滚动）：无滑移约束 v=ω·r + 能量守恒
  - `motion/character/run.py` 268 行 — 跑步与急停（A2）
  - `motion/character/selfcheck.py` 216 行 — 自检脚本：python -m character.selfcheck
  - `motion/character/sit.py` 263 行 — 坐下/站起动作 —— 7 关键姿态 + 三相位，输出与 gait 同构的关节字典
  - `motion/character/throw.py` 309 行 — 投掷（B10 / D22 / E27 通用）
  - `motion/character/turn.py` 363 行 — yaw 连续转身 + 原地换步 —— 让人物真的"转过去"而不是镜像翻转

### motion/character/body/
  - `motion/character/body/cloth.py` 118 行 — 布料：Verlet 链、披帛/衣摆、draw_character 总入口
  - `motion/character/body/gait.py` 211 行 — 步态主函数：臂摆、膝屈曲线、相位推进与 BODY_SPEC
  - `motion/character/body/joints.py` 130 行 — 关节表、躯干摆动常量、步态预设与 gait_params
  - `motion/character/body/leg.py` 164 行 — 腿：两骨 IK、踝高曲线、脚掌俯仰与脚部关键点
  - `motion/character/body/proportions.py` 91 行 — 人体比例常数（Drillis&Contini 1966）与步频/步态常量
  - `motion/character/body/render.py` 228 行 — 渲染：相机投影、SDF 场栅格化、法线明暗着色
  - `motion/character/body/sdf.py` 62 行 — SDF 场原语（胶囊/圆/椭圆/平滑并集）+ BODY_SPEC 胶囊装配清单

### motion/creature/
  - `motion/creature/bird_fly.py` 521 行 ⚠ — 鸟飞扑翼：三位置角 + 下扑/上举不对称 + 准定常叶素法气动（升力/推力由积分真算）
  - `motion/creature/climb_rock.py` 251 行 — 不规则支点攀岩：环境查询支点 + 两骨 IK 放置 + 三点支撑
  - `motion/creature/fish_swim.py` 190 行 — 鱼游行波推进：等弧长脊椎链 + carangiform/anguilliform 包络 + St 反解
  - `motion/creature/quadruped.py` 212 行 — 四足步态——Hildebrand 占空比β+四足相位表参数化，支撑相足端零滑移

### motion/phenom/
  - `motion/phenom/cradle.py` 82 行 — 常见物理现象能力族（leaf_fall/fracture/water_jet/newton_cradle/turntable）
  - `motion/phenom/fracture.py` 235 行 — 砖墙被球撞击碎裂（内聚区 bond 应变阈值失效）
  - `motion/phenom/leaf.py` 110 行 — 常见物理现象能力族（leaf_fall/fracture/water_jet/newton_cradle/turntable）
  - `motion/phenom/turntable.py` 72 行 — 常见物理现象能力族（leaf_fall/fracture/water_jet/newton_cradle/turntable）
  - `motion/phenom/water.py` 111 行 — 常见物理现象能力族（leaf_fall/fracture/water_jet/newton_cradle/turntable）

### motion/rigid2d/
  - `motion/rigid2d/collide.py` 360 行 — 碰撞检测：SAT 盒-盒、地面、圆-线段（含参考面裁剪）
  - `motion/rigid2d/core.py` 92 行 — 2D 刚体常量（Box2D 原文值）与几何基元（Body2/旋转/叉积）
  - `motion/rigid2d/sim.py` 162 行 — 场景仿真：stack/ramp/pendulum 三个能力 + self_check
  - `motion/rigid2d/solve.py` 124 行 — 接触求解：Contact 预处理、冲量施加、顺序冲量迭代、距离约束
  - `motion/rigid2d/world.py` 346 行 — World：接触生成、休眠、积分与位置松弛（物理主循环）

### scene/
  - `scene/bgpack.py` 442 行 — 背景包：五种配方的参数表与展开，输出 geom 供人物对齐
  - `scene/detail.py` 498 行 — 近处细节：草叶/窗户/叶簇/远处行人，按 LOD 分级

### scene/kit/
  - `scene/kit/canvas.py` 77 行 — Canvas 画布 + 噪声基元（value noise / fBm / smoothstep）
  - `scene/kit/city.py` 63 行 — 城：多排矩形坡顶房屋，越近越大越暗
  - `scene/kit/compose.py` 121 行 — 场景组合：元件注册表、配方表、compose 总入口
  - `scene/kit/indoor.py` 121 行 — 室内一点透视：房间壳几何、投影 proj()、水磨石地面
  - `scene/kit/props.py` 120 行 — 室内陈设：落地窗/书架墙/挂画/家具，输出世界坐标锚点供人物就位
  - `scene/kit/road.py` 76 行 — 路面半宽、禁用区间、路面绘制与避让裁剪
  - `scene/kit/selfcheck.py` 104 行 — 自检：python -m kit.selfcheck
  - `scene/kit/sky.py` 111 行 — 天空：Perez 天光模型、地平线色、色带 ramp
  - `scene/kit/terrain.py` 89 行 — 地形：山脊 midpoint displacement、地面、色带
  - `scene/kit/tree.py` 96 行 — 树：Honda 1971 三参数分形（分叉角/长度比/深度）

### shape/
  - `shape/hand.py` 216 行 — 手部解剖：掌与五指的关节/胶囊，按真实比例与外展角生成
  - `shape/line.py` 213 行 — 骨架模板 → 胶囊形体(带 region) → SDF → 轮廓线与细节线

### showreel/
  - `showreel/cafe.py` 200 行 — 咖啡馆 12 秒时间线：四段动作（坐姿→抬头→起身走→落座沙发）
  - `showreel/camrig.py` 223 行 — 连续相机运镜（跟随/横移/推拉/低角度/俯拍/微距），全程 C1 连续不切镜
  - `showreel/params.py` 282 行 — 全局物理参数的连续扰动曲线（重力/摩擦/风/弹性/质量/时间缩放）
  - `showreel/phys.py` 184 行 — 90秒物理预跑，轨迹存 npz、状态 pickle 成 checkpoint 续跑
  - `showreel/render.py` 260 行 — 分层合成——背景/远雨/物体/角色/近雨/辉光，复用既有管线不自造
  - `showreel/scene.py` 403 行 — 90 秒场景世界——多米诺/方块堆/斜坡/摆锤/墙/梯子/移动靶/绳/铰链门
  - `showreel/seam.py` 114 行 — 段内跳帧与段间接缝的流式检测，不全帧入内存
  - `showreel/shard.py` 147 行 — 90秒长镜头分段渲染落盘再 concat，规避内存与时限
  - `showreel/timeline.py` 249 行 — 按视频帧查表渲染，背景/物体/角色/雨丝，相机不切镜

### tests/
  - `tests/cases.py` 128 行 — 35 项测试用例声明（测试第二步：声明）
  - `tests/cases_base.py` 489 行 — def case_A1():
  - `tests/cases_carry.py` 144 行 — E 组搬运用例（E26 搬运箱子）
  - `tests/cases_creature.py` 118 行 — # 契约: tests.cases_creature
  - `tests/cases_crowd.py` 207 行 — D 组多主体用例（人群碰撞 / 两人击掌）
  - `tests/cases_gap.py` 293 行 — # 契约: tests.cases_gap
  - `tests/cases_mixed.py` 185 行 — # 契约: tests.cases_mixed
  - `tests/cases_pass.py` 97 行 — D22 两人传球 用例
  - `tests/cases_phenom.py` 86 行 — # 契约: tests.cases_phenom
  - `tests/cases_phys.py` 281 行 — C 组物理用例（弹球 / 两球对撞）
  - `tests/cases_throw.py` 152 行 — B10 扔球 / B11 接球 用例
  - `tests/common.py` 79 行 — 35 项用例门检与执行（测试第三步：跑）
  - `tests/criteria.py` 202 行 — # 契约: tests.criteria
  - `tests/gen.py` 237 行 — 渲染与剪影校验（测试第二步：出片并量剪影）
  - `tests/gen_doc.py` 107 行 — 生成 35 项推进文档（xlsx）
  - `tests/harness.py` 369 行 — 物理与动作判据库（测试第一步：判定）
  - `tests/run_all.py` 194 行 — if __package__ in (None, ""):

### tools/
  - `tools/baseline.py` 312 行 — 复杂度债务棘轮——基线入版本库，只降不升；新增/恶化即 FAIL，修复自动收紧
  - `tools/capaudit.py` 115 行 — 能力可驱动性审计：注册进 CAP 不等于能被时间线驱动
  - `tools/clone.py` 132 行 — 重复代码(克隆)检测工具  —— 项目瘦身第二阶段
  - `tools/complexity.py` 212 行 — 圈复杂度门禁——用 lizard 实测 CCN，替代自造的「函数>50行」行数规则
  - `tools/consistency.py` 315 行 — 三表一致性：能力注册表 / EXEC 用例表 / 桥接器互为闭包
  - `tools/debtledger.py` 218 行 — R19 已知债务台账：显式登记、有归属、带到期日、只减不增。
  - `tools/docsync.py` 249 行 — 检测 README / INDEX 里的数字声明是否与脚本实测一致，抓"文档说一套、代码是另一套"
  - `tools/efps.py` 100 行 — 有效帧率：渲染了 N 帧不代表画面动了 N 帧
  - `tools/faultbench.py` 287 行 — 缺陷注入基准：注入已知代码缺陷，实测工具矩阵能否检出，量化召回率并暴露盲区
  - `tools/gate.py` 162 行 — 统一自检入口：一键跑全部长期工具，汇总退出码，支持 --json 机器可读输出
  - `tools/layers.py` 108 行 — 分层契约门禁——包装 import-linter，替代自造的 R1(逆向依赖)/R4(上帝包)
  - `tools/motionqual.py` 399 行 — 补齐业界动作质量指标中我们缺失的那几项（稳定性/抖动/自穿透/接触/步态/游动）
  - `tools/mutate.py` 139 行 — 判据效力变异测试：给判据注入必错的坏输入，仍判 PASS 即判据无牙齿
  - `tools/presearch.py` 326 行 — 本地前置检索：先查项目前置库，未达阈值才建议联网搜（不静默跳过）。
  - `tools/provenance.py` 223 行 — 核验判据阈值与其出处自洽、并探测"先调阈值让它过、后补出处"的 HARKing 行为
  - `tools/reach.py` 152 行 — 从活跃入口出发的 import 可达性分析（SCARF 的 Survey 阶段）。
  - `tools/refcheck.py` 472 行 — 核验收工判据/文档里引用的 arXiv 与 DOI 是否真实存在、标题是否与判据语义相关，抓"贴牌引用"
  - `tools/repro.py` 151 行 — 假阳性豁免验证：声称假阳性必须附可执行最小复现，跑得通才算，跑不通按真问题处理
  - `tools/smell.py` 329 行 — 代码异味检查：补 faultbench 实测暴露的 8 类静态盲区（静默异常/判据恒真/自检空转等）

## 契约规则与出处（不凭记忆，逐条可查）

| 规则 | 阈值/要求 | 出处 |
|---|---|---|
| R1 依赖单向 | 上层可依赖下层，**含传递依赖** | import-linter layers contract: "even indirectly" |
| R2 模块行数 | **50~500 行**；<50 不配独立成文件，应与兄弟模块合并 | AlgoMaster / mrognlie coding guide（两处独立来源） |
| R3 函数行数 | ≤50 行 | mrognlie coding guide |
| R4 包条目数 | 3~20 个 | mrognlie coding guide |
| R5 公开名 | ≤40，超出说明模块干太多 | AlgoMaster: "A module with 40 public names is doing too much" |
| R6 契约首行 | ≤72 字符 | numpydoc 规范 |
| R7 职责单一 | 一句话说清；出现两个"和"就该拆 | AlgoMaster |
| R8 避免过深嵌套 | 反模式：too many tiny packages / god package | Smalltalk Package Anti-Patterns |
| R9 圈复杂度 | <=10；>15 需书面说明 | NASA SWEHB 3.2.2 / NIST 结构化测试方法论 |
| R10 包必须真实可导入 | import 一遍不报错 | FixDevs: Verify with a clean import |

已知偏差（有依据，非疏漏）：
- `shape/` `color/` 各只有 1 个模块，低于 R4 下限。但强行再拆会产生
  R8 警告的 "too many tiny packages"，两条规则在此冲突，取 R8。
- `motion/character/sdf.py` 46 行低于 R2 下限，但被 `__init__/render/selfcheck`
  三处引用，合并会破坏既有公开面，暂保留。

## 当前问题（check.py 实时输出）

共 1 项：

- [R2 超纲] motion/bird_fly.py 522>500
