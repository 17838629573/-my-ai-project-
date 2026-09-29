#!/bin/sh
# 独立恢复脚本 — 不依赖 enforce.py（被保护者无法自我保护：
# 一旦 enforce.py 自身被改成语法错误，它自己也跑不起来，无法自回滚）。
# 本脚本为纯 shell，只做一件事：把冻结基线复制回原位。
#
# 用法：
#   sh scripts/restore.sh              # 列出所有可用基线
#   sh scripts/restore.sh scripts/enforce.py   # 恢复指定文件
#   sh scripts/restore.sh --all        # 恢复全部核心区文件

BASE=".workflow-baseline"

if [ ! -d "$BASE" ]; then
  echo "✗ 无基线目录 $BASE（尚未改动过核心区，或已被删除）"
  exit 1
fi

if [ $# -eq 0 ]; then
  echo "可用基线："
  (cd "$BASE" && find . -type f | sed 's|^\./||' | sed 's/^/  /')
  echo
  echo "恢复：sh scripts/restore.sh <文件>  或  --all"
  exit 0
fi

if [ "$1" = "--all" ]; then
  (cd "$BASE" && find . -type f | sed 's|^\./||') | while read -r f; do
    mkdir -p "$(dirname "$f")" 2>/dev/null || true
    cp "$BASE/$f" "$f"
    echo "✓ 已恢复 $f"
  done
  echo "全部恢复完成。信任档位请在 CORELOG.md 追加一条「回滚」记录以重置为 L1。"
  exit 0
fi

if [ ! -f "$BASE/$1" ]; then
  echo "✗ 基线不存在：$BASE/$1"
  exit 1
fi

cp "$BASE/$1" "$1"
echo "✓ 已恢复 $1 → 初始基线"
echo "  请执行：python3 scripts/enforce.py log-effect $1 回滚 - 已恢复至初始基线"
