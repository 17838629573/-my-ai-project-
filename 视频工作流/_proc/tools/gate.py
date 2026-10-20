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
import ast
import io
import json
import os
import re
import shutil
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
    ("有效帧率", "tools/measure/efps.py", False),
    ("豁免复现", "tools/attest/repro.py", False),
    ("能力审计", "tools/measure/capaudit.py", False),
    ("代码异味", "tools/scan/smell.py", False),
    ("圈复杂度", "tools/complexity.py", False),
    ("债务棘轮", "tools/baseline.py", False),
    ("分层契约", "tools/layers.py", False),
    ("文档漂移", "tools/docsync.py", True),
    ("出处核验", "tools/attest/refcheck.py", True),
    ("阈值溯源", "tools/attest/provenance.py", False),
    ("动作质量", "tools/measure/motionqual.py", False),
    ("缺陷注入", "tools/faultbench.py", True),
]

_DEF_RE = re.compile(r"^\s*def\s+([A-Za-z_]\w*)", re.M)
# [R3 函数过长] motion/carry.py::carry_box 86>50
_ISSUE_RE = re.compile(r"^\[(?P<rule>[^\]]+)\]\s+(?P<rest>.+)$")


def _is_main_guard(node):
    """顶层语句是否为 `if __name__ == "__main__":`（AST 层判定）。"""
    if not isinstance(node, ast.If):
        return False
    test = getattr(node, "test", None)
    if not isinstance(test, ast.Compare):
        return False
    if not (isinstance(test.left, ast.Name) and test.left.id == "__name__"):
        return False
    return any(isinstance(c, ast.Constant) and c.value == "__main__"
               for c in test.comparators)


def _has_entry(path):
    """文件是否含可被 `python3 <file>` 触发的入口。

    只认 AST 里的顶层 `if __name__ == "__main__"`，不做子串匹配——
    注释或 docstring 里写一句 __main__ 不算有入口。
    """
    try:
        src = io.open(path, encoding="utf-8").read()
    except OSError:
        return False
    try:
        tree = ast.parse(src)
    except SyntaxError:
        # 语法坏了：跑起来必然非 0，交给 _run 真实执行去暴露，这里不判无入口
        return True
    return any(_is_main_guard(n) for n in tree.body)


def _run(rel, timeout=600):
    """跑一个工具，返回 (returncode, stdout+stderr)。"""
    path = os.path.join(_PROC, rel)
    if not os.path.exists(path):
        return 127, "工具不存在: %s" % rel
    if not _has_entry(path):
        # 为什么必须先查入口: 无 __main__ 的 .py 被当作脚本执行时什么都不做、
        # 退出码 0，gate 会把"一次都没跑"汇总成 PASS——这是最危险的假绿
        # （2026-10-14 实测：tools/measure/motionqual.py 缺入口，
        #  gate 长期报「动作质量 PASS」而自检从未执行）。
        return 127, ("工具无 __main__ 入口: %s —— 未执行任何检查，"
                     "结论无效，不得记为 PASS" % rel)
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


def _collect(quick):
    """按顺序跑各登记工具，收集结果列表。"""
    results = []
    for name, rel, slow in TOOLS:
        if quick and slow:
            results.append({"tool": name, "path": rel, "ok": None,
                            "skipped": True, "issues": []})
            continue
        rc, out = _run(rel)
        issues = _parse_issues(out) if rel == "check.py" else []
        tail = out.strip().splitlines()[-3:] if out else []
        results.append({"tool": name, "path": rel, "ok": rc == 0, "rc": rc,
                        "skipped": False, "issues": issues, "tail": tail})
    return results


def _flag(r):
    if r.get("skipped"):
        return "SKIP"
    return "PASS" if r["ok"] else "FAIL"


def _loc_of(it):
    loc = it["file"] or ""
    if it["line"]:
        loc = "%s:%d" % (loc, it["line"])
    return loc


def _print_one(r):
    """打印单个工具的结果行（失败时附带前 8 条问题与输出尾三行）。"""
    print("  [%s] %-8s %s" % (_flag(r), r["tool"], r["path"]))
    if r["ok"] is not False:
        return
    for it in r["issues"][:8]:
        print("        - [%s] %s %s" % (it["rule"], _loc_of(it), it["msg"]))
    for tl in r.get("tail", []):
        print("        | %s" % tl)


