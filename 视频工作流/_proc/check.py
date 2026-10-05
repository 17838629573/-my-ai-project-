# 契约: proc/check
#   架构契约扫描器：依赖方向 / 行数阈值 / 公开面 / 契约块格式
"""Enforce architecture contracts: layer direction, size limits, public surface.

规则与出处（不凭记忆，逐条可查）：
  R1 依赖单向，且含传递依赖   import-linter layers: "even indirectly"
  R2 模块 50~500 行           AlgoMaster / mrognlie 两处独立来源
  R3 函数 <=50 行             mrognlie coding guide
  R4 包条目 3~20 个           mrognlie coding guide
  R5 公开名 <=40，否则拆      AlgoMaster: "A module with 40 public names is doing too much"
  R6 契约首行 <=72 字符       numpydoc 规范
  R7 职责要能一句话说清        AlgoMaster: 出现两个"和"就该拆
  R9 圈复杂度 <=10（>15 需书面说明）  NASA SWEHB 3.2.2 / NIST
  R8 避免过深嵌套/上帝包      Smalltalk Package Anti-Patterns
  R10 包必须真实可导入         FixDevs: "Verify with a clean import"
  R11 能力/公式必须带出处       Bedrock Grounded RAG: provenance 不可缺失

用法: python check.py
"""
import ast
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# 允许的依赖方向：只有上层可依赖下层（R1）
ALLOW = {
    "shape":  set(),
    "color":  {"shape"},
    "scene":  {"shape", "color"},
    "motion": {"shape", "color", "scene"},
    "(root)": {"shape", "color", "scene", "motion"},
}
PKGS = list(ALLOW)

LIMIT_MIN, LIMIT_MAX = 50, 500      # R2
LIMIT_FUNC = 50                      # R3
PKG_MIN, PKG_MAX = 3, 20             # R4
LIMIT_PUBLIC = 40                    # R5
LIMIT_SUMMARY = 72                   # R6
LIMIT_CC = 10                        # R9  NASA/NIST: 超过 10 就拆
LIMIT_CC_HARD = int(os.environ.get('PROC_CC_HARD', 15))  # R9 红线，可用环境变量临时上调以生成报告
MIN_SOURCE = 8          # R11 出处字符串最短长度，短于此视为没写

SKIP_DIRS = {"_bak", "__pycache__"}


def walk_py():
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fn in sorted(files):
            if fn.endswith(".py") and fn != "__init__.py":
                yield os.path.join(dirpath, fn)


def pkg_of(path):
    rel = os.path.relpath(path, ROOT)
    return rel.split(os.sep)[0] if os.sep in rel else "(root)"


def node_of(path):
    """节点名 pkg.module，用于传递依赖分析。"""
    rel = os.path.relpath(path, ROOT)[:-3]
    return rel.replace(os.sep, ".")


def edges(path):
    """返回该文件 import 到的 (pkg, module) 节点集合。"""
    out = set()
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except SyntaxError:
        return out
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                top = a.name.split(".")[0]
                if top in PKGS:
                    out.add((top, ".".join(a.name.split(".")[:2])))
        elif isinstance(n, ast.ImportFrom) and n.module:
            top = n.module.split(".")[0]
            if top in PKGS:
                out.add((top, ".".join(n.module.split(".")[:2])))
    return out


def _reach(graph, start):
    """传递闭包：从 start 出发可达的全部包（含间接，R1 要查间接）。"""
    seen, stack = set(), [start]
    while stack:
        cur = stack.pop()
        for nxt in graph.get(cur, ()):  # type: ignore[union-attr]
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return {n.split(".")[0] for n in seen}


def _check_interface(tag, src):
    """接口层断言：契约块必须存在，且首行能一句话说清。"""
    out = []
    if "契约:" not in src:
        out.append(f"[缺契约] {tag}")
    m = re.search(r"契约:\s*\S+\s*\n#?\s*(?:一句话:\s*)?(.+)", src)
    if m and len(m.group(1)) > LIMIT_SUMMARY:
        out.append(f"[R6 契约首行过长] {tag} {len(m.group(1))}>{LIMIT_SUMMARY}")
    return out


