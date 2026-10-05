import ast, sys, textwrap

def extract(src_path, names, new_path, new_header, wrapper=True):
    src = open(src_path).read()
    tree = ast.parse(src)
    keep, taken = [], {}
    for n in tree.body:
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in names:
            taken[n.name] = ast.get_source_segment(src, n)
        else:
            keep.append(n)
    assert set(taken) == set(names), f"缺函数: {set(names)-set(taken)}"
    # 新模块
    with open(new_path, 'w') as f:
        f.write(new_header + "\n\n")
        for nm in names:
            f.write(taken[nm] + "\n\n")
    # 原模块：AST 重建，只留未抽取节点
    mod = ast.Module(body=keep, type_ignores=[])
    out = ast.unparse(mod)
    if wrapper:
        out += "\n\n" + "\n".join(
            f"def {nm}(*a, **k):\n    from {new_path[:-3]} import {nm} as _f\n    return _f(*a, **k)\n"
            for nm in names)
    open(src_path, 'w').write("#!/usr/bin/env python3\n" + out)
    print(f"{src_path}: 抽出 {names} -> {new_path}")

if __name__ == "__main__":
    pass
