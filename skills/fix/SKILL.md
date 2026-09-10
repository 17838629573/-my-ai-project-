---
name: fix
description: 精准修改。测试发现 bug、用户要求改代码时调用，禁止全量扫描重写；其他时候不读。
---

# 精准修改

1. **定位**：找到具体 文件:行:函数，只标出要改的范围；范围外不读不碰。定位不了 → 问用户，不许"先全扫一遍"。
2. **最小改动**：只改出问题的位置。
3. **查旧依赖**：grep 被改函数 / 变量 / 接口的所有引用点，确认调用方不被破坏；不兼容就同步改（须告知用户）。
4. **查新依赖**：新增的 import / 调用必须存在且路径正确。
5. **清扫**：grep 旧函数名 / 旧变量名，确认无死代码、无未使用 import。
6. 改完 → 读 `skills/verify/SKILL.md` 回归。

## git 节奏（安全网）
- 改前：工作区干净，或先 `git commit -m "checkpoint: <简述>"` 落检查点。
- 改完：自动 commit（一个逻辑变更一提交），便于回滚。
- 禁止：未提交状态下连续大改导致无法回退。

> 示例：改 login.py:42 的 token 过期逻辑——改前 checkpoint commit；只改第 42 行；grep issue_token 确认调用方签名未变；改完 commit。

红区文件无批准不改（铁律 5）；已批准过同类操作先查 `skills/fix.track.md`（见 `skills/track/SKILL.md`）；修复循环约超 5 轮 → 读 `skills/halt/SKILL.md`。
