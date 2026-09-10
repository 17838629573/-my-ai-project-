---
name: install
description: 把本工作流安装到用户项目（一键脚本或手动）。用户要求安装工作流时读，其他时候不读。
---

# 安装本工作流

优先跑一键脚本（无依赖、纯文件复制，自动识别工具）：
```sh
sh scripts/install.sh            # 在仓库目录本地安装
curl -s https://raw.githubusercontent.com/17838629573/-my-ai-project-/main/scripts/install.sh | sh   # 远程一键（地址见 README）
```

脚本按环境自动落位：CodeBuddy → `.codebuddy/skills/`；Trae → `.trae/skills/`；Claude Code → `.claude/skills/`；Cursor → `.cursor/rules/`；VS Code + Copilot → `.github/copilot-instructions.md`；识别不出 → 复制到 `./ai-workflow/` 并提示手动放置。`WORKFLOW.md` 一律放项目根目录。

脚本不可用（无网络 / 无 sh）时手动：把 `skills/` 复制到上表对应目录，`WORKFLOW.md` 放根目录；工具不支持 Skills → 直接把 `WORKFLOW.md` 贴给 AI，需要哪个动作再贴对应文件。

装完告知用户：以后提任何编程需求，AI 都先读 WORKFLOW.md 判断入口。