def _print_human(results, bad):
    print("=" * 62)
    print("统一自检 gate —— %d 项" % len(results))
    print("=" * 62)
    for r in results:
        _print_one(r)
    print("-" * 62)
    print("结论: %s（失败 %d 项）" % ("OK" if not bad else "有问题", len(bad)))
    if bad:
        print("下一步: 先修 CRITICAL/真问题；"
              "声称假阳性须附最小复现（tools/repro.py）")

# 注入样本：注释/docstring 里提一句 __main__ 不算入口，只有真 guard 才算
_SC_SAMPLES = {
    "no_entry": "def f():\n    return 1\n",
    "in_comment": '# if __name__ == "__main__": 注释里提一句不算\nx = 1\n',
    "real_entry": "def f(): pass\n\nif __name__ == '__main__':\n    f()\n",
}
_SC_EXPECT = {"no_entry": False, "in_comment": False, "real_entry": True}


def _sc_all_entries(_d):
    """断言 1：TOOLS 清单里的文件都存在，且都有 __main__ 入口。"""
    missing = [rel for _, rel, _ in TOOLS
               if not os.path.exists(os.path.join(_PROC, rel))]
    if missing:
        return False, "工具文件缺失: %s" % missing
    no_entry = [rel for _, rel, _ in TOOLS
                if not _has_entry(os.path.join(_PROC, rel))]
    if no_entry:
        return False, "工具缺 __main__ 入口: %s" % no_entry
    return True, "TOOLS %d 个全部有入口" % len(TOOLS)


def _sc_entry_teeth(d):
    """断言 2：_has_entry 对注入样本判定正确——只看"现在有没有"是没牙齿的。"""
    for k, src in _SC_SAMPLES.items():
        p = os.path.join(d, k + ".py")
        io.open(p, "w", encoding="utf-8").write(src)
        got = _has_entry(p)
        if got is not _SC_EXPECT[k]:
            return False, "_has_entry(%s)=%s 期望 %s" % (k, got, _SC_EXPECT[k])
    return True, "_has_entry 注入 %d 例判定正确" % len(_SC_SAMPLES)


def _sc_run_rejects(d):
    """断言 3：缺入口的文件经 _run 必须非 0，且输出明说「未执行」。"""
    tmpdir = os.path.join(_PROC, "_gate_sc")
    os.makedirs(tmpdir, exist_ok=True)
    shutil.copy(os.path.join(d, "no_entry.py"),
                os.path.join(tmpdir, "no_entry.py"))
    rc, out = _run("_gate_sc/no_entry.py")
    shutil.rmtree(tmpdir, ignore_errors=True)
    if rc == 0:
        return False, "缺入口工具 rc=0 —— 会被汇总成 PASS"
    if "未执行" not in out:
        return False, "缺入口工具 rc=%s 但输出未声明「未执行」: %r" % (rc, out[:80])
    return True, "缺入口工具 rc=%s 且不冒充 PASS" % rc


def self_check():
    """自检：汇总器自己会不会把「没跑」当成「通过」。

    三条断言缺一不可（分工见各 _sc_* 的 docstring）。为什么必须注入验证：
    历史上 gate 长期把 tools/measure/motionqual.py 的「未执行」汇总成 PASS
    ——该文件缺 __main__，子进程跑它什么都不做却退 0；
    而"当前 TOOLS 都有入口"这种只看现状的检查抓不到它。
    """
    import tempfile

    d = tempfile.mkdtemp(prefix="gate_sc_")
    msgs = []
    try:
        for fn in (_sc_all_entries, _sc_entry_teeth, _sc_run_rejects):
            ok, msg = fn(d)
            if not ok:
                print("[gate self_check] %s -> FAIL" % msg)
                return False
            msgs.append(msg)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    print("[gate self_check] %s -> PASS" % "；".join(msgs))
    return True


def main(argv):
    """统一入口：跑全部工具，机读 --json / 快跑 --quick。"""
    if "--self-check" in argv:
        return 0 if self_check() else 1
    as_json = "--json" in argv
    results = _collect("--quick" in argv)
    bad = [r for r in results if r["ok"] is False]
    overall = 1 if bad else 0
    if as_json:
        print(json.dumps({"ok": overall == 0, "results": results},
                         ensure_ascii=False, indent=2))
        return overall
    _print_human(results, bad)
    return overall


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
