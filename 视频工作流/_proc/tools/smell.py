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
            if f.endswith(".py"):
                yield os.path.join(root, f)


def _rel(p):
    return os.path.relpath(p, _PROC).replace("\\", "/")


def _is_pass_only(body):
    """except 分支是不是只有 pass / 只有一句无副作用语句。"""
    if len(body) != 1:
        return False
    n = body[0]
    return isinstance(n, ast.Pass)


def check_file(path):
    """对单个文件跑全部 S 规则，返回问题列表。"""
    rel = _rel(path)
    out = []
    try:
        src = io.open(path, encoding="utf-8").read()
        tree = ast.parse(src)
    except (SyntaxError, UnicodeDecodeError):
        return out

    # S01 静默异常 + S04 复制粘贴（需要函数作用域信息）
    for node in ast.walk(tree):
        if isinstance(node, ast.ExceptHandler) and _is_pass_only(node.body):
            out.append("[S01 静默异常] %s:%d except 分支只有 pass，错误被吞掉"
                       % (rel, node.lineno))
        # S05 可变默认参数
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for d in list(node.args.defaults) + [d for d in node.args.kw_defaults if d]:
                if isinstance(d, (ast.List, ast.Dict, ast.Set)):
                    out.append("[S05 可变默认参数] %s:%d %s() 默认值为可变对象"
                               % (rel, node.lineno, node.name))

    # S04 复制粘贴/漏改：引用了全文件范围内从未被绑定的名字
    # 先收集整个文件的所有"绑定"（全局收集，不只模块顶层，避免闭包/中部常量误报）
    bound = set()
    star = False          # 有 from x import * 则本文件无法静态判定，S04 整体跳过
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and any(a.name == "*" for a in n.names):
            star = True
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            bound.add(n.id)                      # 任意赋值/for 目标/with as
        elif isinstance(n, ast.arg):
            bound.add(n.arg)                     # 含嵌套函数的参数
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(n.name)
        elif isinstance(n, ast.ExceptHandler) and n.name:
            bound.add(n.name)                    # except ... as e
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names:
                bound.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.alias):
            bound.add((n.asname or n.name).split(".")[0])
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            bound.update(n.names)
    for node in ([] if star else ast.walk(tree)):
        if not isinstance(node, ast.FunctionDef):
            continue
        used = {n.id for n in ast.walk(node)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}
        undef = used - bound - _BUILTINS - {"self", "cls"}
        undef = {u for u in undef if u.isidentifier() and not u.startswith("__")}
        for name in sorted(undef):
            out.append("[S04 未定义引用] %s:%d %s() 用了全文件未绑定的名字 '%s'"
                       % (rel, node.lineno, node.name, name))

    # S02 判据恒真 + S03 自检空转 + S08 阈值失真
    for _n in ast.walk(tree):
        for _c in ast.iter_child_nodes(_n):
            _c._ps_parent = _n

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name != "self_check":
            continue
        # S03 自检空转：return 里是空列表/空元组，或函数体极短
        for n in ast.walk(node):
            if isinstance(n, ast.Return) and isinstance(n.value, (ast.List, ast.Tuple)):
                if len(n.value.elts) == 0:
                    out.append("[S03 自检空转] %s:%d self_check 返回空列表，等于没检查"
                               % (rel, n.lineno))
        # S02 判据恒真：元组/列表里出现裸 True
        for n in ast.walk(node):
            if isinstance(n, ast.Constant) and n.value is True:
                # 排除 return True 这种正常写法
                if isinstance(getattr(n, "_parent_stmt", None), ast.Return):
                    continue
                # 只认 append(("名", True)) 这类把判据写成常量的写法
                par = getattr(n, "_ps_parent", None)
                if isinstance(par, ast.Tuple) and len(par.elts) >= 2 and par.elts[1] is n:
                    out.append("[S02 判据恒真] %s:%d self_check 把判据写成常量 True"
                               % (rel, n.lineno))

    # S06 硬编码路径
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            v = node.value
            if "\n" in v or len(v) > 120:
                continue          # 多行/超长串是样本或文档，不是路径
            if _ABS_RE.search('"%s"' % v):
                out.append("[S06 硬编码路径] %s:%d 写死绝对路径 '%s'"
                           % (rel, node.lineno, node.value[:48]))

    # S07 浮点相等：== 两侧有一侧是除法/乘法浮点运算
    for node in ast.walk(tree):
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            op = node.ops[0]
            if isinstance(op, (ast.Eq, ast.NotEq)):
                sides = [node.left] + list(node.comparators)
                for s in sides:
                    is_float = isinstance(s, ast.BinOp) and isinstance(
                        s.op, (ast.Div, ast.Mult))
                    if not is_float and isinstance(s, ast.Constant):
                        is_float = isinstance(s.value, float)
                    if is_float:
                        out.append("[S07 浮点相等] %s:%d 用 %s 比较浮点运算结果"
                                   % (rel, node.lineno,
                                      "==" if isinstance(op, ast.Eq) else "!="))
                        break

    # S08 阈值失真：self_check 里出现 >1e3 的阈值常量（对物理/几何判据不现实）
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "self_check":
            for n in ast.walk(node):
                if isinstance(n, ast.Compare):
                    for c in n.comparators:
                        if isinstance(c, ast.Constant) and isinstance(c.value, float):
                            if c.value > 1e3:
                                out.append(
                                    "[S08 阈值失真] %s:%d self_check 阈值 %.0e 过大，"
                                    "判据形同虚设" % (rel, n.lineno, c.value))
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
    """自检：造一个含各类异味的样本，验证规则真能抓到。"""
    sample = '''# 契约: proc/_smell_probe
# -*- coding: utf-8 -*-
import math


def f(xs=[]):
    try:
        return 1 / 0
    except Exception:
        pass


def g(a, b):
    return a / r


def self_check():
    if True:
        return []
    out = []
    out.append(("t", True))
    out.append(("big", abs(math.pi - 3.14) < 1e6))
    out.append(("eq", f([]) == 1.0))
    return out
'''
    p = os.path.join(_PROC, "_smell_probe.py")
    io.open(p, "w", encoding="utf-8").write(sample)
    try:
        hits = check_file(p)
    finally:
        if os.path.exists(p):
            os.remove(p)
    cats = {"S01": False, "S02": False, "S03": False,
            "S04": False, "S05": False, "S08": False}
    for h in hits:
        for k in cats:
            if h.startswith("[%s" % k):
                cats[k] = True
    return [(k, v) for k, v in sorted(cats.items())]


def main(argv):
    out = collect()
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
