#!/bin/sh
# PostToolUse 钩子：工具调用完成后的校验（留痕 + 完整性检查）
# Fail-Close：脚本自身异常时不阻塞，只记录警告（post 是事后检查）
set -u

INPUT=$(cat 2>/dev/null || echo "")

TOOL=$(printf '%s' "$INPUT" | sed -n 's/.*"tool"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
FILE=$(printf '%s' "$INPUT" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
[ -z "$FILE" ] && FILE=$(printf '%s' "$INPUT" | sed -n 's/.*"path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)

# 对核心区文件改动做额外留痕提示
case "$FILE" in
  *enforce.py|*dep_check.py|*WORKFLOW.md|*SKILL.md|*tracks/*.track.md)
    echo "[hook] 核心区文件已改动，请记得执行：" >&2
    echo "[hook]   python3 scripts/enforce.py log-effect $FILE 有效 <分数> <说明>" >&2
    ;;
esac

exit 0
