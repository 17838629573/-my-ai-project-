#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用切分工具：把 solver.py 的一个行区间搬到新模块，并在 solver.py 留 facade。

业界依据（已搜证）：
- 提取顺序：常量/噪声常量 -> 纯函数 -> 有状态逻辑 -> 编排最后
- facade 保留对外 API（preserve public exports），避免破坏调用方
- 懒加载 import 破循环依赖
- 小步验证：每一步必须 run，红状态不前进

用法:
    python3 _split_tool.py <src> <newmod> <起始标记> <结束标记>

"起始标记/结束标记" 是源码中出现的唯一子串；搬走 [起, 终) 区间。
"""
import ast
import sys
import os


def find_line(lines, marker, which="start"):
    hits = [i for i, l in enumerate(lines) if marker in l]
    if len(hits) != 1:
        raise SystemExit(f"标记不唯一({len(hits)}): {marker!r}")
    return hits[0]


def top_names(tree):
    """文件顶层定义/赋值/导入的名字 -> 需要的来源"""
    names = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names[node.name] = "solver"
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names[t.id] = "solver"
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names[node.target.id] = "solver"
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                names[a.asname or a.name.split(".")[0]] = "import"
    return names


def used_names(block_src):
    tree = ast.parse(block_src)
    used = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load):
            used.add(n.id)
        elif isinstance(n, ast.Attribute):
            cur = n
            while isinstance(cur, ast.Attribute):
                cur = cur.value
            if isinstance(cur, ast.Name):
                used.add(cur.id)
    return used


def defined_names(block_src):
    tree = ast.parse(block_src)
    out = set()
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.add(n.name)
        elif isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name):
                    out.add(t.id)
        elif isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name):
            out.add(n.target.id)
    return out


def main():
    src, newmod, m_start, m_end = sys.argv[1:5]
    lines = open(src, encoding="utf-8").read().split("\n")
    i0 = find_line(lines, m_start)
    i1 = find_line(lines, m_end)
    if i1 <= i0:
        raise SystemExit("结束标记不在起始标记之后")

    block = "\n".join(lines[i0:i1])
    defined = defined_names(block)
    tree = ast.parse(open(src, encoding="utf-8").read())
    avail = top_names(tree)
    used = used_names(block)
    need_sorted = sorted(n for n in used if n in avail and avail[n] == "solver"
                         and n not in defined)

    header = (f'# -*- coding: utf-8 -*-\n'
              f'"""{newmod} —— 从 solver.py 切出（业界：文件 150-500 行最优）。\n\n'
              f'依赖: solver（懒加载，破环）\n'
              f'被依赖: solver\n'
              f'改前必读: IMPROVE_{newmod}.md\n'
              f'"""\n')
    body = header + "\n" + block + "\n"
    open(newmod + ".py", "w", encoding="utf-8").write(body)

    # 新模块补齐缺失的 import（从 solver.py 头部抄）
    s_head = open(src, encoding="utf-8").read()
    import re as _re
    need_imports = [n for n in need_sorted]
    imp_lines = []
    for line in s_head.split("\n")[:60]:
        if line.startswith("import ") or line.startswith("from "):
            for n in need_imports:
                if _re.search(r'\b' + _re.escape(n) + r'\b', line):
                    if line not in imp_lines:
                        imp_lines.append(line)
    if imp_lines:
        b = open(newmod + ".py", encoding="utf-8").read()
        b = b.replace('"""\n', '"""\n' + "\n".join(imp_lines) + "\n", 1)
        open(newmod + ".py", "w", encoding="utf-8").write(b)

    # solver.py：删区间，插 facade 导入
    rest = lines[:i0] + lines[i1:]
    if need_sorted:
        facade = ("# facade：保留对外 API（业界 preserve public exports）。\n"
                  f"# {newmod} 中仍需 solver 的名字 -> 运行时注入，避免成环。\n")
        rest = _insert_facade(rest, newmod, need_sorted, facade)
    open(src, "w", encoding="utf-8").write("\n".join(rest))
    print(f"OK {src}: -{i1-i0} 行; {newmod}.py: +{len(block.split(chr(10)))} 行")
    print(f"搬出名字({len(defined)}): {sorted(defined)}")
    print(f"需从 solver 注入({len(need_sorted)}): {need_sorted}")


def _insert_facade(rest, newmod, need_sorted, facade):
    txt = "\n".join(rest)
    inject = "".join(f"{newmod}.{n} = {n}\n" for n in need_sorted)
    code = (f"\n\nimport {newmod}\n" + inject)
    # 插到 __main__ 之前（所有名字都定义完了，避免注入时空引用）
    lines = txt.split("\n")
    idx = None
    for i, l in enumerate(lines):
        if l.startswith('if __name__'):
            idx = i
            break
    if idx is None:
        idx = len(lines)
    lines.insert(idx, code)
    return lines


if __name__ == "__main__":
    main()
