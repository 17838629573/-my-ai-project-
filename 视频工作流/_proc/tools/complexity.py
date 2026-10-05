# 契约: proc/tools/complexity.py
#   一句话: 圈复杂度门禁——用 lizard 实测 CCN，替代自造的「函数>50行」行数规则
#   完整契约见 _proc/tools/__init__.py
#   依据: (1) lizard 是业界成熟的多语言 CCN/长度/参数数扫描器，默认阈值 -C 10 -L 60 -a 5
#            https://github.com/terryyin/lizard
#         (2) ruff C901 / flake8 mccabe 默认 max-complexity = 10
#         (3) radon CC 分级: A 1-5 / B 6-10 / C 11-20 / D 21-30 / E 31-40 / F 41+
#            —— 源自 McCabe 1976 建议 CC<=10 为可接受上限
#         (4) 设计值与红线分开（本项目铁律四）：
#              设计值 CCN<=10（lizard/ruff 默认）  超出登记为债务，带清零条件与到期日
#              硬闸   CCN>20（radon D 级 "alarming"） 直接 FAIL，不登记
# -*- coding: utf-8 -*-
"""圈复杂度门禁（R20）。

为什么废弃自造的「函数 >50 行」：
  行数与复杂度不相关。实测反例——showreel/render.py::build_bg 78 行但 CCN=1（线性直叙），
  而 tools/smell.py::_scan_undefined_names 仅 42 行却 CCN=28。按行数排序会把前者当债、
  放过后者，方向就是错的。业界统一用 CCN（lizard / ruff C901 / radon），本项目改用同一口径。

用法:
    python3 _proc/tools/complexity.py            # 人读
    python3 _proc/tools/complexity.py --json     # 机读
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROC = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_PROC)
for p in (_ROOT, _PROC):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import lizard  # noqa: E402  业界成熟库，不自己实现 CCN
except ImportError:  # 依赖缺失必须报错，不能静默当"零问题"——见 tools/repro.py 铁律一
    lizard = None

CCN_DESIGN = 10   # lizard/ruff 默认上限
CCN_HARD = 20     # radon D 级起始，直接 FAIL
# 长度维度: 自造 R3(函数>50行) 从 check.py 迁到本工具, 由 lizard 同一口径产出,
# 阈值与严重度保持原样(mrognlie 50~200 建议), 仅换实现方, 避免两套口径各报各的。
LEN_DESIGN = 50
LEN_HARD = 100
EXCLUDE_DIRS = {"__pycache__", "_bak", ".git", "_archive_文档_旧链路"}


def scan(root=_PROC, ccn_design=CCN_DESIGN, ccn_hard=CCN_HARD):
    if lizard is None:
        raise RuntimeError("lizard 未安装: pip install -r tools/requirements.txt")
    """扫描全部 .py，返回 (超设计值列表, 超硬闸列表)。

    每项: dict(file, func, line, ccn, length, params)
    """
    over_design, over_hard, over_len = [], [], []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]
        for fn in sorted(filenames):
            if not fn.endswith(".py"):
                continue
            path = os.path.join(dirpath, fn)
            rel = os.path.relpath(path, root)
            try:
                info = lizard.analyze_file(path)
            except Exception:
                continue  # 语法错误由 check.py R0 负责上报，这里不重复
            for f in info.function_list:
                item = {
                    "file": rel.replace("\\", "/"),
                    "func": f.name,
                    # lizard FunctionInfo 字段: start_line / parameter_count(int) / length(nloc)
                    "line": f.start_line,
                    "ccn": f.cyclomatic_complexity,
                    "length": f.length,
                    "params": int(f.parameter_count or 0),
                }
                if item["ccn"] > ccn_hard:
                    over_hard.append(item)
                elif item["ccn"] > ccn_design:
                    over_design.append(item)
                if item["length"] > LEN_HARD:
                    over_hard.append(item)
                elif item["length"] > LEN_DESIGN:
                    over_len.append(item)
    over_hard.sort(key=lambda x: -max(x["ccn"], x["length"]))
    over_design.sort(key=lambda x: -x["ccn"])
    over_len.sort(key=lambda x: -x["length"])
    return over_design, over_hard, over_len


def run(root=_PROC):
    """返回 {"ok":bool, "design":[...], "hard":[...], "counts":{...}}"""
    try:
        design, hard, over_len = scan(root)
    except RuntimeError as e:   # 依赖缺失/工具未真正执行 → 报错，绝不返回 ok
        return {"ok": False, "design": [], "hard": [str(e)], "over_len": [],
                "counts": {"over_design": 0, "over_hard": 1, "over_len": 0,
                           "ccn_design": CCN_DESIGN, "ccn_hard": CCN_HARD,
                           "len_design": LEN_DESIGN, "len_hard": LEN_HARD}}
    # 判定口径: 只有硬闸(CCN>20 / 长度>100)直接 FAIL。
    # 长度>50 属于遗留存量，按 lizard-complexity 实践指南明确列出的 Anti-pattern
    #   "Block PRs on absolute count —— Legacy code can't add a single line"
    # 改为走 tools/baseline.py 的棘轮: 存量入基线(带归属/清零条件/到期日)，
    # 新增或恶化即 FAIL。比"打印一句登记为债务却什么都没登记"严格得多。
    return {
        "ok": not hard,
        "design": design,
        "hard": hard,
        "over_len": over_len,
        "counts": {
            "over_design": len(design),
            "over_hard": len(hard),
            "over_len": len(over_len),
            "ccn_design": CCN_DESIGN,
            "ccn_hard": CCN_HARD,
            "len_design": LEN_DESIGN,
            "len_hard": LEN_HARD,
        },
    }


def self_check():
    """自检 4 项：CCN 判定准、高复杂度抓得到、低复杂度不误报、_bak 被排除。"""
    import tempfile
    ok = True

    def _chk(name, cond):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name)
        ok = ok and bool(cond)

    # 1) 线性函数 CCN 应为 1，且不触发任何阈值
    src_linear = "def f(a):\n    b = a + 1\n    return b\n"
    # 2) 高复杂度函数应被抓到（10 个分支 → CCN 11）
    src_high = "def g(a):\n" + "".join(
        "    if a == %d:\n        return %d\n" % (i, i) for i in range(10)
    ) + "    return -1\n"
    # 两个用例必须分置不同目录：同目录会被同一次 scan 一起扫到，导致互相污染
    with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
        open(os.path.join(td1, "lin.py"), "w").write(src_linear)
        open(os.path.join(td2, "hi.py"), "w").write(src_high)
        d1, h1, l1 = scan(td1)
        d2, h2, l2 = scan(td2)
        _chk("线性函数不报(over_design=0, over_hard=0)", len(d1) == 0 and len(h1) == 0)
        _chk("高复杂度函数被抓到(CCN>10 进 design)", any(x["func"] == "g" for x in d2))
        _chk("CCN 值正确(11)", any(x["func"] == "g" and x["ccn"] == 11 for x in d2))

    # 3) 全项目扫描不崩且能产出结果
    r = run()
    _chk("全项目扫描可执行", isinstance(r["counts"]["over_design"], int))
    # 4) _bak 被排除（冻结封存目录不应出现在结果里）
    _chk("_bak 已排除",
         not any("_bak" in x["file"] for x in r["design"] + r["hard"] + r["over_len"]))
    # 5) 长度维度: 60 行线性函数应被报为长度问题(原 R3 口径), 且不进 CCN 债务
    with tempfile.TemporaryDirectory() as td3:
        src_long = "def h(a):\n" + "".join("    b%d = a + %d\n" % (i, i) for i in range(60)) + "    return b0\n"
        open(os.path.join(td3, "long.py"), "w").write(src_long)
        d3, h3, l3 = scan(td3)
        _chk("长但线性的函数按长度报出而非CCN债务",
             any(x["func"] == "h" for x in l3) and not any(x["func"] == "h" for x in d3))
    return ok


def main():
    if "--self-check" in sys.argv:
        return 0 if self_check() else 1
    r = run()
    if "--json" in sys.argv:
        import json
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["ok"] else 1
    c = r["counts"]
    print("圈复杂度门禁 (lizard CCN)  设计值<=%d  硬闸>%d" % (c["ccn_design"], c["ccn_hard"]))
    print("  超设计值(登记为债务) %d    超硬闸(直接FAIL) %d    超长度>%d %d"
          % (c["over_design"], c["over_hard"], c["len_design"], c["over_len"]))
    if r["hard"]:
        print("  [硬闸] 必须拆分:")
        for x in r["hard"]:
            print("    %s:%d %s CCN=%d len=%d" % (x["file"], x["line"], x["func"], x["ccn"], x["length"]))
    if r["over_len"]:
        print("  [长度] >%d 行:" % r["counts"]["len_design"])
        for x in r["over_len"]:
            print("    %s:%d %s len=%d CCN=%d" % (x["file"], x["line"], x["func"], x["length"], x["ccn"]))
    if r["design"]:
        print("  [设计值] 前 10:")
        for x in r["design"][:10]:
            print("    %s:%d %s CCN=%d len=%d" % (x["file"], x["line"], x["func"], x["ccn"], x["length"]))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
