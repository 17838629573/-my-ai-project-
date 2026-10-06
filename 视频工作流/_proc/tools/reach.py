#!/usr/bin/env python3
"""从活跃入口出发的 import 可达性分析（SCARF 的 Survey 阶段）。

契约: _proc/tools/reach
  输入: 无（扫描项目根）
  输出: 未被引用的 py 文件清单 + 活跃文件清单
  依赖: 标准库 ast/os
  被依赖: 瘦身流程
  约束: 排除 _bak 等存档目录
        短名歧义全部登记, 结果不依赖文件系统遍历顺序(同一份代码必须算出同一结果)
  校验: python3 _proc/tools/reach.py
"""
import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

SKIP_PARTS = {"__pycache__", ".git", "_bak", "tools"}

# 活跃入口：演示脚本 + 测试 + 门禁
ENTRY = {
    "_proc/beat_demo.py",
    "_proc/showreel/cafe.py",
    "_proc/tests/run_all.py",
    "_proc/check.py",
    "_proc/gen_index.py",
    # 新增入口：90秒长镜头管线（timeline/shard/seam 三件套）
    "_proc/showreel/timeline.py",
    "_proc/showreel/shard.py",
    "_proc/showreel/seam.py",
    # 新增入口：分层合成模块自带自检
    "_proc/motion/layer.py",
    "_proc/tests/gen.py",
    # 人工执行入口(无代码引用, 但必须保留)
    "push_gh.py",
}


def all_py():
    for p in ROOT.rglob("*.py"):
        if any(s in p.parts for s in SKIP_PARTS):
            continue
        yield p


def rel(p):
    return p.relative_to(ROOT).as_posix()


def mod_name(relpath):
    """把文件路径转成可能的模块名：目录用 . 连接，.py 去掉。"""
    r = relpath
    if r.endswith(".py"):
        r = r[:-3]
    return r.replace("/", ".").replace(".__init__", "")


def imports_of(path):
    """收集该文件 import 的目标（相对层级 + 绝对名）。"""
    out = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name.split(".")[0])
                # import a.b.c 形式：完整名与各级前缀都要登记，
                # 否则 import motion.rigid 只会解析到 motion/__init__.py
                seg = a.name.split(".")
                for i in range(1, len(seg) + 1):
                    out.add(".".join(seg[:i]))
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # 相对导入
                pkg = mod_name(rel(path))
                parts = pkg.split(".")
                # level=1 表示当前包，level=2 上一级
                base = parts[: len(parts) - (node.level - 1)]
                if node.module:
                    out.add(".".join(base + [node.module]))
                # from . import a, b —— 名字在 names 里，不在 module 里
                for a in node.names:
                    out.add(".".join(base + [a.name]))
            elif node.module:
                out.add(node.module.split(".")[0])
                out.add(node.module)
                # from pkg import name —— name 可能是子模块
                for a in node.names:
                    out.add(node.module + "." + a.name)
    return out


def _build_name2file(files):
    """模块名 -> 文件列表。

    项目内并存两套包名（扁平 motion/scene/shape 与绝对 _proc.motion），两套都要登记。
    短名歧义（如 scene 同时匹配 _proc/scene/__init__.py 与 _proc/showreel/scene.py）
    必须全部登记，不能用 setdefault 只留一个：否则结果取决于文件系统遍历顺序
    （rglob 顺序随目录增删改而变），同一份代码会算出不同的可达集合。
    """
    name2file = {}
    for r in sorted(files):
        m = mod_name(r)
        cands = {m, m.split(".")[-1]}
        if m.startswith("_proc."):
            flat = m[len("_proc."):]
            cands.add(flat)
            cands.add(flat.split(".")[-1])
        for c in cands:
            name2file.setdefault(c, []).append(r)
    return name2file


def _reach(files, name2file):
    """从活跃入口做 BFS，返回可达文件集合。"""
    seen = set()
    queue = [e for e in ENTRY if e in files]
    while queue:
        cur = queue.pop()
        if cur in seen:
            continue
        seen.add(cur)
        for imp in imports_of(files[cur]):
            # 一个 import 名可能对应多个文件（短名歧义）：全部入队
            for tgt in name2file.get(imp, ()):
                if tgt and tgt not in seen:
                    queue.append(tgt)
    return seen


def main():
    files = {rel(p): p for p in all_py()}
    seen = _reach(files, _build_name2file(files))
    orphans = sorted(set(files) - seen)
    print(f"活跃入口 {len(ENTRY)} 个")
    print(f"可达文件 {len(seen)}")
    print(f"孤立文件 {len(orphans)}")
    print()
    print("=== 孤立（无任何活跃入口引用）===")
    for o in orphans:
        n = files[o].stat().st_size
        try:
            lines = len(files[o].read_text(encoding="utf-8", errors="ignore").splitlines())
        except Exception:
            lines = 0
        print(f"  {o}  ({lines} 行, {n} B)")


if __name__ == "__main__":
    sys.exit(main())
