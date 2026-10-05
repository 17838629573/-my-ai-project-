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

## 三、规模（2026-10-05 实测）

```
活跃文件  49 个 / 10,264 行   ← 真正参与运行
孤立文件  47 个               ← 其中根目录 36 个 py（8,029 行）为旧链路遗留
能力表    17 项
测试      PASS 21 / FAIL 0 / STUB 14 / ERROR 0（共 35 项）
仓库体积  7.4 MB（已剔除全部视频产物）
```

活跃/孤立的判定用 `_proc/tools/reach.py`，从 5 个入口做可达性分析，不是眼估。

---

## 四、怎么跑

干净环境（无需设 PYTHONPATH）：

```bash
python3 _proc/beat_demo.py      # 走 beat 时间线出演示片
python3 _proc/motion/cafe.py    # 咖啡馆 12 秒（四段动作）
python3 _proc/tests/run_all.py  # 跑 35 项测试门检
python3 _proc/check.py          # 架构契约扫描
```

每个 `.py` 顶部有 `__file__` 锚定的自举块，自动上溯定位 `_proc`，直接跑即可。

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

## 七、已实现能力（17 项）

```
walk  run  brake  jump  turn  crouch  wave  gaze_shift
finger_tap  page_flip  kick  throw  catch  reach_grab
carry_prop  prop_release  box_release  carry_box
```

每项都带出处（写在 `@capability(name, source, group=...)` 的 `source` 参数里），
出处已登记的能力复用时不重搜；新能力或 STUB 转实现时必须先搜。

---

## 八、测试体系

35 项用例（A 基础动作 / B 抓取 / C 碰撞 / D 多主体 / E 复杂序列 / F 压力测试），
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

**当前**：PASS 21，FAIL 0。STUB 14 是"没做"，不是"做错了"——不伪造。

---

## 九、不含媒体

仓库只含代码与文档。生成的 mp4、索引图不计入交付，
按 `.gitignore` 排除，跑代码即可重新生成。
