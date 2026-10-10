#!/usr/bin/env bash
# 契约: 根目录/run.sh
#   一句话: 零记忆一键入口——自动装依赖并按名字跑任务，不需要知道 _proc 下的路径
#   依据: 第三方评估"开箱即用 5.5/10，无一键脚本"，本脚本补齐该缺口
set -euo pipefail

cd "$(dirname "$0")"
PROC="_proc"

usage() {
  cat <<'EOF'
用法: ./run.sh <任务>

  install   装依赖（首次必做，装完自动继续）
  demo      出演示片（beat 时间线）
  cafe      咖啡馆 12 秒
  test      跑门检 45 项
  check     架构契约扫描
  gate      统一门禁（可加 --json / --quick）
  index     重生成 INDEX.md
  api       重生成 API.md（能力接口文档）
  all       依次跑 index + api + test + gate（完整体检）

示例: ./run.sh all
EOF
}

# 依赖自检：缺哪个装哪个，不写死版本，缺 pip 时明确报错而非静默继续
ensure_deps() {
  python3 - <<'PY' || exit 1
import importlib, subprocess, sys
need = {"numpy": "numpy", "PIL": "pillow", "cv2": "opencv-python-headless"}
miss = [pkg for mod, pkg in need.items() if not importlib.util.find_spec(mod)]
if miss:
    print("缺少运行依赖:", " ".join(miss), "→ 自动安装")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *miss])
else:
    print("运行依赖已就绪")
PY
}

task="${1:-}"; shift || true
case "$task" in
  install) ensure_deps ;;
  demo)  ensure_deps; python3 "$PROC/beat_demo.py" ;;
  cafe)  ensure_deps; python3 "$PROC/showreel/cafe.py" ;;
  test)  ensure_deps; python3 "$PROC/tests/run_all.py" "$@" ;;
  check) ensure_deps; python3 "$PROC/check.py" "$@" ;;
  gate)  ensure_deps; python3 "$PROC/tools/gate.py" "$@" ;;
  index) python3 "$PROC/gen_index.py" ;;
  api)   python3 "$PROC/gen_api.py" ;;
  all)
    python3 "$PROC/gen_index.py"
    python3 "$PROC/gen_api.py"
    python3 "$PROC/tests/run_all.py"
    python3 "$PROC/tools/gate.py" --quick
    ;;
  ""|-h|--help|help) usage ;;
  *) echo "未知任务: $task"; usage; exit 2 ;;
esac
