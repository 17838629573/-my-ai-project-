# 契约: proc/tools/smell
#   一句话: 代码异味检查：补 faultbench 实测暴露的 8 类静态盲区（静默异常/判据恒真/自检空转等）
#   完整契约见 tools/__init__.py
#   依据: faultbench(R18) 实测召回率仅 43%，8 类缺陷静态全漏；
#         ruff BLE001(blind except)、B006(可变默认参数)、PT009(assert True)；
#         pylint W0703(broad-except)、R0123(literal comparison)；
#         NASA/JPL 禁止吞异常与无断言的自检。
# -*- coding: utf-8 -*-
"""R18 代码异味检查 —— 补静态检错的盲区。

为什么单独成模块:
  check.py 管「结构」（依赖、行数、契约块），
  smell.py 管「语义」（这段代码是不是在骗人）。
  两者都靠 AST，但判据性质不同，混在一起会让规则表爆炸。

每条规则对应 faultbench 里一条实测 SURVIVED：
  S01 静默异常 ← F01   S02 判据恒真 ← F03   S03 自检空转 ← F14
  S04 复制粘贴 ← F06   S05 可变默认 ← F09   S06 硬编码路径 ← F11
  S07 浮点相等 ← F13   S08 阈值失真 ← F04
"""
import ast
import builtins
import io
import os
import re
import sys

_PROC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROC not in sys.path:
    sys.path.insert(0, _PROC)

# 硬编码路径特征：绝对路径，非 /usr、/proc 等系统目录
_BUILTINS = set(dir(builtins))
_ABS_RE = re.compile(r"""['"](/data/|/home/|/Users/|/tmp/[A-Za-z一-鿿]|C:\\\\)""")


def _walk():
    for root, dirs, files in os.walk(_PROC):
        dirs[:] = [d for d in dirs
                   if d not in ("__pycache__", ".git", "_bak", "_archive_文档_旧链路")]
        for f in sorted(files):
            if not f.endswith(".py"):
                continue
            # 2026-10-10 修订: 曾把 `_canary_*` 一并排除，理由是残留污染。
            # 那是错的——它让 faultbench 的静态检出率从 100% 掉到 36%，
            # 基准本身失效却无人察觉。正确做法是保证 canary 不残留
            # （faultbench 已改 try/finally + atexit 无条件回收），
            # 而不是屏蔽对它的检测。夹具若在扫描窗口内被看到，报出来才是对的。
            # `_tmp_*` / `tmp_*.py` 是各工具自检临时生成的样本，仍排除。
            if f.startswith(("_tmp_", "tmp_")):
                continue
            yield os.path.join(root, f)


def _rel(p):
    return os.path.relpath(p, _PROC).replace("\\", "/")


def _is_pass_only(body):
    """except 分支是不是只有 pass / 只有一句无副作用语句。"""
    if len(body) != 1:
        return False
    n = body[0]
    return isinstance(n, ast.Pass)


def _scan_try_and_defaults(tree, rel):
    """S01 静默异常 + S05 可变默认参数。

    出处：S01 对应 Python 官方异常文档"except 吞异常是常见反模式"，以及
    flake8-bandit B110 try-except-pass；S05 对应 Python 官方教程
    "Default Parameter Values" —— 可变默认值在多次调用间共享。
    """
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and _is_pass_only(node.body):
            out.append("[S01 静默异常] %s:%d except 分支只有 pass，错误被吞掉"
                       % (rel, node.lineno))
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in list(node.args.defaults) + [d for d in node.args.kw_defaults if d]:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    out.append("[S05 可变默认参数] %s:%d %s() 默认值为可变对象"
                               % (rel, node.lineno, node.name))
    return out


def _has_star_import(tree):
    """文件是否含 `from x import *`。

    有星号导入时静态不可判定（绑定名取决于被导入模块），调用方应整体跳过本规则。
    """
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names):
            return True
    return False


# 绑定名提取规则表：(节点类型, 提取函数)。顺序即优先级，与原 elif 链一致。
_BIND_RULES = (
    (ast.Name, lambda n: {n.id} if isinstance(n.ctx, ast.Store) else None),
    (ast.arg, lambda n: {n.arg}),
    ((ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef), lambda n: {n.name}),
    (ast.ExceptHandler, lambda n: {n.name} if n.name else None),
    ((ast.Import, ast.ImportFrom),
     lambda n: {(a.asname or a.name).split(".")[0] for a in n.names}),
    (ast.alias, lambda n: {(n.asname or n.name).split(".")[0]}),
    ((ast.Global, ast.Nonlocal), lambda n: set(n.names)),
)

def _bound_names(node):
    """单个 AST 节点贡献的绑定名集合（表驱动，规则顺序与原 elif 链一致）。"""
    for kinds, get in _BIND_RULES:
        if isinstance(node, kinds):
            names = get(node)
            return set(names) if names else set()
    return set()

