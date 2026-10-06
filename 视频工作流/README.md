# 视频工作流 —— 程序化动画引擎

**一句话**：用代码算出关节与物理，逐帧光栅化成图，合成 mp4。**不调用任何生图模型。**

2026-10-05 重写。旧 README 描述的是"生图 + 抠像合成"的旧链路，与本代码无关，
已归档至 `_archive_文档_旧链路/`。

---

## 一、它到底是什么

不是文生视频，不是扩散模型。是一个**自己写渲染器的 2D 动画引擎**：

```
骨架关节 → 胶囊形体 → SDF 距离场 → 光栅化 → 着色 → mp4
```

人物不是一张张画出来的，是**每帧按公式算出来再光栅化**的。
所以能验"物理对不对"：脚有没有滑、手有没有穿透杯子、动量守不守恒——全部可量化。

---

## 二、渲染管线（五步）

| 步 | 模块 | 干什么 |
|---|---|---|
| 1 画线 | `shape/line.py` | 骨架模板 → 胶囊形体（每根带 region 标签）→ SDF 场 |
| 2 填色 | `color/paint.py` | 按 region 查色卡 + SDF 法线明暗 |
| 3 装背景 | `scene/kit/` | 室内一点透视、陈设锚点 |
| 4 跑起来 | `motion/` | 时间线 → 逐帧关节 → 投影 → 光栅化 |
| 5 出片 | `motion/run.py` | 合成写 mp4 |

**关键设计：颜色挂 region（胶囊），不挂像素。**
骨架一动，形体跟着动，颜色自动跟着走——从结构上杜绝"披帛飘出身体""脚朝后"这类病。

---

## 三、规模（2026-10-06 脚本实测，非记忆值）

```
活跃文件  78 个         ← reach.py: 入口 11 个，可达性分析得出
孤立文件  24 个         ← 无任何活跃入口引用
能力表    注册 30（可直接驱动时间线 10）
测试      PASS 39 / FAIL 0 / STUB 0 / ERROR 0（共 39 项）
仓库体积  工作树 1.1 MB / GitHub 平台 136 MB（含 git 历史对象）
```

数字来源与复核方式（A4 铁律：文档数字由脚本同步，不手填）：

| 项 | 取数命令 |
|---|---|
| 活跃 / 孤立 | `python3 _proc/tools/reach.py` |
| 测试成绩 | `python3 _proc/tests/run_all.py` |
| 模块索引 | `python3 _proc/gen_index.py`（改代码后必须重跑，否则 INDEX 过期） |

**体积口径说明**：三个数字都对，但统计对象不同——工作树 1.1 MB 是 `du` 当前文件；
GitHub 平台 136 MB 含全部 git 历史对象（历史上曾推入视频产物，已从工作树删除但历史仍在）；
此前 README 的 7.4 MB 是删除视频产物过程中的中间态，不再作为声明值。

**完成度如实披露**（不藏在附录）：39 项测试**全部通过、0 项 STUB**（缺口用例已全部补执行体，见第九节）；
注册 30 个能力中 **仅 10 个（33%）可直接驱动时间线**，注册 ≠ 可调用。

---

## 四、怎么跑

干净环境（无需设 PYTHONPATH）：

```bash
python3 _proc/beat_demo.py      # 走 beat 时间线出演示片
python3 _proc/motion/cafe.py    # 咖啡馆 12 秒（四段动作）
python3 _proc/tests/run_all.py  # 跑 39 项测试门检
python3 _proc/check.py          # 架构契约扫描
python3 _proc/tools/gate.py     # 统一门禁入口（7 项，--json 机读）
```

每个 `.py` 顶部有 `__file__` 锚定的自举块，自动上溯定位 `_proc`，直接跑即可。

门禁工具依赖两个业界库（不重复造轮子），跑之前先装：

```bash
pip install -r _proc/tools/requirements.txt   # import-linter / lizard
```

依赖缺失时门禁**报错而非静默当通过**（`layers.py` 契约数为 0 判失败、`complexity.py` 缺 lizard 返回 error）。

R1 依赖方向由 **import-linter**（`.importlinter`，双包名配置）产出，R3 函数长度由 **lizard** 产出；
`check.py` 不再自造这两条规则——自造 ALLOW 表只认 `_proc.*`，对扁平包名 `motion.xxx` 完全漏检（实测注入未被报出）。

---

## 五、三层契约结构

```
_proc/                     大模块  __init__.py 只登记契约
├─ shape/   画线           line.py, hand.py
├─ color/   填色           paint.py
├─ scene/   背景           kit/indoor.py, kit/props.py
├─ motion/  跑起来         beat, camera, crowd, rigid, rigid2d, run
│  └─ character/           gait, sit, turn, jump, run, kick,
│                          throw, catch, carry, prop, gesture,
│                          crouch, cloth, ball, leg, joints, render
└─ tests/                  harness(判据), cases_*, run_all
```

**契约明文化**：每个文件顶部有契约块，含一句话职责 / 输入 / 输出 / 依赖 / 被依赖 / 约束 / 校验入口。
`_proc/INDEX.md` 由 `gen_index.py` 从这些契约块**自动生成**——代码改了不跑它，文档就不会错。

---

## 六、硬规矩（改代码前必读）

