# 契约: proc/gen_api
#   一句话: 从契约块与能力装饰器自动生成 API.md，补齐"只有契约块、无接口文档"的缺口
#   输入: _proc 下全部 .py（契约块一句话 + @capability 装饰器 + 公开函数签名）
#   输出: _proc/API.md —— 分层接口手册（AI 可直接查"哪个能力能用、签名长什么样"）
#   依赖: 仅标准库（os/re/ast/json），不依赖 numpy/PIL，保证门禁环境下也能跑
#   被依赖: Makefile(api) / run.sh(api) / README 第四节
#   约束: 本文件行数须落在 R2 的 50~500 区间；生成结果只增不改人工注释段
#   校验入口: python3 gen_api.py（末尾打印生成条数，0 条即失败）
"""生成 API.md —— 让能力接口不必读源码就能查。

为什么单独于 gen_index.py:
  INDEX.md 回答"有哪些文件、各自负责什么"（面向人，按目录树组织）；
  API.md   回答"能调什么、怎么调"（面向调用方/AI，按能力与函数签名组织）。
  两者数据源相同（契约块），但受众与组织方式不同，混一份会两边都不好用。

抽取三样东西:
  1. 每模块的一句话职责（复用 gen_index 的契约块正则口径）
  2. @capability(name, source=..., group=...) —— 能力名/出处/分类/落点文件
  3. 顶层 def 的公开函数签名 —— 参数名与默认值，不抽函数体

不抽什么:
  私有函数（下划线开头）、类内部方法、局部变量。
  理由: API 手册只承诺稳定可调用面，抽出内部实现反而锁死重构空间。
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SKIP = {"_bak", "__pycache__", "_archive_文档_旧链路"}

# 与 gen_index.py 同一口径：只认文件头部的"一句话"行
ONE_LINER = re.compile(r"一句话[:：]\s*(.+)")
# @capability(...) 可能跨多行，先抓首个字符串字面量当名字
CAP_HEAD = re.compile(r"@capability\(\s*[\"']([^\"']+)[\"']")


def iter_py():
    """遍历 _proc 下全部 .py，返回排序后的绝对路径列表（铁律5：结果不依赖遍历顺序）。"""
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP)
        for fn in sorted(filenames):
            if fn.endswith(".py") and fn != "__init__.py":
                out.append(os.path.join(dirpath, fn))
    return sorted(out)


def one_liner(path):
    """取文件头部契约块的一句话职责；取不到返回占位串，不静默跳过。"""
    with open(path, encoding="utf-8", errors="replace") as fh:
        head = fh.read(4000)
    m = ONE_LINER.search(head)
    if m:
        return m.group(1).strip()
    return "（缺一句话职责）"


def rel(path):
    return os.path.relpath(path, ROOT).replace(os.sep, "/")


def scan_capabilities(path, text):
    """用 AST 抽 @capability 装饰器：能力名、source、group。"""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            if not isinstance(dec, ast.Call):
                continue
            fn = dec.func
            name = getattr(fn, "id", None) or getattr(fn, "attr", None)
            if name != "capability":
                continue
            out.append(_cap_from_decorator(dec, text, node))
    return out


def _cap_kw(dec):
    """从 @capability(...) 的关键字参数里取 source / group。"""
    got = {"source": "", "group": ""}
    for kw in dec.keywords:
        if kw.arg in got and isinstance(kw.value, ast.Constant):
            got[kw.arg] = str(kw.value.value)
    return got


def _cap_from_decorator(dec, text, node):
    """把一个 @capability 装饰器节点解析成能力字典。"""
    cap = {"name": "", "line": node.lineno}
    cap.update(_cap_kw(dec))
    if dec.args and isinstance(dec.args[0], ast.Constant):
        cap["name"] = str(dec.args[0].value)
    if not cap["name"]:
        m = CAP_HEAD.search(text)
        cap["name"] = m.group(1) if m else node.name
    return cap


def scan_public_funcs(path, text):
    """抽顶层公开函数签名（不含下划线开头），只取名字与参数，不取函数体。"""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    out = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef) or node.name.startswith("_"):
            continue
        out.append(_sig_of(node))
    return out


def _sig_args(node):
    """拼参数串，带默认值的写成 name=default。"""
    args = [a.arg for a in node.args.args]
    if node.args.defaults:
        pos = node.args.args[len(node.args.defaults):]
        for a, d in zip(pos, node.args.defaults):
            args[args.index(a.arg)] = "%s=%s" % (a.arg, ast.unparse(d))
    return args


def _sig_of(node):
    """把一个顶层函数节点变成 (名字, 签名, 行号, 首行文档)。"""
    args = _sig_args(node)
    ret = ast.unparse(node.returns) if node.returns else ""
    tail = " -> " + ret if ret else ""
    doc = (ast.get_docstring(node) or "").split("\n")[0].strip()
    return (node.name, "(%s)%s" % (", ".join(args), tail), node.lineno, doc)


def build():
    """扫全部文件，返回 (能力列表, 模块列表)。"""
    caps, mods = [], []
    for path in iter_py():
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
        r = rel(path)
        for c in scan_capabilities(path, text):
            c["file"] = r
            caps.append(c)
        funcs = scan_public_funcs(path, text)
        if funcs:
            mods.append((r, one_liner(path), funcs))
    caps.sort(key=lambda c: (c["group"], c["name"]))
    mods.sort()
    return caps, mods


def by_group(caps):
    g = {}
    for c in caps:
        g.setdefault(c["group"] or "未分类", []).append(c)
    return dict(sorted(g.items()))


def render(caps, mods):
    L = ["# API 手册（自动生成）", "",
         "> 由 `gen_api.py` 从契约块与 `@capability` 装饰器抽取，**改代码后需重跑**。",
         "> 人工编辑会在下次生成时被覆盖；要长期保留的说明请写进各文件的契约块。", "",
         "## 一、能力索引（%d 项）" % len(caps), "",
         "能力名可直接喂给 `beat.Timeline`；出处写在 `source` 参数里，空出处需先补再调用。", ""]
    for grp, items in by_group(caps).items():
        L.append("### %s（%d）" % (grp, len(items)))
        L.append("")
        L.append("| 能力 | 出处 | 落点 |")
        L.append("|---|---|---|")
        for c in items:
            src = c["source"] or "**缺出处**"
            src = src.replace("|", "/").split("\n")[0][:90]
            L.append("| `%s` | %s | `%s:%d` |" % (c["name"], src, c["file"], c["line"]))
        L.append("")
    L += ["## 二、模块公开面（%d 个模块）" % len(mods), "",
          "只列顶层公开函数（下划线开头为内部实现，不承诺稳定）。", ""]
    for r, one, funcs in mods:
        L.append("### `%s`" % r)
        L.append("")
        L.append(one)
        L.append("")
        for name, sig, line, doc in funcs:
            tail = "　—　" + doc if doc else ""
            L.append("- `%s%s`　`L%d`%s" % (name, sig, line, tail))
        L.append("")
    return "\n".join(L)


def main():
    caps, mods = build()
    text = render(caps, mods)
    out = os.path.join(ROOT, "API.md")
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(text)
    nsrc = sum(1 for c in caps if c["source"])
    print("API.md 已生成：能力 %d 项（有出处 %d / 缺出处 %d），模块 %d 个"
          % (len(caps), nsrc, len(caps) - nsrc, len(mods)))
    # 铁律2：判定靠命令输出。0 条能力说明抽取器失效，必须非零退出
    if not caps:
        print("失败：未抽到任何能力，抽取器失效")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
