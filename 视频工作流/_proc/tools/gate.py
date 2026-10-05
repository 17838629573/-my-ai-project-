# 契约: proc/tools/gate
#   一句话: 统一自检入口：一键跑全部长期工具，汇总退出码，支持 --json 机器可读输出
#   完整契约见 tools/__init__.py
#   依据: CI 门禁惯例——单一入口 + 非零退出码阻断（pytest/tox 均如此）；
#         gosec/semgrep 输出机器可读格式供自动化消费；
#         报错带 file:line 是 linter 的通用约定（grep -n 可二次定位）。
# -*- coding: utf-8 -*-
"""统一自检入口 gate.py —— 给 AI 和 CI 用的一条命令。

用法:
    python3 tools/gate.py            # 人读：分组摘要
    python3 tools/gate.py --json     # 机读：结构化 JSON，供 AI 直接 parse
    python3 tools/gate.py --quick    # 跳过耗时项（变异测试/门检）

设计要点（针对 AI 消费优化）:
  1. 单一入口：AI 不必知道内部有 6 个工具、各自怎么调
  2. 退出码可信：任一工具失败 -> 整体非零
  3. 结构化输出：--json 出 {tool, ok, issues:[{rule,file,line,msg}]}
  4. 报错带行号：R3/R14 等文本报错自动二次定位到 def 行
"""
import io
import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROC = os.path.dirname(_HERE)
if _PROC not in sys.path:
    sys.path.insert(0, _PROC)

# 工具清单: (显示名, 相对路径, 是否耗时)
TOOLS = [
    ("契约检查", "check.py", False),
    ("判据变异", "tools/mutate.py", True),
    ("三表一致", "tools/consistency.py", False),
    ("有效帧率", "tools/efps.py", False),
    ("豁免复现", "tools/repro.py", False),
    ("能力审计", "tools/capaudit.py", False),
]

_DEF_RE = re.compile(r"^\s*def\s+([A-Za-z_]\w*)", re.M)
# [R3 函数过长] motion/carry.py::carry_box 86>50
_ISSUE_RE = re.compile(r"^\[(?P<rule>[^\]]+)\]\s+(?P<rest>.+)$")


def _run(rel, timeout=600):
    """跑一个工具，返回 (returncode, stdout+stderr)。"""
    path = os.path.join(_PROC, rel)
    if not os.path.exists(path):
        return 127, "工具不存在: %s" % rel
    try:
        p = subprocess.run(
            [sys.executable, rel], cwd=_PROC, timeout=timeout,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        out = p.stdout.decode("utf-8", "replace")
        return p.returncode, out
    except subprocess.TimeoutExpired:
        return 124, "超时 %ss" % timeout


def _locate(rel_file, fname):
    """给函数名补行号：在文件里找 def fname。"""
    path = os.path.join(_PROC, rel_file)
    if not os.path.exists(path) or not fname:
        return None
    try:
        src = io.open(path, encoding="utf-8").read()
    except Exception:
        return None
    for i, line in enumerate(src.splitlines(), 1):
        m = _DEF_RE.match(line)
        if m and m.group(1) == fname:
            return i
    return None


def _parse_issues(out):
    """从 check.py 输出里抽问题行，并尽力补 file:line。"""
    issues = []
    for line in out.splitlines():
        line = line.strip()
        m = _ISSUE_RE.match(line)
        if not m:
            continue
        rule, rest = m.group("rule"), m.group("rest")
        f, ln, msg = None, None, rest
        # 形如 "motion/carry.py::carry_box 86>50"
        mm = re.match(r"([A-Za-z0-9_./]+\.py)::([A-Za-z_]\w*)\s*(.*)$", rest)
        if mm:
            f, fn, tail = mm.group(1), mm.group(2), mm.group(3)
            ln = _locate(f, fn)
            msg = "%s %s" % (fn, tail) if tail else fn
        else:
            mm2 = re.match(r"([A-Za-z0-9_./]+\.py)\s*(.*)$", rest)
            if mm2:
                f, msg = mm2.group(1), mm2.group(2)
        if "已知债务" in rule or line.startswith("已知债务"):
            continue
        issues.append({"rule": rule, "file": f, "line": ln, "msg": msg.strip()})
    return issues


def main(argv):
    as_json = "--json" in argv
    quick = "--quick" in argv
    results = []
    for name, rel, slow in TOOLS:
        if quick and slow:
            results.append({"tool": name, "path": rel, "ok": None,
                            "skipped": True, "issues": []})
            continue
        rc, out = _run(rel)
        ok = (rc == 0)
        issues = _parse_issues(out) if rel == "check.py" else []
        results.append({"tool": name, "path": rel, "ok": ok, "rc": rc,
                        "skipped": False, "issues": issues,
                        "tail": out.strip().splitlines()[-3:] if out else []})
    bad = [r for r in results if r["ok"] is False]
    overall = 1 if bad else 0

    if as_json:
        print(json.dumps({"ok": overall == 0, "results": results},
                         ensure_ascii=False, indent=2))
        return overall

    print("=" * 62)
    print("统一自检 gate —— %d 项" % len(results))
    print("=" * 62)
    for r in results:
        if r.get("skipped"):
            flag = "SKIP"
        else:
            flag = "PASS" if r["ok"] else "FAIL"
        print("  [%s] %-8s %s" % (flag, r["tool"], r["path"]))
        if r["ok"] is False:
            for it in r["issues"][:8]:
                loc = it["file"] or ""
                if it["line"]:
                    loc = "%s:%d" % (loc, it["line"])
                print("        - [%s] %s %s" % (it["rule"], loc, it["msg"]))
            for tl in r.get("tail", []):
                print("        | %s" % tl)
    print("-" * 62)
    print("结论: %s（失败 %d 项）" % ("OK" if overall == 0 else "有问题", len(bad)))
    if bad:
        print("下一步: 先修 CRITICAL/真问题；声称假阳性须附最小复现（tools/repro.py）")
    return overall


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
