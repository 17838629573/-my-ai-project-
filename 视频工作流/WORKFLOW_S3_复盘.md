

<!-- 从主干迁入：全量自检结果 -->
## 七、全量自检结果（run_batch.py 分批跑，沙盒超时故分批）

```
共 32 模块：PASS 16 / NO_SELFTEST 8 / NOFILE 2 / FAIL 6
```

| 状态 | 模块 | 含义 |
|---|---|---|
| **NO_SELFTEST** | chroma, subtitle, systems, loop_engine, film_assemble ~~render_v4~~（活跃） | **假 PASS 高危**：无 `__main__` 无 `self_check`，`python3 <mod>.py` 只 import 成功即退出，**零验证** |
| NOFILE | assets_tang/bg, assets_tang/char | deps.md 把【目录】当模块登记了 |
| FAIL | 6 个休眠 TTS 模块 | 缺第三方依赖（piper_phonemize 等），休眠层不影响主链 |

### 铁律26：无自检 = 不通过，零输出不算 PASS
`python3 <mod>.py` 零输出 + rc=0 ≠ 通过。
→ 每个模块必须有 `self_check()`；跑批器判定 `NO_SELFTEST` / `SUSPECT`（输出<30字符）。

### 铁律27：deps.md 只登记 .py 模块，目录不算模块
assets_tang/bg、assets_tang/char 是资产目录，不是代码模块。

### 铁律31：缺槽即报错，绝不静默填默认值

AI 漏填物性时，代码必须 raise，不能自己补个默认值继续跑。
**理由**：默认值会让错误结果看起来正常（静默失效，比报错危险得多）。

### 铁律32：文献判据外置，代码不内置知识

regime 阈值（如 Izawa 的 B\* 区间）是**文献知识**，会更新，由 AI 搜证后传入。
**铁证**：Izawa 2024 的 [1.72e-3, 4.06e-3] 属 **inverted flag**（下游端固定、倒着飘），
用于常规旗（迎风边固定）直接判错。已改 Connell & Yue 的 μ 判据。

### 铁律33：代码必须主动输出任务包给 AI（briefing）

**AI 会忘，代码不能忘。** 每次做视频，代码必须输出"AI 该做的事"清单，
不依赖 AI 自己记得流程。

```python
briefing(needs) -> {必搜物性, 必填槽位, 生图规格, 交付回代码}
briefing_text(b) -> 可读任务包（AI 照做即可）
```

**铁证**：本轮之前，AI 多次漏掉"先生成资产""先算几何"等前置步骤，
因为流程只存在于对话里，没有落到代码。

### 铁律34：动力学统一为 chain（受迫阻尼链）

凡"部分动、部分不动"的物体，**都是同一结构**，不各写一套：

```
驱动点(动) → 附属体(被动响应)
树干→枝条   头皮→发丝   肩腰→衣摆   幡身末端→垂带
```

四个公式（全代数式）：
```
ω_n=√(3EI/(m_eq·L³))   m_eq=33/140·m·L
r=ω_drive/ω_n          M=r²/√((1-r²)²+(2ζr)²)       φ=atan2(2ζr,1-r²)
A=M×A_drive
```
依据 Moore 2002 实测：枝条振荡频率≈**整树**自然频率，非枝条自身固有频率。

### 铁律35：冲击波 = 瞬态，不是稳态

冲击波是"突然的大风"——物理上成立，但解要换成瞬态包络：
```
A_env(t) = A_steady + (A_peak-A_steady)·exp(-ζ·ω_n·(t-t0))
```
**关键**：冲击过后回到 `A_steady`（原扰动量），**不是回到 0**。

### 铁律36：代码不知道本片有什么物体——只反问，不硬编码

**代码不该知道"幡旗/胡杨/玄奘"是什么。** 那是 AI 的活（语义分类）。
代码只做两件事：

1. `survey()` —— 问 AI：本片有几个动物、静物？逐个分类
2. 每建一个美术资源回来 → **反问：这物件上哪些相对动、哪些相对静？**

三类角色（AI 填）：
```
anchor  绝对不动：固定端/基座，位移恒 0（杆、树干基部）
driven  主动运动：受外部驱动源直接作用（风/步频/冲击）
passive 被动响应：挂在上游被带动（衣摆、发丝、枝条）
```
驱动源：`wind` / `gait` / `impulse` / `none`

**组装规则**：driven 是链首，passive 依次挂后，anchor 不进动力学。
有 passive → `chain` 族；只有 driven → `cantilever`。