def _check_structure(tag, pkg, direct, transit):
    """架构层断言：依赖方向单向，同包内 import 放行。"""
    allow = ALLOW.get(pkg, set()) | {pkg}
    return [f"[R1 逆向依赖] {tag} -> {b}"
            for b in sorted((direct | transit) - allow)]


def _check_size(tag, n):
    """实现层 R2：模块行数落在 50~500。"""
    if n > LIMIT_MAX:
        return [f"[R2 超纲] {tag} {n}>{LIMIT_MAX}"]
    if n < LIMIT_MIN:
        return [f"[R2 过短] {tag} {n}<{LIMIT_MIN}"]
    return []


def _check_funcs(tag, src):
    """实现层 R3：单个函数不超过 50 行。"""
    out = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out
    for fn in [x for x in ast.walk(tree)
               if isinstance(x, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        ln = (fn.end_lineno or fn.lineno) - fn.lineno + 1
        if ln > LIMIT_FUNC:
            out.append(f"[R3 函数过长] {tag}::{fn.name} {ln}>{LIMIT_FUNC}")
    return out


def _check_public(tag, src):
    """实现层 R5：公开名不超过 40，超了说明模块干太多。"""
    pub = [m for m in re.findall(r"^([a-z_][\w]*)\s*(?:=|\()", src, re.M)
           if not m.startswith("_")]
    if len(pub) > LIMIT_PUBLIC:
        return [f"[R5 公开面过大] {tag} {len(pub)}>{LIMIT_PUBLIC}"]
    return []


def _check_complexity(tag, src):
    """实现层 R9：圈复杂度 <=10；>15 必须书面说明为何降不下来。

    出处: NASA Software Engineering Handbook 3.2.2——"limit cyclomatic
    complexity to 15 or provide a written explanation"；NIST 结构化测试
    方法论在特殊情形下放宽到 15，10 是已获大量佐证的推荐值。
    radon 分级 1-5=A / 6-10=B / 11-20=C，故取 10 为线、15 为红线。
    """
    try:
        from radon.complexity import cc_visit
    except ImportError:
        return []
    out = []
    for b in cc_visit(src):
        if b.complexity > LIMIT_CC_HARD:
            out.append(f"[R9 圈复杂度红线] {tag}::{b.name} {b.complexity}>{LIMIT_CC_HARD}")
        elif b.complexity > LIMIT_CC:
            out.append(f"[R9 圈复杂度超线] {tag}::{b.name} {b.complexity}>{LIMIT_CC}")
    return out

def _check_internals(tag, src, n):
    """实现层断言汇总：尺寸 + 函数 + 公开面。"""
    return (_check_size(tag, n)
            + _check_funcs(tag, src)
            + _check_public(tag, src)
            + _check_complexity(tag, src))


def _check_pkg_counts(counts):
    """包粒度断言：条目数落在 3~20，既防空壳包也防上帝包。"""
    return [f"[R4 包条目数] {p} {c} 不在 {PKG_MIN}~{PKG_MAX}"
            for p, c in counts.items()
            if c and not (PKG_MIN <= c <= PKG_MAX)]


def _check_importable():
    """R10 可导入性：真实 import 一遍，抓静态扫描看不见的死结。

    出处: FixDevs "Verify with a clean import — run python -c 'import app'"。
    本条由真实事故催生: render.py 与 cloth.py 互相 import，
    行数/依赖/复杂度/契约全部通过，但 motion.character 整体 ImportError 跑不起来。
    """
    out = []
    for dirpath, _dirs, files in os.walk(ROOT):
        if os.path.basename(dirpath) in SKIP_DIRS or "__init__.py" not in files:
            continue
        rel = os.path.relpath(dirpath, ROOT).replace(os.sep, ".")
        if rel in (".", ""):
            continue
        try:
            r = subprocess.run([sys.executable, "-c", f"import {rel}"],
                               cwd=ROOT, capture_output=True,
                               text=True, timeout=120)
        except subprocess.TimeoutExpired:
            out.append(f"[R10 导入超时] {rel}")
            continue
        if r.returncode != 0:
            last = (r.stderr.strip().splitlines() or ["未知错误"])[-1]
            out.append(f"[R10 不可导入] {rel}: {last[:120]}")
    return out


def _scan_file(f, graph):
    """扫描单个文件：接口 → 架构 → 实现，返回 (包名, 报告行, 问题列表)。

    出处: qadrlabs Long Method Signal 3——"循环体含复杂逻辑就该取出命名方法"，
    取出后内层逻辑可独立验证，主函数只留编排。
    """
    pkg = pkg_of(f)
    src = open(f, encoding="utf-8").read()
    n = src.count("\n") + 1
    tag = f"{pkg}/{os.path.basename(f)}"
    direct = {p for p, _ in edges(f)}
    out = (_check_interface(tag, src)
           + _check_structure(tag, pkg, direct,
                              _reach(graph, node_of(f)) - {pkg})
           + _check_internals(tag, src, n))
    size = "超纲" if n > LIMIT_MAX else ("过短" if n < LIMIT_MIN else "OK")
    row = (pkg, os.path.basename(f), n, size,
           "Y" if "契约:" in src else "N",
           ",".join(sorted(direct)) or "-")
    return pkg, row, out


def _caps_without_source(path):
    """用 AST 取 @capability 的名字与出处。

    不用正则：装饰器既有位置参数也有 source= 关键字，还有跨行写法，
    正则会漏掉后两种，导致无出处的能力静默通过。
    """
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in node.decorator_list:
            if not isinstance(d, ast.Call):
                continue
            fn = d.func
            if not (isinstance(fn, ast.Name) and fn.id == "capability"):
                continue
            name = d.args[0].value if d.args and isinstance(
                d.args[0], ast.Constant) else "?"
            source = ""
            if len(d.args) > 1 and isinstance(d.args[1], ast.Constant):
                source = str(d.args[1].value)
            for kw in d.keywords:
                if kw.arg == "source" and isinstance(kw.value, ast.Constant):
                    source = str(kw.value.value)
            if len(source.strip()) < MIN_SOURCE:
                out.append("[R11 能力无出处] %s (%s)"
                           % (name, os.path.basename(path)))
    return out


def _check_provenance():
    """R11：已登记的能力与公式必须带出处，缺出处说明是凭记忆写的。

    出处: Bedrock Grounded RAG Fallback Chain——生成结果必须带 provenance，
    缺 provenance 的不可采信。只查已实现的（IMPL），STUB 允许暂时没出处。
    """
    out = []
    for f in walk_py():
        out += _caps_without_source(f)
    reg = os.path.join(ROOT, "FORMULA_REGISTRY.json")
    if os.path.exists(reg):
        with open(reg, encoding="utf-8") as fh:
            data = json.load(fh)
        for g in data.get("groups", []):
            for it in g.get("items", []):
                if it.get("status") != "IMPL":
                    continue
                if len(str(it.get("src", "")).strip()) < MIN_SOURCE:
                    out.append("[R11 公式无出处] %s" % it.get("id"))
    return out


def _report(rows, problems):
    """一次打印全部问题，多失败一起报，不停在第一个。"""
    print(f"{'包':<8}{'文件':<18}{'行数':>6}  {'尺寸':<5}契约  直接依赖")
    for r in sorted(rows):
        print(f"{r[0]:<8}{r[1]:<18}{r[2]:>6}  {r[3]:<5}{r[4]}     {r[5]}")
    print()
    for s in problems or ["全部通过"]:
        print(s)
    print(f"\n合计 {len(rows)} 个小模块，{len(problems)} 个问题")


def main():
    """编排：建依赖图 → 逐文件扫描 → 包粒度汇总 → 出报告。"""
    files = list(walk_py())
    graph = {node_of(f): {f"{p}.{m}" for p, m in edges(f)} for f in files}
    counts = {p: 0 for p in PKGS}
    problems, rows = [], []
    for f in files:
        pkg, row, out = _scan_file(f, graph)
        counts[pkg] = counts.get(pkg, 0) + 1
        rows.append(row)
        problems += out
    problems += (_check_pkg_counts(counts) + _check_importable()
                 + _check_provenance())
    _report(rows, problems)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
