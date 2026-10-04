# proc —— 程序化动画引擎（三层契约图）

本文件由 `python gen_index.py` **自动生成**，职责与行数据来自各文件顶部契约块，不会与代码脱节。

点开顺序：**本文件 → 中模块 `__init__.py` → 小模块**。每层只暴露下一层的一句话职责。

## 流水线

```
画线 shape → 填色 color → 装背景 scene → 跑起来 motion → mp4
```

## 三层树

### (根)/
  - `beat_demo.py` 66 行 — 入口脚本：走 beat 时间线出演示片
  - `check.py` 262 行 — Enforce architecture contracts: layer direction, size limits, public s
  - `formula.py` 123 行 — 公式注册表与 STUB 门禁：缺公式抛错并给搜索关键词，禁止凭记忆写近似值
  - `gen_index.py` 129 行 — 从各文件顶部契约块抽取职责，自动生成 INDEX.md（文档永不与代码脱节）
  - `prompt2spec.py` 211 行 — 提示词 → 规格对照：逐字段判能做/降级/不能，STUB 带搜索提示

### color/
  - `paint.py` 142 行 — 按胶囊 region 查色卡，配合 SDF 法线做明暗着色；颜色挂 region 不挂像素

### motion/
  - `beat.py` 376 行 — 节拍时间线：prep→stroke→relax 三相位串多段动作，含跨段无跳变与互斥校验
  - `cafe.py` 179 行 — 咖啡馆 12 秒时间线：四段动作（坐姿→抬头→起身走→落座沙发）
  - `camera.py` 185 行 — 相机：视高/焦距/px_per_m(Z)/反投影；人物与路必须共用同一台
  - `rigid.py` 246 行 — 刚体物理：半隐式欧拉定步长积分 + 冲量法碰撞响应 + 恢复系数衰减
  - `run.py` 264 行 — 时间线与出片：逐帧渲染并写 mp4
  - `stage.py` 361 行 — 场景合成：烘焙背景 + 人物 + 出片
  - `wind.py` 137 行 — 风场：主弯曲 + 细节弯曲，相位纳入世界坐标使异株不同步

### motion/character/
  - `ball.py` 134 行 — 球体与碰撞（B10/C18/C20 通用）
  - `cloth.py` 118 行 — 布料：Verlet 链、披帛/衣摆、draw_character 总入口
  - `crouch.py` 165 行 — 下蹲（A7）
  - `gait.py` 211 行 — 步态主函数：臂摆、膝屈曲线、相位推进与 BODY_SPEC
  - `gesture.py` 305 行 — 注视转移 / 手指敲击 / 翻页 —— 头部与手部的短促动作
  - `joints.py` 130 行 — 关节表、躯干摆动常量、步态预设与 gait_params
  - `jump.py` 158 行 — 原地跳跃（A3）
  - `kick.py` 204 行 — 踢球（A6/B10 通用）
  - `leg.py` 155 行 — 腿：两骨 IK、踝高曲线、脚掌俯仰与脚部关键点
  - `prop.py` 464 行 — 道具交接 —— pickup→held→release→recovery 四相位，所有权 world↔hand 显式切换
  - `proportions.py` 73 行 — 人体比例常数（Drillis&Contini 1966）与步频/步态常量
  - `render.py` 228 行 — 渲染：相机投影、SDF 场栅格化、法线明暗着色
  - `run.py` 254 行 — 跑步与急停（A2）
  - `sdf.py` 62 行 — SDF 场原语（胶囊/圆/椭圆/平滑并集）+ BODY_SPEC 胶囊装配清单
  - `selfcheck.py` 205 行 — 自检脚本：python -m character.selfcheck
  - `sit.py` 263 行 — 坐下/站起动作 —— 7 关键姿态 + 三相位，输出与 gait 同构的关节字典
  - `turn.py` 181 行 — yaw 连续转身 + 原地换步 —— 让人物真的"转过去"而不是镜像翻转

### scene/
  - `bgpack.py` 442 行 — 背景包：五种配方的参数表与展开，输出 geom 供人物对齐
  - `detail.py` 498 行 — 近处细节：草叶/窗户/叶簇/远处行人，按 LOD 分级

### scene/kit/
  - `canvas.py` 77 行 — Canvas 画布 + 噪声基元（value noise / fBm / smoothstep）
  - `city.py` 63 行 — 城：多排矩形坡顶房屋，越近越大越暗
  - `compose.py` 121 行 — 场景组合：元件注册表、配方表、compose 总入口
  - `indoor.py` 110 行 — 室内一点透视：房间壳几何、投影 proj()、水磨石地面
  - `props.py` 109 行 — 室内陈设：落地窗/书架墙/挂画/家具，输出世界坐标锚点供人物就位
  - `road.py` 76 行 — 路面半宽、禁用区间、路面绘制与避让裁剪
  - `selfcheck.py` 93 行 — 自检：python -m kit.selfcheck
  - `sky.py` 111 行 — 天空：Perez 天光模型、地平线色、色带 ramp
  - `terrain.py` 89 行 — 地形：山脊 midpoint displacement、地面、色带
  - `tree.py` 96 行 — 树：Honda 1971 三参数分形（分叉角/长度比/深度）

### shape/
  - `hand.py` 216 行 — 手部解剖：掌与五指的关节/胶囊，按真实比例与外展角生成
  - `line.py` 213 行 — 骨架模板 → 胶囊形体(带 region) → SDF → 轮廓线与细节线

### tests/
  - `cases.py` 115 行 — 35 项测试用例声明（测试第二步：声明）
  - `cases_phys.py` 110 行 — C 组物理用例（弹球 / 两球对撞）
  - `gen.py` 230 行 — 渲染与剪影校验（测试第二步：出片并量剪影）
  - `gen_doc.py` 107 行 — 生成 35 项推进文档（xlsx）
  - `harness.py` 385 行 — 物理与动作判据库（测试第一步：判定）
  - `run_all.py` 503 行 ⚠ — 35 项用例门检与执行（测试第三步：跑）

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

共 11 项：

- [R3 函数过长] motion/cafe.py::pose_at 51>50
- [R3 函数过长] motion/run.py::run 65>50
- [R1 逆向依赖] tests/cases_phys.py -> motion
- [R1 逆向依赖] tests/gen_doc.py -> motion
- [R1 逆向依赖] tests/run_all.py -> motion
- [R2 超纲] tests/run_all.py 504>500
- [R3 函数过长] tests/run_all.py::case_A2 55>50
- [R3 函数过长] tests/run_all.py::case_B9 54>50
- [R4 包条目数] shape 2 不在 3~20
- [R4 包条目数] color 1 不在 3~20
- [R4 包条目数] motion 24 不在 3~20
