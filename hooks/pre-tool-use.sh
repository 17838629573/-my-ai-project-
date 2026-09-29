#!/bin/sh
# PreToolUse 钩子：拦截 Write / Edit，把铁律5 红黄区保护挂到工具层
# 不再依赖 AI 主动调用 —— 每次写文件都会自动被拦
# Fail-Close：脚本自身异常时默认拒绝（不是放行）
set -u

INPUT=$(cat 2>/dev/null || echo "")

# 从 JSON 输入中解析目标文件路径（兼容多种宿主字段名）
FILE=$(printf '%s' "$INPUT" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
[ -z "$FILE" ] && FILE=$(printf '%s' "$INPUT" | sed -n 's/.*"path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
[ -z "$FILE" ] && FILE=$(printf '%s' "$INPUT" | sed -n 's/.*"filepath"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)

if [ -z "$FILE" ]; then
  echo "BLOCK: 无法解析目标文件路径，按 Fail-Close 拒绝写入" >&2
  exit 2
fi

# 跳过非写操作工具（读/搜索等）
TOOL=$(printf '%s' "$INPUT" | sed -n 's/.*"tool"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)
case "$TOOL" in
  read*|search*|fetch*|list*|glob*|ls*|pwd*|cat*|head*|tail*|grep*|find*)
    exit 0  # 只读工具直接放行
    ;;
esac

# 调用 enforce.py check-write 做实际门禁检查
if [ -x scripts/enforce.py ]; then
  python3 scripts/enforce.py check-write "$FILE" >&2 || exit 2
elif [ -f scripts/enforce.py ]; then
  python3 scripts/enforce.py check-write "$FILE" >&2 || exit 2
elif [ -f enforce.py ]; then
  python3 enforce.py check-write "$FILE" >&2 || exit 2
else
  echo "BLOCK: 找不到 enforce.py，按 Fail-Close 拒绝写入" >&2
  exit 2
fi

exit 0
