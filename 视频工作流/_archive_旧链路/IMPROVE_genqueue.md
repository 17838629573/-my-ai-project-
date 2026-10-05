# IMPROVE_genqueue —— 改 genqueue.py 前必读

> 契约见 contracts/genqueue.md。本文件记真坑、待办与业界依据。
> 契约只写「依赖/被依赖 + 改前必读指针」，细节与经验一律放这里。

## 一、业界依据（真联网搜证，非推测）

| 结论 | 来源 |
|---|---|
| 批量生图会把物体A特征混进B（灰猫+红狗→红灰猫；红花瓶+橡皮鸭→混合体） | SIGGRAPH Asia 2025（BLIP-Diffusion / KOSMOS-G） |
| "Batch-level generic prompts are the biggest source of cross-contamination" | agency-multi-brand-pack |
| 身份参考图必须逐物体独立，不对着上一个资产做 | 业界 sprite 管线 |
| ONE PER VIEW；bad seed poisons whole row | office-sprite-pipeline |
| 模板必须按作用域隔离 | outlierkit |
| 先串行验通单物体，再复制到其他物体 | Sprite Pipeline Playbook |
| Divide / Conquer / Combine 防多主体属性泄漏 | MIGC |

## 二、踩过的坑（改前必看，别重犯）

### 坑1 自检用的 solved 是我手填的 → 违反铁律68
第一次自检第6项 FAIL：`structural_pose` 要求姿态必须来自代码计算。
修法：自检里 import pose，`PS.solve(s,"walk",t)` 真算 joint 坐标再填 solved。
**自检数据也不能手编，否则测的是假数据。**

### 坑2 biped 必填「关节角」被我删掉
删了就报缺槽。正确修法：从 solved 推导字符串，不是手填角度。
```python
params["关节角"] = "，".join(f"{k}={v}" for k,v in solved.items())
```

### 坑3 GenQueueError 从未定义（真 bug）
第71行 raise 它，但类没定义 → 触发时 NameError 而非清晰报错。
已补 `class GenQueueError(ValueError)`：**继承 ValueError 是为了兼容既有
`except ValueError` 的调用方**，改成别的基类会让自检8/9静默失效。

### 坑4 段内 {占位符} 不在必填里 → 渲染静默留空（真 bug）
自检13 抓出：biped/quadruped/vegetation 用了 `{构图占比}`、cloth 用了
`{物理点}`，都没进必填。已补进必填。
**教训：模板是白名单，未声明槽会被静默丢弃；段占位符必须 ⊆ 必填。**

### 坑5 污染注入的证伪一度空转
第一次把污染塞进未声明槽「服饰」→ 被白名单丢弃 → 检测器测不到 → 假 PASS。
必须注入到**已声明槽**（如「风格」）才有效。
**这已是第 8 次「自检自身空转」，每次新增检测器都要配注入证伪。**

### 坑6 证伪14 写法错误
缺族时 `briefing` 内部 `plan` 直接抛 DriverError，不会返回字符串。
我原写 `b2 = briefing(...)` 再查文本 → 直接崩。
正确：用 try/except 断言"必须抛错"。**正确行为≠能拿到返回值。**

## 三、待办（程序做不到，须 AI 或后续模块补）

1. `build_video.py` **仍未接 genqueue**（也未接 prompt_tpl）——
   不接则"一次一物体"纪律在真实生图流程里不生效。
2. quadruped / rigid 两族只登记了族，**驱动器未实现**：
   四足腿相位交错、车轮自转，代码目前算不出来。
3. 生图工具能否传 control map 未确认；未确认前禁把骨架图当参考图（铁律78）。
4. `solver.py` 1172 行、`systems.py` 669 行、`solver_check.py` 612 行仍超 400 行软上限。

## 四、文件长度现状（活跃层 top）

| 行 | 文件 | 处置 |
|---|---|---|
| 1172 | solver.py | 已切 survey/check，剩余物理+骨架+图集，**耦合紧未切** |
| 669 | systems.py | 职责单一，暂不切 |
| 612 | solver_check.py | 已独立，属自检体量 |
| 250 | genqueue.py | 本轮**新建独立模块**，未塞进 driver |
| 297 | driver.py | — |
| 296 | prompt_tpl.py | — |

---

---

---
## Y-Statement（gen:why_apply 勿手改）

meta: genqueue
处境: 生图队列：按物体逐个生成身份参考与序列帧的排队模块（IMPROVE_genqueue.md:67 新建独立模块）
问题: 自检数据也不能手编，否则测的是假数据。**
决定: 身份参考图必须逐物体独立，不对着上一个资产做 | 业界 sprite 管线 |
否决方案: 第71行 raise 它，但类没定义 → 触发时 NameError 而非清晰报错。
收益: 已补 `class GenQueueError(ValueError)`：**继承 ValueError 是为了兼容既有
代价: 2. quadruped / rigid 两族只登记了族，**驱动器未实现**：
依据出处: > 契约见 contracts/genqueue.md。本文件记真坑、待办与业界依据。
