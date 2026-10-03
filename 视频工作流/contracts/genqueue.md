# genqueue · 生图任务队列契约

## 依赖 / 被依赖
- 依赖: `prompt_tpl`（按族组装提示词）, `driver`（族判定）
- 被依赖: `build_video`（取任务）, `driver`（提醒里引用）

## 改前必读
`IMPROVE_genqueue.md` ← 业界依据 + 踩过的坑 + 待办

## 铁律

**81 一次只放行一个物体的一种图。**
队列同一时刻只暴露 1 个任务；未 `accept` 不放行下一个。
依据：agency-multi-brand-pack 原话 *"Batch-level generic prompts are the biggest
source of cross-contamination"*——批量级通用提示词是跨污染最大来源。

**82 提示词按族模板组装，只含该物体槽值，禁跨物体复用。**
依据：SIGGRAPH Asia 2025 实测，多物体同批会让 BLIP-Diffusion 产出
"reddish gray cat"（灰猫+红狗→红灰猫），KOSMOS-G 产出
"red vase + rubber duck" 的混合体。outlierkit: *"模板必须按作用域隔离，
共享模板会重新引入混淆"*。

**83 不同实例（不同人物）是不同任务，禁共用提示词。**
依据：office-sprite-pipeline *"ONE PER VIEW"*，identity seed 逐角色独立，
*"A bad seed poisons its whole row"*。

**84 一次一个动作意图。**
依据：Sprite Pipeline Playbook *"Run one action at a time，avoid mixing
multiple motion intentions in a single iteration"*。
稳定块（身份+风格+配色）/ 可变块（本次动作参数）。

**85 无骨骼族不产生序列帧任务。**
vegetation/rigid 只出单张，见 driver 族表。

## 接口

```python
plan(objects)                 -> {"tasks":[...], "n":int}
build_prompt(task)            -> 单条提示词（只含该物体槽）
next_task(q, done)            -> 1 个任务 or None（未验收不放行）
accept(q, tid, report) / reject(q, tid, reason)
```
