---
name: ai-coding-workflow
description: AI编程工作流 —— 7步主干流程自动执行编程任务，9条铁律 + 5道代码执行门禁，硬规则不可跳过
---

# AI编程工作流

## 概述
本技能将完整的 AI 编程工作流封装为可复用能力。加载后自动按以下流程执行：
**接需求 → 拆模块(用户勾选) → 写模块(并行) → 集成 → 测试找bug → 汇报 → 交付**

核心硬规则（铁律5/8/9、断点WORKLOG、判定依据）已固化为 `scripts/enforce.py` 代码执行，不可跳过、不可绕过。

## 使用流程

### 1. 加载后立即常驻 `WORKFLOW.md`
`WORKFLOW.md` 是主干流程，包含：
- **9条铁律**：所有步骤生效的强制纪律
- **5道执行门禁**：代码强制的硬规则
- **断点续作**：每步过门写 WORKLOG，下次可"继续上次"
- **入口判断**：7种入口场景，自动定位起始步骤
- **7步主干**：逐步骤执行

### 2. 按入口判断定位起始步骤
`WORKFLOW.md`「入口判断」节覆盖：从零做 / 只测试找bug / 只改一段代码 / 拆模块重构 / 打安装包 / 安装工作流 / 继续上次 / 认不出则问用户

### 3. 逐步骤执行
每步先读对应 `skills/*/SKILL.md`，执行完回到 WORKFLOW.md 继续下一步。

### 4. 自动触发执行门禁
每步自动调用 `scripts/enforce.py`，包括：
- `validate` — 入口先全局自检
- `gate pre-step N` / `gate post-step N` — 每步前后门禁
- `check-write <file>` — 写文件前红黄区检查
- `check-auth <track>` — 授权前检查
- `check-iron-law WORKFLOW.md` — 铁律保护
- `check-evidence <code> <desc>` — 判定依据核验

## 输入
用户提交的编程任务，格式不限（自然语言描述 / 代码片段 / 需求文档 / 项目链接 / GitHub 仓库）

## 输出产物
- ✅ 可运行的代码（按模块组织）
- ✅ `WORKLOG.md`（断点记录，支持下回续作）
- ✅ 验证声明（quick-check / full-check / 测试报告）
- ✅ `deps.md` 全局契约图（供后续维护定位）
- ✅ `.track.md` 授权跟踪（授权过的事不重复问）
- ✅ 交付物（安装包 / 可访问链接 / README）

## 核心文件清单

| 文件 | 角色 |
|------|------|
| `WORKFLOW.md` | **主干流程**（常驻上下文） |
| `scripts/enforce.py` | **执行门禁**（自动触发，不可跳过） |
| `scripts/dep_check.py` | 依赖图验证（循环/孤立/不一致） |
| `scripts/install.sh` | 一键安装脚本 |
| `skills/check/SKILL.md` | 静态检查（quick-check / full-check） |
| `skills/write/SKILL.md` | 写模块（含TDD分支 + 子agent并行） |
| `skills/track/SKILL.md` | 授权跟踪（临时/半永久90天/永久） |
| `skills/split/SKILL.md` | 拆模块（架构师层级递归） |
| `skills/test/SKILL.md` | 测试找bug（三层扫描） |
| `skills/fix/SKILL.md` | 精准修改（一次修同类） |
| `skills/halt/SKILL.md` | 卡住协议（失败/超时/循环） |
| `skills/verify/SKILL.md` | 验证声明（5项完整） |
| `skills/architect/SKILL.md` | 架构师层级定义 |
| `skills/apk/SKILL.md` | APK打包 |
| `skills/install/SKILL.md` | 安装本工作流 |

## 铁律（所有步骤生效）

1. **判定靠命令输出**：测试通过 / grep 为 0 / 退出码 0，禁止说"应该没问题"
2. **只动必要范围**：不"顺手优化"无关文件；全量改须用户明说
3. **每步留产物**：确认文本 / 检查结果 / 可运行文件
4. **遇技术难题先搜方案**：不自造易碎方案，报用户批准
5. **红黄区保护**：红区（.env/auth/secrets/deploy/CI/依赖文件）禁自动改；黄区（config/routes/models/入口）改前告知
6. **失败/卡住 → halt**：读 `skills/halt/SKILL.md` 写 ERRORS.md，固化/删除权归用户
7. **估耗时 ×3**：有外部 I/O 的操作；禁止悬空态
8. **授权先查 track**：.track.md 存在且未过期 = 有效，否则重新询问
9. **铁律不可覆盖**：不可逆操作先确认，确认后落 track

## 执行门禁（代码强制执行）

以下硬规则已固化为 `scripts/enforce.py`，不可跳过、不可绕过：

| 门禁 | 对应铁律 | 触发时机 | 阻断条件 |
|------|---------|---------|---------|
| `check-write` | 铁律5 | 写文件前 | 红区文件无授权 → 阻断 |
| `check-auth` | 铁律8 | 授权操作前 | .track.md 不存在/过期/格式错 → 阻断 |
| `check-iron-law` | 铁律9 | full-check 时 | WORKFLOW.md 铁律被删除或 <9条 → 阻断 |
| `gate post-step` | 断点强制 | 每步完成后 | WORKLOG 无该步记录 → 阻断 |
| `check-evidence` | 铁律1 | 每步过门前 | 退出码非整数或无数值依据 → 阻断 |
| `validate` | 全局自检 | 入口/全检 | 铁律/dep_check/门禁自身缺失 → 阻断 |

## 运行时产物（不入库，跟项目走）

- `.track.md` — 授权跟踪（`.gitignore` 已排除）
- `deps.md` — 全局契约图（层间 `# L0`/`# L1` 标注）
- `WORKLOG.md` — 断点记录（enforce.py 自动校验）
- `ERRORS.md` — 失败记录（halt 触发，固化权归用户）