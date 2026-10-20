# 契约: proc/tools/scan/capsrc
#   一句话: R11 用 AST 取 @capability 的名字与出处，检出「无出处」的能力。
#   完整契约见 tools/__init__.py
#   依据: 装饰器既有位置参数也有 source= 关键字，还有跨行写法，
#         正则会漏掉后两种，导致无出处的能力静默通过——故用 AST 不用正则。
#   下沉原因: 该规则置于 check.py 时其达 502 行 > R2 上限 500，
#         与 debtledger.py 同因下沉。判据与阈值一律由调用方传入。
# -*- coding: utf-8 -*-
"""R11 能力出处检查（从 check.py 拆出，避免其超纲 R2>500）。"""
import ast
import os


def _cap_name(d):
    """取 @capability 第一个位置参数作为能力名。"""
    if d.args and isinstance(d.args[0], ast.Constant):
        return d.args[0].value
    return "?"


def _cap_source(d):
    """取出处：位置参数与 source= 关键字都要认（项目内两种写法都存在）。"""
    source = ""
    if len(d.args) > 1 and isinstance(d.args[1], ast.Constant):
        source = str(d.args[1].value)
    for kw in d.keywords:
        if kw.arg == "source" and isinstance(kw.value, ast.Constant):
            source = str(kw.value.value)
    return source


def cap_source_of(d):
    """从 @capability(...) 调用节点取 (名字, 出处)；非该装饰器返回 None。

    位置参数与 source= 关键字都要认——项目中两种写法都存在，
    只认一种会让无出处的能力静默通过。
    """
    if not isinstance(d, ast.Call):
        return None
    fn = d.func
    if not (isinstance(fn, ast.Name) and fn.id == "capability"):
        return None
    return _cap_name(d), _cap_source(d)



def caps_without_source(path, min_source):
    """返回 (问题列表, 语法错误串)。语法错误串为空表示解析正常。

    语法错误不静默返回空：调用方须照原样上报，否则坏文件会被判零问题。
    """
    try:
        tree = ast.parse(open(path, encoding="utf-8").read())
    except SyntaxError as e:
        return [], ("[R0 语法错误] %s:%s %s"
                    % (path, getattr(e, "lineno", "?"), e.msg))
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for d in node.decorator_list:
            got = cap_source_of(d)
            if got is None:
                continue
            name, source = got
            if len(source.strip()) < min_source:
                out.append("[R11 能力无出处] %s (%s)"
                           % (name, os.path.basename(path)))
    return out, ""


def self_check():
    """自检：三种装饰器写法都要取到出处，缺失的必须报出。"""
    import tempfile
    src = (
        "def capability(*a, **k):\n    def _d(f):\n        return f\n    return _d\n"
        "\n"
        "@capability('a1', '依据: 位置参数写出处')\n"
        "def f1():\n    pass\n"
        "\n"
        "@capability('a2', source='依据: 关键字写出处')\n"
        "def f2():\n    pass\n"
        "\n"
        "@capability('a3', '短')\n"
        "def f3():\n    pass\n"
    )
    fd, p = tempfile.mkstemp(suffix=".py")
    os.write(fd, src.encode("utf-8"))
    os.close(fd)
    try:
        out, err = caps_without_source(p, 8)
        ok = (err == "" and len(out) == 1 and "a3" in out[0]
              and "f1" not in "".join(out) and "f2" not in "".join(out))
        return ok, {"out": out, "err": err}
    finally:
        os.unlink(p)