1. **搜索先行** —— 每个能力开工前先搜业界/文献依据，把出处写进 `source` 参数。凭记忆写的值一律不许进代码。
2. **契约明文化** —— 新文件必须写契约块，缺了 `check.py` 会报。
3. **单一渲染管线** —— 所有人形一律走 `run.draw_actor`。测试里曾有人另写精简渲染，只画头和手，导致腿脚消失。已加剪影判据（`silhouette_gap_px` / `span_ratio` / `mask_iou`）兜底。
4. **缺能力不静默降级** —— `beat.require()` 缺能力抛 `CapabilityError` 并给搜索提示，绝不偷偷降级成走路。
5. **模块 >500 行必须拆** —— 拆之前先搜拆分依据。
6. **产物不入库** —— `.gitignore` 已排除 `*.mp4` / `__pycache__` / 归档目录。

---

## 七、已实现能力（注册 30，按可驱动性分四类）

**重要：注册 ≠ 能被时间线调用。** 经 `tools/capaudit.py` 实测，30 个注册能力里
只有 10 个能直接驱动骨架。以下按真实类别标注，不虚报。

| 类别 | 数量 | 含义 | 成员 |
|---|---|---|---|
| **POSE** | 10 | 姿态函数 `(u,params)->{关节}`，可直接串时间线 | walk run jump kick throw catch crouch reach_grab climb carry_box |
| **ADDITIVE** | 4 | 增量 `{"J":delta}`，须叠加到基础姿态，**不可**当绝对姿态混合 | wave gaze_shift finger_tap page_flip |
| **PHYS** | 5 | 物理仿真，返回轨迹/标量，与角色动画不同层 | bounce rigid_body ramp stack pendulum |
| **AUX** | 11 | 求解器/群体函数/道具轨迹/状态名，不是姿态 | turn brake ball high5 contact crowd_collide multi_actor carry_prop prop_release box_release pass_ball |

分流由 `motion/capbridge.py` 完成（`init_capabilities()`）：工厂解包、签名适配、
含 `J` 的复合结构取关节、标量求解器强制归 AUX。
依据：ADAPT 的 blend node 分层、UE Layered Blend per Bone 的 additive/override 之分、
Box2D Lite 的物理层与动画层分离。

**注意**：`turn`（转身）与 `wave`（挥手）都不在 POSE 里——
`turn` 是角度求解器（出片走 `turn_torso`+`gait` 组合路径），`wave` 是增量。
`cafe.py` 能出 12 秒片是因为它绕过 `beat.Timeline` 手写 `pose_at`。

每项都带出处（写在 `@capability(name, source, group=...)` 的 `source` 参数里），
出处已登记的能力复用时不重搜；新能力或 STUB 转实现时必须先搜。

### 7.1 能力三态（可用 / 在研 / 未接入）

| 状态 | 数量 | 判定 | 成员 |
|---|---|---|---|
| **可用** | 10 | POSE，`(u,params)->{关节}`，时间线可直接调用 | walk run jump kick throw catch crouch reach_grab climb carry_box |
| **在研（STUB）** | 0 | 门检显式报 `缺能力: xxx`，未实现、不降级不伪造 | 曾缺：F30 ccd / F31 broadphase / F32 gravity_off / F33 friction / F34 overlap_resolve / E29 toppling，已全部补执行体 |
| **未接入** | 16 | 已注册但非姿态（ADDITIVE 4 / PHYS 5 / AUX 7），须经 `capbridge` 分流后才能参与合成 | wave gaze_shift finger_tap page_flip bounce rigid_body ramp stack pendulum turn brake ball high5 contact crowd_collide |

**不要用注册数衡量完成度**：注册 30 ≠ 可用 30。真实可驱动时间线的只有 10 个（33%）。

---

## 八、测试体系

39 项用例（A 基础动作 / B 抓取 / C 碰撞 / D 多主体 / E 复杂序列 / F 压力测试），
每项固定随机种子，出片后量判据。

判据全部带出处，不许拍阈值：

```
skate_cm_frame     脚底滑移（支撑期世界坐标后退速率）
penetration_m      手-物 / 物-物穿透
momentum_err       动量守恒
restitution_err    恢复系数 h·e^(2n)
jitter_px          帧间抖动
frame_jump_ratio   帧间跳变（测加速度有界，不受速度过零影响）
silhouette_gap_px  剪影纵向断裂
mask_iou           渲染掩膜 vs 胶囊几何真值
```

**当前**：PASS 39 / FAIL 0 / STUB 0 / ERROR 0（共 39 项，以 `run_all.py` 实测为准）。
STUB 是"没做"，不是"做错了"——不伪造；未实现能力在门检中显式报 `缺能力: xxx` 并计 STUB。

**判据出处已按红队质控逐条复核**（2026-10-06）：

| 判据 | 出处状态 |
|---|---|
| `penetration_m` 等 4 项 slop | 0.01 → **0.005**，对齐 Box2D v2.4.1 `b2_common.h:65` 的 `b2_linearSlop`；单点定义 `_SLOP` |
| `jitter_px` | 撤除 SMPTE 引用（SMPTE 的 jitter 是广电时钟概念，非像素抖动），改标工程自测值 |
| `pos_drift_m` | WorldCycle/CycleBench（港科大·武大·腾讯视频 AI 技术中心 2026-08）确为真实框架；阈值另标注为本工程自测标定 |
| `mask_iou` | 撤除 ResiHMR 贴牌（该论文主题为残肢人群 3D 人体网格恢复，与本判据无方法论关联），改 Jaccard 1912 + 自测标定 |
| `peak_rate_dps` | ISBS 2015 论文 Table 1 数值 414(90)°/s 真实可考；但补注样本为 U-13 青少年、任务为 5m 运球脚底半转身，仅取量级作参考上限，非生理极限 |

---

## 九、不含媒体

仓库只含代码与文档。生成的 mp4、索引图不计入交付，
按 `.gitignore` 排除，跑代码即可重新生成。
