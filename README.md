# AI 编程工作流 · 通用模块化版

给 AI 编程助手用的工作流。**常驻一份主干，动作按需调用**——任何时刻 AI 上下文里只有「主干 + 当前步骤文件 + 正在用的那一个通用模块」，单文件 ≤2.3KB（主干 WORKFLOW 约 3.8KB），不会上下文爆炸。

## 核心机制

- **7 步主干**：接需求 → 拆模块（用户勾选）→ 写模块（多模块子 agent 并行）→ 集成 → 测试找 bug → 汇报 → 交付；只做其中一段时入口直接跳到对应步骤。
- **规模判断 + 架构师层级递归**：接需求时先问项目规模——大型项目由用户定拆几层（= 架构师层级）；不确定可"拆到不能再拆"；小项目单层拆完直接写。递归时总架构师定顶层 → 次级架构师逐层拆 → 代码 AI 写实现；上层对下层只读、只改自己契约；每层产出自己的契约图，全局契约图（`deps.md`）输出供以后改架构定位。
- **授权跟踪（.track.md）**：权限 / 决策授权分三类——临时（不落文件、用完即忘）、半永久（默认 90 天，到期重问，用户说不要就删条目）、永久（永不过期）；用户拒绝 = 临时，下次重问。**文件存在 = 有效，文件不存在 = 无效**，无额外标记位；授权过的事不重复问。
- **判定外置**：不靠 AI 嘴上说，靠命令输出（测试通过 / grep 为 0 / 退出码 0）。

## 文件清单（18 份产物）

**根目录（常驻）**
| 文件 | 用途 |
|---|---|
| `WORKFLOW.md` | 铁律 9 条 + 断点续作 + 入口判断 + 7 步主干（常驻） |
| `ERRORS.md` | 失败与边界记录，halt 触发时写入，固化 / 删除权归用户 |
| `README.md` | 本文件（门面与说明） |
| `LICENSE` | MIT |
| `.gitignore` | 标配；`*.track.md` 默认本地化不入库（授权记忆跟人走） |

**通用模块（被 2+ 步骤复用，点名才加载）**
| 文件 | 触发条件 |
|---|---|
| `skills/track/` | 需要权限 / 决策授权、或可能重复询问前 |
| `skills/architect/` | 递归拆模块时：定义架构师层级（总架构师→次级架构师→代码 AI）与层间纪律、契约图归属 |
| `skills/verify/` | 写完模块 / 集成后 / 测完 / 交付前出验证声明 |
| `skills/fix/` | 修 bug、用户要求改代码 |
| `skills/check/` | 每写完一个模块 quick-check、集成后 full-check（含依赖图验证） |
| `skills/halt/` | 任何一步遇阻：工具缺失、超时、搜索无果、循环返工、要求矛盾 |

**步骤文件（走到才读）**
| 文件 | 对应步骤 |
|---|---|
| `skills/split/` | 步骤 2：架构师层级递归拆模块 + 依赖图 + 契约 + 全局契约图，问 TDD |
| `skills/write/` | 步骤 3：写模块（子 agent 并行 / TDD 分支） |
| `skills/test/` | 步骤 5：测试找 bug |
| `skills/apk/` | 步骤 7：打 APK |
| `skills/install/` | 用户要求安装本工作流时 |

**脚本（无依赖）**
| 文件 | 用途 |
|---|---|
| `scripts/dep_check.py` | 依赖图验证：纯标准库，查循环依赖 / 孤立模块 / 图与代码一致性；支持括号注释与 `[runtime]` 运行时契约；有 error 退出码 1（halt 问用户） |
| `scripts/enforce.py` | **执行门禁**：将不可绕过的硬规则（铁律5/8/9、WORKLOG断点、判定依据）固化为代码执行。每步过门自动触发，失败阻断流程。详见 WORKFLOW.md「执行门禁」节 |
| `scripts/install.sh` | 一键安装：自动识别工具环境复制文件，纯复制无编译 |

`.track.md` 文件随授权过程生成（跟随步骤文件同名，如 `skills/split.track.md`），不随仓库分发。`deps.md` 是拆分时产出的全局契约图（各架构师只维护自己那层，层间 `# L0`/`# L1` 标注），供 `dep_check.py` 校验、也供以后改架构定位。

## 安装

一键（仓库目录本地）：
```sh
sh scripts/install.sh [目标项目目录]
```
远程（传上 GitHub 后替换地址）：
```sh
curl -s https://raw.githubusercontent.com/17838629573/-my-ai-project-/main/scripts/install.sh | sh
```

自动识别落位：CodeBuddy → `.codebuddy/skills/`；Trae → `.trae/skills/`；Claude Code → `.claude/skills/`；Cursor → `.cursor/rules/`；VS Code + Copilot → `.github/copilot-instructions.md`；识别不出 → 复制到 `./ai-workflow/` 并提示手动放置。`WORKFLOW.md` 一律放项目根目录。

不支持 Skills 的工具：把 `WORKFLOW.md` 贴给 AI，走到哪步需要哪个动作，再贴对应文件。

## 边界
本工作流核心硬规则（铁律5/8/9、断点WORKLOG、判定依据）已由 `scripts/enforce.py` 固化为代码执行，不可跳过。弹性规则（铁律2/3/4/6/7）仍为提示词纪律。门禁检查不通过 → 流程阻断，读 `skills/halt/SKILL.md` 停。

License: MIT
