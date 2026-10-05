"""通用函数抽取工具：把源模块中指定函数搬到新模块，原模块留 wrapper 重导出。

用法:
    python _extract_tool.py <源模块> <新模块> <函数名1> [函数名2 ...]

原理（避免循环导入）:
    * 原模块中被搬走的函数替换为 wrapper，wrapper 内做"函数级 import"
      ——调用时才导入，此时源模块已完整初始化，无循环风险。
    * 新模块顶层 `from 源模块 import <被引用符号>`，显式列出，含下划线私有名。
"""
import ast
import sys
import os


def collect_top_defs(src):
    """顶层定义的函数/类/变量符号集合"""
    tree = ast.parse(src)
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name):
                    names.add(t.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def collect_refs(func_src, top_names):
    """函数体内引用了哪些顶层符号（含嵌套函数内）"""
    tree = ast.parse(func_src)
    refs = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
            if node.id in top_names:
                refs.add(node.id)
        elif isinstance(node, ast.Attribute):
            pass
    return refs


def get_import_block(src):
    """抽取源文件的顶层 import 区源码（到第一个非 import 语句为止）"""
    tree = ast.parse(src)
    lines = src.split("\n")
    out = []
    last = 0
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            start = node.lineno - 1
            end = node.end_lineno
            # 保留装饰器/注释略，直接取行
            out.extend(lines[start:end])
            last = end
    return "\n".join(out), last


def extract(src_module, new_module, func_names, dry=False):
    base = src_module[:-3] if src_module.endswith(".py") else src_module
    src_path = src_module if src_module.endswith(".py") else src_module + ".py"
    new_path = new_module if new_module.endswith(".py") else new_module + ".py"

    src = open(src_path, encoding="utf-8").read()
    tree = ast.parse(src)
    lines = src.split("\n")

    top_names = collect_top_defs(src)
    import_block, _ = get_import_block(src)

    # 取每个函数的源码段
    segs = {}
    all_refs = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in func_names:
                seg = ast.get_source_segment(src, node)
                segs[node.name] = seg
                all_refs |= collect_refs(seg, top_names)
    missing = [f for f in func_names if f not in segs]
    if missing:
        raise SystemExit(f"[FAIL] 未找到函数: {missing}")

    # 被搬走函数之间互相引用，不算外部依赖
    all_refs -= set(func_names)

    # 新模块内容
    body = "\n\n".join(segs[f] for f in func_names if f in segs)
    dep_line = (f"from {base} import {', '.join(sorted(all_refs))}\n\n"
                if all_refs else "")
    new_src = (
        f'"""{base} 的自检/检查逻辑（由 _extract_tool.py 从 {base}.py 抽出）\n\n'
        f'改前必读: IMPROVE_{base}.md\n"""\n'
        f"{import_block}\n"
        f"{dep_line}"
        f"{body}\n"
    )

    # 原模块：删除函数定义，替换成 wrapper
    spans = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in func_names:
                spans.append((node.lineno - 1, node.end_lineno, node.name))
    spans.sort(reverse=True)
    new_lines = list(lines)
    for start, end, name in spans:
        # 保留装饰器行不处理（自检函数通常无装饰器）
        wrapper = [
            f"def {name}(*a, **k):",
            f"    from {os.path.basename(new_path)[:-3]} import {name} as _f",
            f"    return _f(*a, **k)",
        ]
        new_lines[start:end] = wrapper
    src_out = "\n".join(new_lines)
    if src.endswith("\n"):
        src_out += "\n"

    if dry:
        return new_src, src_out

    open(new_path, "w", encoding="utf-8").write(new_src)
    open(src_path, "w", encoding="utf-8").write(src_out)
    print(f"[OK] {src_module}: 抽出 {sorted(func_names)} -> {new_module}")
    print(f"     依赖回引: {sorted(all_refs)}")
    return new_src, src_out


if __name__ == "__main__":
    if len(sys.argv) < 4:
        raise SystemExit("用法: python _extract_tool.py <源模块> <新模块> <函数...>")
    extract(sys.argv[1], sys.argv[2], sys.argv[3:])
