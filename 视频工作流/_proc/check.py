# 契约: proc/check
#   架构契约扫描器：依赖方向 / 行数阈值 / 公开面 / 契约块格式
"""Enforce architecture contracts: layer direction, size limits, public surface.

规则与出处（不凭记忆，逐条可查）：
  R1 依赖单向，且含传递依赖   已迁至 import-linter(见 .importlinter / tools/layers.py)
                              —— 自造 ALLOW 表漏登记层会产生假阳性, 且只认 _proc.* 包名,
                                 扁平包名(motion.xxx) 完全漏检(实测注入未被报出)。
  R2 模块 50~500 行           AlgoMaster / mrognlie 两处独立来源
  R3 函数 <=50 行             已迁至 lizard(tools/complexity.py), 同一阈值 50,
                              由 lizard 的 length 字段产出, 避免两套口径各报各的。
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
import datetime as _dt
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import tools.debtledger as _dl

# 允许的依赖方向：只有上层可依赖下层（R1）
ALLOW = {
    # base 位于最底: 零依赖公共设施(如统一断言执行器)，任何层都可依赖。
    # 由真实事故催生: 执行器原置 tools/(最上) → motion/showreel 反向依赖 tools(8条R1)
    "base":   set(),
    "shape":  {"base"},
    "color":  {"base", "shape"},
    "scene":  {"base", "shape", "color"},
    "motion": {"base", "shape", "color", "scene"},
    "showreel": {"base", "shape", "color", "scene", "motion"},
    "tests": {"base", "shape", "color", "scene", "motion", "showreel"},
    # tools 是检查者，必须能读到被检查的每一层，故置于最上
    "tools": {"base", "shape", "color", "scene", "motion", "showreel", "tests"},
    "(root)": {"base", "shape", "color", "scene", "motion", "showreel", "tests", "tools"},
}
PKGS = list(ALLOW)

# R16 分层表完整性：实际存在的顶层包必须登记。
# 出处: import-linter "exhaustive = true — if a module is added to the code base
#       in the same package as your layers, the contract will fail"
# 本条由真实事故催生: 新建 tools/ 目录后未登记进 ALLOW，
# 导致 tools/* -> motion 被判逆向依赖，12 条假阳性把真问题(超纲模块)埋掉。
EXHAUSTIVE_IGNORES = {"_bak", "__pycache__", "_archive_旧链路"}

# 已知债务清单：显式登记、有归属、只减不增。
# 出处: import-linter "ignore_imports — keep that list short and treat each
#       entry as debt with an owner"。与静默忽略的区别: 清单外一律照报。
# 已知债务台账已下沉到 tools/debtledger.py（R19）。
# 下沉原因: 台账本体置于本文件时，check.py 达 565 行 > R2 上限 500。
# 与静默忽略的区别: 清单外一律照报，见 debtledger.py 顶部注释。

LIMIT_MIN, LIMIT_MAX = 50, 500
LIMIT_MIN_EFF = 20   # R2 下界改用有效代码行，依据 SIG/SonarQube NCLoC      # R2
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


_SYNTAX_ERRS = []   # 语法错误收集器：绝不静默吞掉

def edges(path):
    """返回该文件 import 到的 (pkg, module) 节点集合。"""
    out = set()
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except SyntaxError as e:
        _SYNTAX_ERRS.append(f"[R0 语法错误] {path}:{getattr(e,'lineno','?')} {e.msg}")
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


# R1(依赖方向)已于 2026-10-06 迁至 import-linter：本文件的 ALLOW 表只认 _proc.* 包名，
# 对本项目大量使用的扁平包名(motion.xxx / tools.xxx)完全漏检——
# 实测注入 shape/_tmp_rev.py 写 "from motion import beat", R1 报错而 lint-imports 报 KEPT。
# 配置见项目根 .importlinter，门禁入口 tools/layers.py。

def _eff_lines(src):
    """有效代码行 NCLoC：去空行、注释、docstring。

    依据 SIG / SonarQube "Lines to count = lines with code"：规模度量应只数
    可执行代码，排除注释与空行。aivosto 建议文件下限 LLOC>=1（非空即可），
    文件行数合理区间 [5,1000]。本项目模块自带契约块+self_check，
    取 20 为"职责没落地"的判定线，远高于业界下限，留足余量。
    """
    lines = src.split("\n")
    n = sum(1 for ln in lines if ln.strip() and not ln.strip().startswith("#"))
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return n
    for node in ast.walk(tree):
        if isinstance(node,(ast.Module,ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
            d = ast.get_docstring(node, clean=False)
            if d is not None:
                n -= d.count("\n") + 1
    return max(n, 0)

def _check_size(tag, n, src=None):
    """实现层 R2：模块规模。

    上界用总行数（防超纲，LIMIT_MAX=500）。
    下界用有效代码行 NCLoC（LIMIT_MIN_EFF=20）——总行数下界会把
    "注释/契约块写得厚、代码其实完整"的模块误判成空壳。
    """
    if n > LIMIT_MAX:
        return [f"[R2 超纲] {tag} {n}>{LIMIT_MAX}"]
    if src is not None:
        eff = _eff_lines(src)
        if eff < LIMIT_MIN_EFF:
            return [f"[R2 空壳] {tag} 有效代码行 {eff}<{LIMIT_MIN_EFF}（总行 {n}）"]
    elif n < LIMIT_MIN:
        return [f"[R2 过短] {tag} {n}<{LIMIT_MIN}"]
    return []


# R3(函数<=50行)已迁至 tools/complexity.py：由 lizard 的 length 字段产出，
# 阈值仍为 50(mrognlie)，严重度不变，仅换实现方。

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
    """实现层断言汇总：尺寸 + 公开面 + 复杂度。

    函数长度(R3)已于 2026-10-06 迁至 tools/complexity.py(lizard)，
    依赖方向(R1)迁至 import-linter —— 两者都由上游工具产出同一口径，
    本文件不再重复实现，避免"两套标准各报各的"。
    """
    return (_check_size(tag, n, src)
            + _check_public(tag, src)
            + _check_complexity(tag, src))


def _check_pkg_counts(counts, rdep=None):
    rdep = rdep or {}
    """包粒度断言：上界防上帝包，下界只查非基础层。

    mrognlie 的 3~20 下界本意是防"只有一个文件的假包"。
    但基础层(ALLOW 为空集的叶子层, 如 shape/color)条目天然少，
    对它们套下界会稳定产出假阳性——故只对会被他人依赖的业务层套下界。
    """
    out = []
    for p, c in sorted(counts.items()):
        if not c:
            continue
        if c > PKG_MAX:
            out.append(f"[R4 上帝包] {p} {c}>{PKG_MAX}")
        elif rdep.get(p, 0) == 0 and c < PKG_MIN:
            # 下界只查"没人依赖的孤包"。叶子层(ALLOW 为空集)条目天然少，
            # 只要有人依赖就是真分层而非"只有一个文件的假包"——
            # 对它们套 3 个模块的下界会稳定产出假阳性(见 repro S3)。
            # 但"零依赖 + 条目少"是真孤包，照报，不豁免。
            out.append(f"[R4 空壳包] {p} {c}<{PKG_MIN} 且无人依赖(rdep=0)")
    return out


def _check_layer_exhaustive(counts):
    """R16 分层表完整性：实际存在的顶层包必须登记进 ALLOW。

    出处: import-linter exhaustive = true。
    这条是"防误报的工具"——分层表一旦漏登记新目录，
    R1 会对该目录所有文件报逆向依赖，噪音淹没真问题。
    与其事后修噪音，不如让漏登记本身立刻报错。
    """
    return [f"[R16 分层表漏登记] 顶层包 '{p}' 存在但未写入 ALLOW "
            f"({c} 个文件) —— 不登记会让 R1 对它全量误报"
            for p, c in sorted(counts.items())
            if p in PKGS
            if c and p not in ALLOW and p not in EXHAUSTIVE_IGNORES]


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
    except SyntaxError as e:
        _SYNTAX_ERRS.append(f"[R0 语法错误] {path}:{getattr(e,'lineno','?')} {e.msg}")
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


def _check_judge_power():
    """R13 判据效力：给判据注入已知坏输入，仍判 PASS 说明判据是瞎的。

    出处: Mutation Testing (PIT / mutmut)。行覆盖率 100% 也可能一条有效断言
    都没有——注入 mutant 后测试仍全绿即为 SURVIVED，那正是测试盲区。
    本项目事故：F35 复用 case_A1、B10 支撑脚反解导致判据恒 0，
    两者都能被"注入坏值仍 PASS"直接抓到。
    """
    import subprocess
    p = os.path.join(ROOT, "tools", "mutate.py")
    if not os.path.exists(p):
        return []
    try:
        r = subprocess.run([sys.executable, p], capture_output=True,
                           text=True, timeout=300)
    except Exception:                                  # noqa: BLE001
        return []
    out = []
    for line in (r.stdout or "").splitlines():
        if line.strip().startswith("[存活]"):
            out.append("[R13 判据无牙齿] " + line.strip()[5:].strip())
    return out


def _check_cross_consistency():
    """R14 三表一致性：能力注册表 / 用例执行表 / 桥接器 互为闭包。

    出处: cross-reference integrity。单一视图自洽不等于系统自洽。
    本项目事故：climb 写完却被门禁报 STUB；EXEC 里两个 ID 指向同一函数。
    """
    import subprocess
    p = os.path.join(ROOT, "tools", "consistency.py")
    if not os.path.exists(p):
        return []
    try:
        r = subprocess.run([sys.executable, p], capture_output=True,
                           text=True, timeout=300)
    except Exception:                                  # noqa: BLE001
        return []
    return [l.strip() for l in (r.stdout or "").splitlines()
            if l.strip().startswith("[R14")]


def _report(rows, problems):
    """一次打印全部问题，多失败一起报，不停在第一个。"""
    print(f"{'包':<8}{'文件':<18}{'行数':>6}  {'尺寸':<5}契约  直接依赖")
    for r in sorted(rows):
        print(f"{r[0]:<8}{r[1]:<18}{r[2]:>6}  {r[3]:<5}{r[4]}     {r[5]}")
    print()
    c = _dl.report_debt(problems)
    print(f"\n合计 {len(rows)} 个小模块，"
          f"新增 {c['fresh']} 个问题，已知债务 {c['debt']} 项，"
          f"到期 {c['overdue']} 项，陈旧 {c['stale']} 项")


def _dir_members(cur):
    """单个目录的直接成员数：直接 .py 子模块 + 直接子包（有 __init__.py）。"""
    fs = [f for f in os.listdir(cur) if f.endswith(".py") and f != "__init__.py"]
    sp = [x for x in os.listdir(cur)
          if os.path.isfile(os.path.join(cur, x, "__init__.py"))]
    return len(fs) + len(sp)


def _direct_member_counts():
    """包条目 = 直接成员数（直接子模块 + 直接子包），不递归累加。

    为什么改口径: 递归计数会把"每个子包各 8 个模块、全部合规"的父包
    算成 8+8+8=24 而误判为上帝包（最小复现见 tools/repro.py）。
    重复计数不是上帝包——上帝包的判据是"单个包直接挂了太多职责"。
    """
    out = {p: 0 for p in PKGS}
    for top in PKGS:
        d = os.path.join(ROOT, top)
        if not os.path.isdir(d):
            continue
        for cur, dirs, _ in os.walk(d):
            if "__pycache__" in cur:
                continue
            rel = os.path.relpath(cur, d)
            node = top if rel == "." else top + "." + rel.replace(os.sep, ".")
            out[node] = _dir_members(cur)
    return out


def main():
    """编排：建依赖图 → 逐文件扫描 → 包粒度汇总 → 出报告。"""
    files = list(walk_py())
    graph = {node_of(f): {f"{p}.{m}" for p, m in edges(f)} for f in files}
    counts = _direct_member_counts()
    problems, rows = [], []
    for f in files:
        pkg, row, out = _scan_file(f, graph)
        rows.append(row)
        problems += out
    # 入度: 有多少个其他包依赖它（判断原子层 vs 孤包）
    rdep = {}
    for _f, deps in graph.items():
        src = node_of(_f).split(".")[0]
        for d in deps:
            tgt = d.split(".")[0]
            if tgt != src:
                rdep.setdefault(tgt, set()).add(src)
    rdep = {k: len(v) for k, v in rdep.items()}
    problems = _SYNTAX_ERRS + problems        # R0 置顶：坏文件绝不当"零问题"
    problems += (_check_pkg_counts(counts, rdep) + _check_layer_exhaustive(counts)
                 + _check_importable()
                 + _check_provenance()
                 + _check_judge_power() + _check_cross_consistency())
    _report(rows, problems)
    # 未到期的已知债务不算失败（否则债务等于没豁免）；到期/陈旧/新增问题才算
    _d, fresh, overdue, stale = _dl.split_debt(problems)
    return 1 if fresh or overdue or stale else 0


if __name__ == "__main__":
    sys.exit(main())