**铁证**：之前 briefing 硬编码"幡旗/垂带/胡杨"当演示——把 AI 的活抢了。
现自检第 21 项直接扫描源码逻辑区，禁出现任何具体物体名。

### 铁律37：示例要硬编码，提问不硬编码

**提问时**：代码不知道本片有什么物体，`survey()`/`inventory()` 只反问。
**示例区**：必须硬编码，让**其他 AI 拿到就有简陋心智模型**，能分辨动静。

```python

<!-- 从主干迁入：NO_SELFTEST 清零 -->
## 九、NO_SELFTEST 清零（4 个模块补自检，各抓出真 bug）

| 模块 | 自检项 | 抓出的 bug |
|---|---|---|
| **loop_engine** | 6 项 | `register()` 后不清 `_order` 缓存 → **新注册的系统永不执行**（证伪：新系统 0 次调用）；`run(fps=60)` 写死 |
| **film_assemble** | 5 项 | `render_one(fps=60)` 写死；第 4 项原为空转（broken 资产本不在输出域）→ 改对照实验后才真正生效（ECU: hands->stand） |
| **chroma** | 5 项 | `chroma_key` / `trim_alpha` 实际返回 `(bgra, meta)` 二元组，旧调用方未解包 |
| **subtitle** | 5 项 | `check_timing` 写死 **24fps**，而输出是 60fps → 字幕时长判据错位 2.5 倍 |

### 自检自身的假 PASS（第三次遇到）
```
loop_engine 第4项"禁用系统零调用"、film_assemble 第4项"broken过滤"
→ 都是"永远成立"的空转检查，显示 PASS 但什么都没查
→ 必须做证伪测试：故意注入违规，看检查是否报错
```

### chroma 形状检查的诚实边界
```
历史 bug 资产宽高比 0.264，落在合理区间 0.02~50 内
→ 纯几何拦不住（它就是一面细长幡旗的形状）
→ 改为：只拦极端异常 + 输出主色 [37,52,118] 供 AI 复核（铁律18：形态归 AI）
```

### 最终状态
```
活跃 16 模块：全部 PASS，NO_SELFTEST = 0
门禁 validate PASS
assets_tang/bg、assets_tang/char 已从 deps.md 移除（铁律27：目录不算模块）
```

### 铁律46 播放端必须消费代码算出的时长，禁自己线性取帧
- 铁证：solver 算了 frame_durations，播放端 systems 却用 `(i/fps)/period*n`
  线性取帧 -> 改了 solver 等于没改（断链）。证伪：非均匀时长下有 169 个
  时刻本应取到不同帧，实际全同。
- 边界由索引前缀和算出，禁累加舍入（业界：Do not accumulate rounded
  timestamps；实测 N=35 时前缀和与累加差 <1e-9）。
- 均匀是默认；**循环闭合不住 = 缺过渡姿态，应补生成姿态**，
  不是改时长掩盖，更不是复制末帧（duplicate endpoint 会让每圈顿一下）。

### 铁律47：图集每格必须「容纳 + 留边 + 同尺度」，缺一即报错
- 判据：`max_fill_w/h`=0.80、`min_fill`=0.25、`margin_px`=8、`centroid_policy` 必填。
- 来源：lobehub agent-sprite-forge / SummerEngine STRICT atlas / AutoSprite / Seele AI。
- 抓的是历史 bug：`banner_f33` 前景占比 0.6% 却放行。
- `centroid_policy`：角色用 `planted`（动姿态不动位置），摆动件用 `free`
  （质心本就该动）——这是语义判断，归 AI（铁律18）。

### 铁律48：先生 8 格探针，验过一致性才升级到全量帧数
- `n_probe = min(8, N)`；`probe_check` 验面积/尺度/配色/足迹 4 项，任一 FAIL 不许升级。
- 来源：元域费曼"先 8 格 4×2 验脸/衣服/配色再升 16 格，第 7 格起人物会变异"。
- 阈值 `area_spread/scale_spread/color_maxdist` = 0.35/0.25/60，可被 spec 覆盖（铁律32）。

### 铁律49：播放帧数（物理定）≠ 生成帧数（复用定），两个数字禁混用
- 播放帧数 `frames` 由周期 T 定；生成张数 `gen_n` 由复用规划定。
- 抓的历史 bug：137 帧全量生成，模型扛不住一致性，且大量帧几何重复。

### 铁律50：对称复用前必须量化对称残差，超阈值禁止镜像
- 判据 `x[i]+x[i+half]` 的残差 / 峰峰值 ≤ `mirror_residual_max`（默认 0.05）。
- 恒定偏置可被 offset 完整补偿（`x[i]+x[i+half]=2·offset`）；二次谐波补不掉，必须拒。

### 铁律51：镜像必须指定锚点，且补 offset 修正
- 无锚点翻转会导致主体滑移（业界硬约束）。锚点缺失 → 复用降级为询问，不静默全量。

### 铁律52：复用方案必须输出并交 AI 确认，禁代码自作主张
- 输出帧数时**必须**同时输出 `ask_ai` 清单：左右是否真只是方向反了、
  有无不可翻转特征（文字/单侧配饰/光向/发型分缝）、offset 是否可接受。

### 铁律53：物体分层生成，摆动由 additive 叠加，禁整块重新生图
- `base`（主体结构，只生一次）+ `overlay`（发丝/衣摆，挂 anchor + dx/dy/scale）。
- 左右走共用同一套主体骨架，方向差异 = 镜像；摆动差异 = `additive_offset` 逐点叠加。
- 来源：SummerEngine Modular Atlas / Terraria Body-Head-Legs 分离合成 /
  Unity Playables 三层 / mocaponline additive offset curve（5 base → 50 NPC）。

### 铁律54：视频不做 16 帧封顶，素材张数 = round(T·FPS)
- `mat_frames = N`（FPS=60），**禁止 `min(N, 16)`**。16 格是游戏值
  （团结引擎 4×4 定式），不是视频值。
- 来源：Singular.live 8×8=64 格 @30fps、16×16=256 格 @60fps；
  SpritePilot 10-12fps 是**游戏**足够值。
- 铁证：`N=35 → mat_frames=min(35,16)=16 → playrate=2.19`
  = 27fps 素材硬撑 60fps，每格撑 2.19 帧，必然顿。

### 铁律55：多帧必须合图，禁逐帧单图
- 生成 N 帧 ≠ 生 N 张单图。合图是帧间一致性的**结构保障**：
  同一张图内模型只做一次构图决策，跨图则从零重新决定。
- 来源：团结引擎「参考图显著减少帧间漂移」/ FrameSprite
  「一致性=减少模型每帧要重新决定的东西」/ Sorceress 参考图+锁 seed 12 帧不漂。

### 铁律56：单张图集格数上限由 AI 声明，默认 16
- 一致性上限是**模型能力**不是代码常量。默认 `max_cells=16`
  （GPT-Image「先 8 帧验稳定再扩 16」），AI 可按所用模型上调。
- 超出 → 拆多张，**所有图集共用同一张身份参考图**（铁律55）。
- 每张容量 = min(max_cells, 2048 上限反推)，**不许为了少拆把格压糊**
  （自检：每格 ≥128px）。

### 铁律57：长条物体用 strip，禁塞方形格
- 长宽比 > 2 → 布局走 `1×N` strip + custom wide cells，不用 4×4 方形格。
- 来源：lobehub sprite-forge「platforms/walls/gates/long hazards
  use 1×3/1×4 strips, custom wide cells」。

### 铁律40（修订）：一物体 = 一组图集，共用同一张身份参考图
- 原表述「一物体一张图集」与铁律54 冲突（35 帧装不进 16 格）。
- 修订：一致性保障从「同一张图」改为「**同一张身份参考图**」。
  拆多张是允许的，前提是参考图锁定。

### 铁律58：合成必须 Porter-Duff Over，严格从远到近
- `C_out = C_s·α_s + C_d·(1-α_s)`，预乘 alpha、线性空间。
- alpha 混合**非交换**（实测 maxdiff=54），顺序即结果；多层按 depth 升序（远→近）。

### 铁律59：AI 资产禁以色键为主抠像
- `chroma` / `flood_key` 不得作为主抠像；走 matte（straight alpha /
  difference matting / RVM）。
- 来源：AI 扩散模型把背景色扩散进边缘，固定阈值抠不净。

### 铁律60：背景可控时优先 Clean Plate + Difference Matting
- clean plate 由代码生成并登记（`build_plate`），不得 AI 口头指定。
- 来源：Aximmetry 工业级管线，可保留接触阴影与半透明。

### 铁律61：镜头位移必须显式声明 intent
- `travel`（横穿，root motion）或 `treadmill`（跟拍，in-place + 背景滚动）。
- 未声明**报错**，不默认。来源：Unity Root Motion 官方定义。

### 铁律62：前景必须带接触阴影
- 由 alpha 腐蚀 + 位移生成（`contact_shadow`），否则前景"浮空"，禁止交付。

| 81-85 | 提示词按族取模板禁按物体写死；模板区零物体名；姿态走结构性量；未知族报错 |
