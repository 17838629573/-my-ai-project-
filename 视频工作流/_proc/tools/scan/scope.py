# 契约: proc/tools/scan/scope
#   一句话: 名字作用域分析：提取绑定名/形参归属/未定义引用，供 smell 的 S04 规则使用
#   完整契约见 tools/__init__.py
#   依据: ast 官方 Name Binding & Resolution（作用域：module/function/class）
# -*- coding: utf-8 -*-
"""名字作用域分析 —— 从 smell.py 拆出。

为什么单独成模块:
  这一段只回答「某个名字在全文件范围内有没有被绑定、属于哪个函数的形参」，
  与「这是不是异味」无关。把它和规则表混在一起会让 smell.py 超过 500 行
  模块红线（实测 512 行），而按职责切分后两边都回到红线内。
"""
import ast
import builtins

_BUILTINS = set(dir(builtins))



# 绑定名提取规则表：(节点类型, 提取函数)。顺序即优先级，与原 elif 链一致。
def _has_star_import(tree):
    """文件是否含 `from x import *`。

    有星号导入时静态不可判定（绑定名取决于被导入模块），调用方应整体跳过本规则。
    """
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names):
            return True
    return False


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


