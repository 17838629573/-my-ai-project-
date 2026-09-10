#!/bin/sh
# 一键安装本工作流到当前项目：自动识别 AI 工具环境，纯文件复制，无依赖。
# 用法：在仓库目录执行  sh scripts/install.sh [目标项目目录]
set -e

SRC="$(cd "$(dirname "$0")/.." && pwd)"
DEST="${1:-.}"
DEST="$(cd "$DEST" 2>/dev/null && pwd)" || { echo "目标目录不存在: $1"; exit 1; }
cd "$DEST" || { echo "目标目录不存在: $DEST"; exit 1; }

cp_workflow() { cp "$SRC/WORKFLOW.md" "$DEST/WORKFLOW.md" 2>/dev/null || true; }

echo "检测环境: $DEST"
if [ -d ".codebuddy" ]; then
  mkdir -p .codebuddy/skills && cp -R "$SRC/skills/." .codebuddy/skills/ && cp_workflow
  echo "已安装到 CodeBuddy → .codebuddy/skills/ + WORKFLOW.md"
elif [ -d ".trae" ]; then
  mkdir -p .trae/skills && cp -R "$SRC/skills/." .trae/skills/ && cp_workflow
  echo "已安装到 Trae → .trae/skills/ + WORKFLOW.md"
elif [ -d ".claude" ]; then
  mkdir -p .claude/skills && cp -R "$SRC/skills/." .claude/skills/ && cp_workflow
  echo "已安装到 Claude Code → .claude/skills/ + WORKFLOW.md"
elif [ -d ".cursor" ]; then
  mkdir -p .cursor/rules && cp "$SRC/WORKFLOW.md" .cursor/rules/WORKFLOW.md
  cp -R "$SRC/skills/." .cursor/rules/ 2>/dev/null || true
  echo "已安装到 Cursor → .cursor/rules/（WORKFLOW.md + skills）"
elif [ -d ".github" ]; then
  mkdir -p .github && {
    for f in "$SRC/WORKFLOW.md" "$SRC"/skills/*/SKILL.md; do
      echo ""; echo "===== $f ====="; cat "$f"
    done
  } >> .github/copilot-instructions.md
  echo "已安装到 VS Code + Copilot → .github/copilot-instructions.md"
else
  mkdir -p ai-workflow && cp -R "$SRC/skills" "$SRC/WORKFLOW.md" ai-workflow/
  echo "未识别到 AI 工具目录，已复制到 ./ai-workflow/。"
  echo "请按你的工具手动放置：CodeBuddy=.codebuddy/skills/  Trae=.trae/skills/  Claude=.claude/skills/  Cursor=.cursor/rules/  Copilot=.github/copilot-instructions.md"
fi
echo "完成。以后提编程需求，AI 会先读 WORKFLOW.md 判断入口。"
