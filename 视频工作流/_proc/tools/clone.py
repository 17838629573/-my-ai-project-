"""重复代码(克隆)检测工具  —— 项目瘦身第二阶段

契约: proc/tools/clone
  输入: 项目根目录(默认 _proc)、最小行数、最小token数
  输出: 克隆组清单 [{hash, n, lines, members:[(file,func,lineno)]}]
        按"可节省行数"降序
  依赖: 标准库 ast / hashlib / pathlib
  被依赖: 人工瘦身决策(无代码引用, 属工具层)
  约束: 阈值出处 archlinter code_clone 默认 min_lines=6 min_tokens=50;
        UVA CloneRefactor 论文建议 min_tokens=10(更严, 抓2语句级克隆);
        本工具两档都支持, 默认用 min_lines=6/min_tokens=30 折中;
        变量名/常量归一化后比对 => 可抓 Type-2(结构同参数异)克隆;
        只报不改, 提取公共函数由人工确认后执行(避免误合语义不同的代码)
  校验: python3 _proc/tools/clone.py [--min-lines N] [--min-tokens N]
"""

from __future__ import annotations

import ast
import hashlib
import sys
from pathlib import Path

# ---- 阈值出处 ----
# archlinter code_clone 检测器默认 min_lines=6, min_tokens=50
# UVA "Towards Automated Merging of Code Clones" 6.2 节: 多数工具取 6 行/
# 50 token, 但该文实测 10 token 的两语句克隆中大量"应该重构", 故更严
MIN_LINES = 6
MIN_TOKENS = 30

SKIP_PARTS = {"__pycache__", ".git", "_bak", "tools", ".venv"}


class _Norm(ast.NodeTransformer):
    """归一化: 变量名 -> V, 常量值 -> C, 属性名保留(语义锚点)"""

    def visit_Name(self, node: ast.Name) -> ast.Name:
        return ast.Name(id="V", ctx=node.ctx)

    def visit_Constant(self, node: ast.Constant):
        # 保留类型不保留值: 数字串不同但结构相同的算克隆
        return ast.Constant(value=None, kind=None)

    def visit_arg(self, node: ast.arg) -> ast.arg:
        return ast.arg(arg="V", annotation=None, type_comment=None)


def _token_count(node: ast.AST) -> int:
    return sum(1 for _ in ast.walk(node))


def _sig(node: ast.AST) -> str:
    """归一化后的结构摘要 -> 稳定哈希"""
    try:
        n = _Norm().visit(ast.parse(ast.unparse(node)))
        ast.fix_missing_locations(n)
        src = ast.dump(n, annotate_fields=True, include_attributes=False)
    except Exception:
        return ""
    return hashlib.sha1(src.encode("utf-8")).hexdigest()[:16]


def _iter_funcs(root: Path):
    for p in sorted(root.rglob("*.py")):
        if any(part in SKIP_PARTS for part in p.parts):
            continue
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield p, node


def scan(root: Path, min_lines: int = MIN_LINES, min_tokens: int = MIN_TOKENS):
    groups: dict[str, list] = {}
    for p, node in _iter_funcs(root):
        body = node.body
        end = getattr(body[-1], "end_lineno", node.lineno) if body else node.lineno
        lines = end - node.lineno + 1
        if lines < min_lines:
            continue
        tok = _token_count(node)
        if tok < min_tokens:
            continue
        sig = _sig(node)
        if not sig:
            continue
        groups.setdefault(sig, []).append({
            "file": str(p), "func": node.name,
            "lineno": node.lineno, "lines": lines, "tokens": tok,
        })
    out = []
    for sig, mem in groups.items():
        if len(mem) < 2:
            continue
        lines = mem[0]["lines"]
        # 可节省 = 重复份数-1 份的行数
        out.append({
            "sig": sig, "n": len(mem), "lines": lines,
            "save": lines * (len(mem) - 1), "members": mem,
        })
    out.sort(key=lambda g: -g["save"])
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    min_lines, min_tokens = MIN_LINES, MIN_TOKENS
    if "--min-lines" in argv:
        min_lines = int(argv[argv.index("--min-lines") + 1])
    if "--min-tokens" in argv:
        min_tokens = int(argv[argv.index("--min-tokens") + 1])
    root = Path(__file__).resolve().parents[1]
    groups = scan(root, min_lines, min_tokens)
    total = sum(g["save"] for g in groups)
    print(f"阈值 min_lines={min_lines} min_tokens={min_tokens}")
    print(f"克隆组 {len(groups)}  可节省约 {total} 行")
    print("-" * 78)
    for g in groups[:20]:
        print(f"[{g['sig']}] x{g['n']}  {g['lines']}行/份  可省 {g['save']}行")
        for m in g["members"]:
            rel = m["file"].replace(str(root) + "/", "")
            print(f"    {rel}:{m['lineno']}  {m['func']}()")
    if len(groups) > 20:
        print(f"... 另有 {len(groups)-20} 组")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
