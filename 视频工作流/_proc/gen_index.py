# 契约: proc/gen_index
#   一句话: 从各文件顶部契约块抽取职责，自动生成 INDEX.md（文档永不与代码脱节）
"""Generate INDEX.md from the contract blocks embedded in every module.

新增模块后跑一次即可：python gen_index.py
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SKIP = {"_bak", "__pycache__", "_archive_旧链路"}

RULE_DOC = """## 契约规则与出处（不凭记忆，逐条可查）

| 规则 | 阈值/要求 | 出处 |
|---|---|---|
| R1 依赖单向 | 上层可依赖下层，**含传递依赖** | import-linter layers contract: "even indirectly" |
| R2 模块行数 | **50~500 行**；<50 不配独立成文件，应与兄弟模块合并 | AlgoMaster / mrognlie coding guide（两处独立来源） |
| R3 函数行数 | ≤50 行 | mrognlie coding guide |
| R4 包条目数 | 3~20 个 | mrognlie coding guide |
| R5 公开名 | ≤40，超出说明模块干太多 | AlgoMaster: "A module with 40 public names is doing too much" |
| R6 契约首行 | ≤72 字符 | numpydoc 规范 |
| R7 职责单一 | 一句话说清；出现两个"和"就该拆 | AlgoMaster |
| R8 避免过深嵌套 | 反模式：too many tiny packages / god package | Smalltalk Package Anti-Patterns |
| R9 圈复杂度 | <=10；>15 需书面说明 | NASA SWEHB 3.2.2 / NIST 结构化测试方法论 |
| R10 包必须真实可导入 | import 一遍不报错 | FixDevs: Verify with a clean import |

已知偏差（有依据，非疏漏）：
- `shape/` `color/` 各只有 1 个模块，低于 R4 下限。但强行再拆会产生
  R8 警告的 "too many tiny packages"，两条规则在此冲突，取 R8。
- `motion/character/sdf.py` 46 行低于 R2 下限，但被 `__init__/render/selfcheck`
  三处引用，合并会破坏既有公开面，暂保留。
"""


def one_liner(path, text=None):
    """只从文件头 40 行抽取职责，避免抓到源码里的正则片段。"""
    if text is None:
        text = open(path, encoding="utf-8").read()
    head = "\n".join(text.splitlines()[:40])
    m = re.search(r"一句话[:：]\s*(.+)", head)
    if m:
        return m.group(1).strip()
    m = re.search(r'^"""(.*?)"""', head, re.S | re.M)
    if m:
        return m.group(1).strip().splitlines()[0][:70]
    for ln in head.splitlines():
        s = ln.strip()
        if s and not s.startswith(("#", "import", "from", '"""')):
            return s[:70]
    return "（缺一句话职责）"


def _dir_key(dirpath):
    """相对根目录的层名；根目录改名 '(根)' 以便排序时置顶。"""
    key = os.path.relpath(dirpath, ROOT)
    return "(根)" if key == "." else key


def _size_flag(n):
    """超 500 行标 ⚠，不足 50 行标 ·，其余无标记（R2/R3 的可视化）。"""
    if n > 500:
        return " ⚠"
    return " ·" if n < 50 else ""


def scan_tree():
    """扫描三层目录，返回 {层名: [(文件名, 行数, 一句话职责)]}。"""
    by_dir = {}
    for dirpath, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in SKIP]
        key = _dir_key(dirpath)
        for fn in sorted(files):
            if not fn.endswith(".py") or fn == "__init__.py":
                continue
            p = os.path.join(dirpath, fn)
            text = open(p, encoding="utf-8").read()
            by_dir.setdefault(key, []).append(
                (fn, len(text.splitlines()), one_liner(p, text)))
    return by_dir


def _tree_lines(by_dir):
    """渲染"三层树"段落：根目录置顶，其余按层名字典序。"""
    out = []
    for key in sorted(by_dir, key=lambda k: (k != "(根)", k)):
        out.append(f"### {key}/")
        for fn, n, desc in by_dir[key]:
            out.append(f"  - `{fn}` {n} 行{_size_flag(n)} — {desc}")
        out.append("")
    return out


def _problem_lines():
    """调用 check.py 取实时问题清单；调用失败时降级为一行说明。"""
    try:
        r = subprocess.run([sys.executable, "check.py"], cwd=ROOT,
                           capture_output=True, text=True, timeout=120)
    except Exception as e:
        return [f"（check.py 未运行：{e}）"]
    probs = [l for l in r.stdout.splitlines() if l.startswith("[")]
    out = ["## 当前问题（check.py 实时输出）", "",
           f"共 {len(probs)} 项：" if probs else "全部通过 ✅", ""]
    out += [f"- {p}" for p in probs]
    return out


def main():
    """编排：扫描 → 头部 → 三层树 → 规则表 → 问题清单 → 写盘。"""
    by_dir = scan_tree()
    out = ["# proc —— 程序化动画引擎（三层契约图）", "",
           "本文件由 `python gen_index.py` **自动生成**，职责与行数据来自各文件顶部契约块，不会与代码脱节。",
           "", "点开顺序：**本文件 → 中模块 `__init__.py` → 小模块**。每层只暴露下一层的一句话职责。",
           "", "## 流水线", "", "```", "画线 shape → 填色 color → 装背景 scene → 跑起来 motion → mp4", "```",
           "", "## 三层树", ""]
    out += _tree_lines(by_dir)
    out += [RULE_DOC]
    out += _problem_lines()

    dst = os.path.join(ROOT, "INDEX.md")
    with open(dst, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out) + "\n")
    print(f"已生成 {dst}，{sum(len(v) for v in by_dir.values())} 个文件")


if __name__ == "__main__":
    main()
