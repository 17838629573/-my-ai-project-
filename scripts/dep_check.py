#!/usr/bin/env python3
"""依赖图验证：读 deps.md 声明，扫代码实际 import，查三类问题。
用法：在项目根目录跑 python3 scripts/dep_check.py
退出码：0=通过（可有 warning）；1=有 error（循环依赖 / 未声明依赖），应交用户裁定。"""
import os, re, sys

DEPS_FILE = "deps.md"
CODE_EXT = (".py", ".js", ".jsx", ".ts", ".tsx")
RUNTIME_TAG = "[runtime]"   # 行尾标记：跨语言/跨进程运行时契约，跳过代码存在性验证（仍查循环依赖）

def load_deps():
    """解析 deps.md：每行 `模块 -> 依赖A, 依赖B`；# 开头为注释；括号为行内注释；
    行尾 [runtime] 的依赖不要求代码 import 可见。
    返回 (graph, runtime, 主模块集合)；主模块 = 出现在 -> 左侧的模块，才有代码归属权。"""
    graph, runtime, mods_main = {}, {}, set()
    if not os.path.isfile(DEPS_FILE):
        print(f"[error] 找不到 {DEPS_FILE}（split 步骤应产出）"); sys.exit(1)
    for line in open(DEPS_FILE, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "->" not in line:
            continue
        mod, deps = line.split("->", 1)
        mod = mod.strip()
        mods_main.add(mod)
        graph.setdefault(mod, set())
        runtime.setdefault(mod, set())
        for d in re.split(r",", deps.strip()):   # 逗号分隔模块；[runtime] 与括号注释贴模块名后
            d = d.strip()
            if not d:
                continue
            is_runtime = d.endswith(RUNTIME_TAG)
            if is_runtime:
                d = d[: -len(RUNTIME_TAG)].strip()
            d = re.sub(r"\([^)]*\)", "", d).strip()   # 剥括号注释
            if not d:
                continue
            graph[mod].add(d)
            if is_runtime:
                runtime[mod].add(d)
    for ds in list(graph.values()):
        for d in ds:
            graph.setdefault(d, set())
            runtime.setdefault(d, set())
    return graph, runtime, mods_main

def _segs(rel):
    """相对路径去扩展名后拆段：'backend/app/api/login.py' -> ['backend','app','api','login']"""
    for ext in CODE_EXT:
        if rel.endswith(ext):
            rel = rel[: -len(ext)]
            break
    return rel.split("/")

_PAT_FROM = re.compile(r"""from\s+['"]?([A-Za-z_][\w./-]*)\s+import\s+([^\n;]+)""")
_PAT_IMP = re.compile(r"""import\s+['"]?([A-Za-z_][\w./-]*(?:\s*,\s*['"]?[A-Za-z_][\w./-]*)*)""")
_PAT_REQ = re.compile(r"""require\(\s*['"]([A-Za-z_][\w./-]*)""")
_PAT_IMP_FROM = re.compile(r"""import\s+[^;\n]*?\bfrom\s+['"]([A-Za-z_][\w./-]*)""")   # ESM: import {...} from "mod"

def collect_tokens(text, modules):
    """提取可能指向本项目模块的 import token。
    from X import Y：X 的剥前缀候选能匹配模块 → 只依赖 X（Y 是名字/属性，忽略）；
    匹配不到（如 from pkg import submodule）→ Y 列表项当候选。
    独立 import a, b：逐项当候选。require('X') / import {...} from "X"：X 当候选。"""
    toks = set()
    for m in _PAT_FROM.finditer(text):
        x = m.group(1).strip()
        xparts = re.split(r"[./]", x)
        if any(".".join(xparts[i:]) in modules for i in range(len(xparts))):
            toks.add(x)
        else:
            for item in re.split(r"[,\s]+", m.group(2).strip()):
                item = item.strip()
                if item and not item.startswith("*") and re.match(r"^[A-Za-z_][\w./-]*$", item):
                    toks.add(item)
    text2 = _PAT_FROM.sub("", text)   # 剔掉 from 语句，避免 import 列表被当独立 import
    for m in _PAT_IMP.finditer(text2):
        for item in re.split(r"[,\s]+", m.group(1).strip()):
            if item and re.match(r"^[A-Za-z_][\w./-]*$", item):
                toks.add(item)
    for m in _PAT_REQ.finditer(text):
        toks.add(m.group(1).strip())
    for m in _PAT_IMP_FROM.finditer(text2):
        toks.add(m.group(1).strip())
    return toks

def _match_pos(ms, fsegs):
    """ms 在 fsegs 中的最后匹配位置（保序子序列）；不匹配返回 -1。"""
    idx = -1
    for s in ms:
        while idx + 1 < len(fsegs) and fsegs[idx + 1] != s:
            idx += 1
        if idx + 1 >= len(fsegs):
            return -1
        idx += 1
    return idx

def scan_imports(modules, owner_modules):
    """扫代码里实际出现的模块间依赖：返回 {模块: set(实际依赖)}。
    owner_modules = 主模块集合（出现在 deps.md -> 左侧），才有代码归属权；
    仅作依赖目标（如 [runtime] 契约目标）的模块不参与归属。"""
    found = {m: set() for m in modules}
    msegs = {m: m.replace(".", "/").split("/") for m in owner_modules}
    for root, _, files in os.walk("."):
        if any(x in root for x in (".git", "node_modules", "__pycache__", "scripts")):
            continue
        for f in files:
            if not f.endswith(CODE_EXT):
                continue
            path = os.path.join(root, f)
            rel = os.path.relpath(path, ".").replace(os.sep, "/")
            fsegs = _segs(rel)
            # 归属：模块名段是文件路径段的保序子序列；选最后匹配位置最靠后的（最贴近文件的模块最精确）
            owner, owner_pos = None, -1
            for m in owner_modules:
                ms = msegs[m]
                if len(ms) > len(fsegs):
                    continue
                pos = _match_pos(ms, fsegs)
                if pos >= 0 and pos > owner_pos:
                    owner, owner_pos = m, pos
            if not owner:
                continue
            try:
                text = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for token in collect_tokens(text, modules):
                # token 可能是 "core.parser"（包内模块），逐级剥前缀生成候选匹配模块名
                parts = re.split(r"[./]", token)
                for i in range(len(parts)):
                    cand = ".".join(parts[i:])
                    if cand in modules and cand != owner:
                        found[owner].add(cand)
    return found

def find_cycles(graph):
    cycles, stack, state = [], [], {}
    def dfs(n):
        state[n] = 1
        stack.append(n)
        for d in graph.get(n, ()):
            if state.get(d) == 1:
                cycles.append(stack[stack.index(d):] + [d])
            elif state.get(d, 0) == 0:
                dfs(d)
        stack.pop()
        state[n] = 2
    for n in graph:
        if state.get(n, 0) == 0:
            dfs(n)
    return cycles

def main():
    graph, runtime, mods_main = load_deps()
    mods = set(graph)
    errors, warns = [], []

    for c in find_cycles(graph):
        errors.append("循环依赖: " + " -> ".join(c))

    indeg = {m: 0 for m in mods}
    for m, ds in graph.items():
        for d in ds:
            indeg[d] = indeg.get(d, 0) + 1
    for m in mods:
        if not graph[m] and indeg.get(m, 0) == 0 and len(mods) > 1:
            warns.append(f"孤立模块: {m}（既不依赖谁也无人调用，确认是否多余）")

    actual = scan_imports(mods, mods_main)
    for m, ds in actual.items():
        for d in ds:
            if d not in graph.get(m, set()):
                errors.append(f"图与代码不一致: {m} 实际依赖 {d}，但 deps.md 未声明")
    for m, ds in graph.items():
        for d in ds:
            if d not in actual.get(m, set()):
                if d in runtime.get(m, set()):
                    continue   # 运行时契约（HTTP API / 数据库 Schema），代码中不见属正常
                warns.append(f"图与代码不一致: deps.md 声明 {m} -> {d}，代码中未见（动态引用可忽略）")

    print(f"模块数: {len(mods)}")
    for w in warns:
        print("[warn ]", w)
    for e in errors:
        print("[error]", e)
    if errors:
        print(f"\n{len(errors)} 个 error → 停下交用户裁定（补 deps.md / 改代码 / 确认例外）")
        sys.exit(1)
    print(f"\n依赖图验证通过（{len(warns)} 个 warning 可人工过目）")
    sys.exit(0)

if __name__ == "__main__":
    main()
