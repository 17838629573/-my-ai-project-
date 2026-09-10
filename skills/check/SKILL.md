---
name: check
description: 静态检查。写模块步骤每写完一个模块跑 quick-check，集成后跑 full-check（含依赖图验证）；其他时候不读。
---

# 代码检查

## quick-check（单个模块写完）
1. 语法检查（按语言选：`py_compile` / `tsc --noEmit` / …）
2. 注释标签齐全（用途 / 参数 / 返回）
3. 高危扫描：未定义变量、未处理异常、硬编码密钥

过门：无错误且高危 = 0，才允许写下一个模块。

## full-check（集成后）
1. **执行门禁自检**：`python3 scripts/enforce.py validate` → 硬规则完整性（铁律存在 / dep_check 存在 / 门禁自身正常）
2. quick-check 全部项
3. 死代码、未使用 import、重复实现
4. 函数签名与契约块一致
5. **依赖图验证**：跑 `python3 scripts/dep_check.py`（根目录运行，读 `deps.md` 并扫代码 import），检测：循环依赖、孤立模块（无人用也不依赖人）、依赖图与代码实际 import 不一致。
   - 退出码 0 → 通过；报问题 → 读 `skills/halt/SKILL.md` 停下问用户（补图 / 改代码 / 确认例外），不擅自改依赖结构。
6. **铁律保护验证**：`python3 scripts/enforce.py check-iron-law WORKFLOW.md` → 铁律章节被删除或缩减 → 阻断并 halt。

过门：通过，或仅剩中低危问题（逐项列明）。

## 对抗评审（可选，到这一步问用户，不预设）
- 用户选"是"：派一个干净上下文、没参与写代码的子 agent，只给它「契约块 + 本次 diff」挑毛病，只回传 1-2K 摘要；主流程不混入评审上下文。
- 用户选"否"：主 agent 自行 full-check。