def _collect_bound(tree):
    """收集「文件级绑定集合」：Name.Store / 形参 / 定义名 / except as / import 别名。

    【拆自动机】原 _scan_undefined_names CCN=28，绝大部分复杂度来自这里
    的 elif 分支堆叠。抽出 _bound_names 后只剩 walk 调度，判定仍集中一处。
    """
    bound = set()
    for n in ast.walk(tree):
        bound.update(_bound_names(n))
    return bound


def _undef_in_func(node, bound):
    """单个函数里"用了但全文件从未绑定"的名字（排序后返回）。"""
    used = {n.id for n in ast.walk(node)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
    undef = used - bound - _BUILTINS - {"self", "cls"}
    return sorted(u for u in undef
                  if u.isidentifier() and not u.startswith("__"))

def _scan_undefined_names(tree, rel):
    """S04 复制粘贴/漏改：引用了全文件范围内从未被绑定的名字。

    【已修误报】判定必须放在"文件级绑定集合"上，不能按函数作用域：
    闭包与函数中段定义的常量会被误判成未绑定，曾一次报 417 条。
    另：有 `from x import *` 时静态不可判定，本规则整体跳过（不是降级）。
    """
    if _has_star_import(tree):
        return []
    bound = _collect_bound(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for name in _undef_in_func(node, bound):
            out.append(
                "[S04 未定义引用] %s:%d %s() 用了全文件未绑定的名字 '%s'"
                % (rel, node.lineno, node.name, name))
    return out


def _func_params(node):
    """函数的形参名集合（含 *args / **kwargs）。"""
    names = {a.arg for a in node.args.args + node.args.kwonlyargs}
    if node.args.vararg:
        names.add(node.args.vararg.arg)
    if node.args.kwarg:
        names.add(node.args.kwarg.arg)
    return names


def _enclosing(node, funcs):
    """包含 node 的外层函数（按行号区间判断嵌套），用于放过闭包合法引用。

    ast 不提供父指针，改用 end_lineno 区间判断包含关系；嵌套函数引用
    外层形参是合法的（闭包），不能报成复制粘贴。
    """
    lo = node.lineno
    hi = node.end_lineno or node.lineno
    return [f for f in funcs
            if f is not node and f.lineno <= lo
            and (f.end_lineno or f.lineno) >= hi]


def _module_scope(tree):
    """模块级绑定名：只看顶层语句，不下钻函数/类内部。

    2026-10-11 补：初版 ok 集合只有「本函数 + 外层函数」，漏了模块级变量，
    于是 motion/stage.py 的 tip() 合法引用模块级 bg/geom 被报成
    "用了 sheet() 的形参" —— 这正是既有 _scan_undefined_names 坚持用
    「文件级绑定集合」的原因，新规则必须同样尊重模块作用域。
    """
    names = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
            continue
        for c in ast.walk(n):
            names.update(_bound_names(c))
    return names


def _owner_of_param(name, node, funcs, encl):
    """第一个以 name 为形参、且不是 node 外层函数的函数名（没有则 None）。

    抽出内层查找是为了控 CCN：主循环里三层嵌套 + 多个 continue 会让
    _scan_param_leak 的 CCN 到 16（设计值上限 10），而这段查找逻辑
    本身是一个独立、可单独验证的小判定。
    """
    for other in funcs:
        if other is node or name not in _func_params(other):
            continue
        if other in encl:
            continue
        return other.name
    return None


def _scope_of(node, funcs):
    """本函数 + 所有外层函数可见的绑定名集合（放过闭包合法引用）。"""
    ok = set(_func_params(node))
    for n in ast.walk(node):
        ok.update(_bound_names(n))
    for anc in _enclosing(node, funcs):
        ok |= _func_params(anc)
        for n in ast.walk(anc):
            ok.update(_bound_names(n))
    return ok


def _loaded_names(node):
    """函数内以 Load 方式使用的名字集合。"""
    return {n.id for n in ast.walk(node)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}


def _scan_param_leak(tree, rel):
    """S04 复制粘贴/漏改（形参串台）：用了别的函数的形参。

    为什么单独一条：_scan_undefined_names 的判据是「全文件是否绑定过」，
    而 F06 注入的 `ratio(a,b){return a/r}` 里 r 是 area(r) 的形参——
    全文件确实绑定过，规则完全没有牙齿，基准如实报了 SURVIVED。
    复制粘贴的真实特征不是"未定义"，而是"用了非本作用域的形参"。

    误报防护（两次踩坑后定型）：可见集合必须包含
      ① 本函数自身绑定（漏了会误报 for 循环变量，一次 1130 条）
      ② 外层函数绑定（闭包）
      ③ 模块级绑定（漏了会误报模块级常量，stage.py tip() 中招）
    """
    funcs = [n for n in ast.walk(tree)
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    if len(funcs) < 2:
        return []
    mod = _module_scope(tree)
    out = []
    for node in funcs:
        ok = _scope_of(node, funcs)
        encl = _enclosing(node, funcs)
        used = _loaded_names(node) - ok - mod - _BUILTINS - {"self", "cls"}
        for name in sorted(used):
            owner = _owner_of_param(name, node, funcs, encl)
            if owner:
                out.append(
                    "[S04 未定义引用] %s:%d %s() 用了 %s() 的形参 '%s'，"
                    "疑似复制粘贴漏改" % (rel, node.lineno, node.name,
                                        owner, name))
    return out


def _empty_assigns(node):
    """{变量名 -> 行号}：本函数内被赋值为空 list/tuple 的变量。"""
    empties = {}
    for n in ast.walk(node):
        if not (isinstance(n, ast.Assign)
                and isinstance(n.value, (ast.List, ast.Tuple))
                and len(n.value.elts) == 0):
            continue
        for t in n.targets:
            if isinstance(t, ast.Name):
                empties[t.id] = n.lineno
    return empties


def _growth_lines(node):
    """{变量名 -> 最早的 append/extend/insert 行号}。"""
    grows = {}
    for n in ast.walk(node):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr in ("append", "extend", "insert")
                and isinstance(n.func.value, ast.Name)):
            continue
        v = n.func.value.id
        if v not in grows or n.lineno < grows[v]:
            grows[v] = n.lineno
    return grows


def _empty_and_growth(node):
    """收集 (空容器赋值变量 -> 行号, 变量 -> 最早 append 行号)。

    拆成 _empty_assigns / _growth_lines 两条独立收集：合在一起时本函数
    CCN=13 超设计值 10，而二者互不依赖，分开后各自可单独验证。
    """
    return _empty_assigns(node), _growth_lines(node)


def _sc_empty_return(node, rel):
    """S03 自检空转：self_check 返回空容器，等于没检查。

    2026-10-11 扩：原实现只认 `return []` 字面量，而 F14 注入的是
    `out = []` + `return out`（名字引用）—— 这恰是本项目 self_check 的
    通用写法，规则完全漏掉，基准如实报了 SURVIVED。
    现两种形态都认：空容器字面量；以及赋值为空容器的变量被 return，
    且对它的 append 全部排在 return 之后（死代码）或压根没有 append。
    """
    out = []
    empties, grows = _empty_and_growth(node)
    for n in ast.walk(node):
        if not isinstance(n, ast.Return):
            continue
        v = n.value
        if isinstance(v, (ast.List, ast.Tuple)) and len(v.elts) == 0:
            out.append("[S03 自检空转] %s:%d self_check 返回空容器，等于没检查"
                       % (rel, n.lineno))
        elif isinstance(v, ast.Name) and v.id in empties:
            g = grows.get(v.id)
            if g is None or g > n.lineno:
                out.append("[S03 自检空转] %s:%d self_check 返回空容器 %r"
                           "(赋值于 L%d，其后无有效 append)，等于没检查"
                           % (rel, n.lineno, v.id, empties[v.id]))
    return out


def _sc_const_true(node, rel):
    """S02 判据恒真：判据位写成常量 True（出处 PIT/mutmut 变异永远存活）。"""
    out = []
    for n in ast.walk(node):
        if not (isinstance(n, ast.Constant) and n.value is True):
            continue
        if isinstance(getattr(n, "_parent_stmt", None), ast.Return):
            continue
        par = getattr(n, "_ps_parent", None)
        if isinstance(par, ast.Tuple) and len(par.elts) >= 2 and par.elts[1] is n:
            out.append("[S02 判据恒真] %s:%d self_check 把判据写成常量 True"
                       % (rel, n.lineno))
    return out


def _sc_bad_thresh(node, rel):
    """S08 阈值失真：米制物理量的阈值 >1e3，判据形同虚设。"""
    out = []
    for n in ast.walk(node):
        if not isinstance(n, ast.Compare):
            continue
        for c in n.comparators:
            if isinstance(c, ast.Constant) and isinstance(c.value, float):
                if c.value > 1e3:
                    out.append(
                        "[S08 阈值失真] %s:%d self_check 阈值 %.0e 过大，"
                        "判据形同虚设" % (rel, n.lineno, c.value))
    return out


_SC_SCANNERS = (_sc_empty_return, _sc_const_true, _sc_bad_thresh)


def _scan_selfcheck(tree, rel):
    """S02 判据恒真 + S03 自检空转 + S08 阈值失真（只作用于 self_check）。

    出处：S02/S03 对应变异测试（PIT/mutmut）—— 判据写成常量 True 的变异体
    永远存活，等价于没有判据；S08 阈值 >1e3 对米制物理量不现实。
    """
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name != "self_check":
            continue
        for scan in _SC_SCANNERS:
            out.extend(scan(node, rel))
    return out


def _scan_abs_path(tree, rel):
    """S06：绝对路径常量（多行/超长串是样本或文档，不算路径）。"""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            if "\n" in v or len(v) > 120:
                continue          # 多行/超长串是样本或文档，不是路径
            if _ABS_RE.search('"%s"' % v):
                out.append("[S06 硬编码路径] %s:%d 写死绝对路径 '%s'"
                           % (rel, node.lineno, node.value[:48]))
    return out


def _is_float_expr(node):
    """该表达式是不是"浮点来源"：除法/乘法结果，或 float 常量。"""
    is_float = isinstance(node, ast.BinOp) and isinstance(
        node.op, (ast.Div, ast.Mult))
    if not is_float and isinstance(node, ast.Constant):
        is_float = isinstance(node.value, float)
    return is_float

def _scan_float_eq(tree, rel):
    """S07：== / != 比较浮点运算结果（IEEE 754，等值比较脆断）。"""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            op = node.ops[0]
            if isinstance(op, (ast.Eq, ast.NotEq)):
                for s in [node.left] + list(node.comparators):
                    if _is_float_expr(s):
                        out.append(
                            "[S07 浮点相等] %s:%d 用 %s 比较浮点运算结果"
                            % (rel, node.lineno,
                               "==" if isinstance(op, ast.Eq) else "!="))
                        break
    return out

def _scan_path_and_float_eq(tree, rel):
    """S06 硬编码绝对路径 + S07 浮点相等比较，两个独立扫描器逐条拼接。

    出处：S06 对应十二要素应用 III（配置存于环境）——写死 /data/... 会让
    仓库在别人机器上直接崩；S07 对应浮点算术 IEEE 754 与 Python 官方
    教程"Floating Point Arithmetic: Issues and Limitations"。
    """
    return _scan_abs_path(tree, rel) + _scan_float_eq(tree, rel)


def check_file(path):
    """对单个文件跑全部 S 规则，返回问题列表。

    拆分为 5 个 _scan_* 前本函数 123 行（R3 上限 50），且 S01/S05、S02/S03/S08
    两组规则混在一个 walk 里，改一条规则要读完整个函数。现按"规则族"分组，
    每条规则独占一个函数，扫描顺序与判据逐字保持，故行为不变
    （验证：全项目扫描输出条数与内容一致）。
    """
    rel = _rel(path)
    out = []
    try:
        src = io.open(path, encoding="utf-8").read()
        tree = ast.parse(src)
    except (SyntaxError, UnicodeDecodeError):
        return out
    out.extend(_scan_try_and_defaults(tree, rel))
    out.extend(_scan_undefined_names(tree, rel))
    out.extend(_scan_param_leak(tree, rel))
    # S02/S08 需要父子指针判断"常量出现在元组第二位"
    for _n in ast.walk(tree):
        for _c in ast.iter_child_nodes(_n):
            _c._ps_parent = _n
    out.extend(_scan_selfcheck(tree, rel))
    out.extend(_scan_path_and_float_eq(tree, rel))
    return out


def collect(target=None):
    """扫全项目（或指定目录）的代码异味。"""
    out = []
    for p in _walk():
        if target and target not in _rel(p):
            continue
        try:
            out.extend(check_file(p))
        except Exception as e:  # noqa: BLE001 —— 单文件失败不能吞掉整体
            out.append("[S00 检查器故障] %s: %s" % (_rel(p), e))
    return out


def self_check():
    """自检委托：语料与驱动在 tools/corpus/smell_selfcheck.py。

    拆走原因：样本+驱动约 40 行与扫描逻辑无关，内联会让本文件超 500 行红线。
    此前 self_check 缺 CLI 入口且无调用方（白写），现补 --self-check。
    """
    from tools.corpus import smell_selfcheck
    return smell_selfcheck.self_check()


def main(argv):
    if "--self-check" in argv:
        return 0 if self_check() else 1
    # --files=子串：只扫匹配的文件。faultbench 每条缺陷只需 canary 一个文件的
    # 结果，全项目扫描让 14 条缺陷跑不完单批时限，而超时又被当成"没抓到"。
    tgt = None
    for a in argv:
        if a.startswith("--files="):
            tgt = a.split("=", 1)[1]
    out = collect(target=tgt)
    if "--json" in argv:
        import json
        print(json.dumps(out, ensure_ascii=False, indent=2))
        return 1 if out else 0
    for ln in out:
        print(ln)
    print("-" * 60)
    print("代码异味合计 %d 条" % len(out))
    return 1 if out else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
