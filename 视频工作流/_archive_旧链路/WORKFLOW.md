# 视频工作流 v4（主干·常驻·结构化为唯一格式）

## 0 路由（改代码只需这 4 步，其余不进上下文）
```
① WORKFLOW.md（本文件）
② contracts/<模块>.md       定位层：does/api/const/up/down/rule
③ 按末尾指针取详细层
     fact: detail/<m>.md     机器翻译的事实（行号/签名/调用/常量）
     why : IMPROVE_<m>.md    人工写的依据/坑/意图（缺则标「待补」）
④ 该文件本身 + IMPROVE_<m>.md 的 trap 段
```
改动史在 `notes/<模块>.md`，**不进常驻上下文**（铁律22 按需拉取）。

## 1 改后必跑（勿凭印象）
```
python3 contract_gen.py <m>    # 事实层随代码重生
python3 impact.py <m>          # 列出下游
python3 impact.py <m> --check  # 实跑下游自检（退出码 1 即阻断）
python3 gate_doc.py            # 文档体积门禁
```

## 2 Stage（含按需拉取闭环）
| S | 内容 | 过门 |
|---|---|---|
| 0 | 定方案（搜行业标准） | 方案+来源落盘 |
| 1 | 接需求 | 叙事文本落盘 |
| 2 | 拆模块 | `gate post-stage 2` |
| 3 | 备资产 | `check-assets` PASS（主配角硬阻断）+ 可动件须循环序列帧 |
| 3.5 | **按需拉取**（铁律22） | 见下闭环 |
| 4 | 装配 | 解析表落盘 |
| 5 | 渲染 | 每段 mp4 |
| 6 | 校验 | 抽帧检测报告 |
| 7 | 交付 | 成片 + WORKLOG |

Stage 3.5 闭环（**一次只处理一个物体**）
```
① 代码提问：需要 X，物性如下（尺寸/质量/约束）
② AI 搜公式 → 算无量纲数 → 回代码
③ 代码校验硬约束 → 提问「需参考图集」
④ AI 搜多张参考 → 合成图集（24 帧网格）
⑤ AI 搜真实尺寸 → 填 scene_spec → 代码校验 px/m 一致性
⑥ 通过 → 图生图 → 序列帧入库
```

## 3 资产分类
```
能动 → actor（人/动物/植物/门/旗/水/火），必须可驱动
动不了 → 背景（城池/房屋/地形/远山），静态整图
```
背景禁烘焙可动件。驱动不了 = HALT，禁降级禁占位。

## 4 AI 填 / 代码算（禁越界）
```
AI 填：mass / kind / cd / b_vogel / surface / 真实尺寸（物性，可搜，标源）
代码算：area / force / accel / displacement / px_per_m（派生量，禁手填）
```
三档：有据（必搜+标源）｜估算（按 kind 默认）｜N/A（不适用，非漏填）

## 5 halt 协议
报四项：卡在哪步 / 已试什么 / 缺什么 / 四个选项
触发：下载失败 3 源｜同 bug 修 3 轮不过｜单段渲染超预估 3 倍

## 6 参数声明（param_decl / cloth_aero）
- T99 代码缺参数 → `param_decl.require()` 抛 `AskAI` 反问。禁默算、禁静默兜底
- T100 落盘参数须有 `source`（文献/标准/厂商文档），无来源拒绝
- T101 须带 `range` 合理区间，越界拒绝；`value` 须在区间内

## 7 门禁盲区（待补，勿重复踩）
| 盲区 | 现象 | 状态 |
|---|---|---|
| import 可达性 | deps 已声明、validate PASS，但没写 import → NameError | 待补 |
| 剪辑规则不阻断 | 镜7→8 同景别同角度跳切，只警告仍渲染 | 待补 |
| 叶子模块漏登记 | 无人 import，validate 查不出 | `contract_gen` 已出 down 字段 |
| 证据可证伪性 | 聚合指标冒充因果证据 | 靠铁律2 |
| 资产形状合理性 | 图存在但形状不对 | 待补 |

## 8 指针
- 铁律全文：`WORKFLOW_R0_铁律全文.md`
- 契约索引：`contracts/_INDEX.md`（L→M→S）
- 事实层：`detail/` | 依据层：`IMPROVE_*.md` | 影响：`impact.py`
