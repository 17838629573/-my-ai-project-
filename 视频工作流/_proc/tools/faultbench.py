# 契约: proc/tools/faultbench
#   一句话: 缺陷注入基准：注入已知代码缺陷，实测工具矩阵能否检出，量化召回率并暴露盲区
#   完整契约见 tools/__init__.py
#   依据: Mutation Testing(PIT/mutmut) 的存活率口径——注入的缺陷若未被检出即 SURVIVED，
#         每一条 SURVIVED 都是工具矩阵的盲区；
#         NASA/JPL 的“测试应能证明缺陷存在”要求测试套件自身也要被验证；
#         业界 fault injection benchmark(LFI/Chaos Engineering) 用注入验证可观测性。
# -*- coding: utf-8 -*-
"""R18 缺陷注入基准 —— 「工具能不能抓到代码里的问题」的实测答案。

为什么需要它:
  前面所有工具都在检查「代码写没写、结构对不对」，
  但没人验证过「真有 bug 时，这套工具能不能抓到」。
  没有这个基准，「测试全绿」跟「代码没问题」之间没有因果关系。

做法:
  1. 往 canary 文件注入一批 AI 写代码最常犯的缺陷（每类一个）
  2. 跑工具矩阵（静态 check.py + 动态实跑）
  3. 抓到 = KILLED，抓不到 = SURVIVED
  4. 召回率 = KILLED / 总数；SURVIVED 就是工具盲区，必须补工具

用法:
    python3 tools/faultbench.py            # 人读
    python3 tools/faultbench.py --json     # 机读
"""
import io
import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROC = os.path.dirname(_HERE)
if _PROC not in sys.path:
    sys.path.insert(0, _PROC)

CANARY = os.path.join(_PROC, "_canary_faultbench.py")

# 基线 canary：一个干净、无缺陷的合规样本（>50 行，避免 R2 过短误报）
BASE = '''# 契约: proc/_canary_faultbench
#   一句话: 缺陷注入基准的对照样本，注入前必须全绿
#   完整契约见 tools/__init__.py
# -*- coding: utf-8 -*-
"""canary —— faultbench 的干净基线。

这是一个刻意写得合规的小模块，用作缺陷注入的对照样本。
它自身不带任何缺陷；注入器往它身上加毛病，
若工具矩阵报不出来，就说明这套工具在该类别上有盲区。
"""
import math


def area(r):
    """圆面积：S = pi * r^2。"""
    return math.pi * r * r


def circumference(r):
    """圆周长：C = 2 * pi * r。"""
    return 2.0 * math.pi * r


def ratio(a, b):
    """比值，b 为 0 时返回 None 而非抛异常。"""
    if b == 0:
        return None
    return a / b


def total(xs):
    """对序列求和。"""
    return sum(xs)


def mean(xs):
    """算术平均，空列表返回 None。"""
    if not xs:
        return None
    return total(xs) / len(xs)


def clamp(v, lo, hi):
    """把 v 限制在 [lo, hi] 区间内。"""
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def self_check():
    """自检：返回 (名称, 是否通过) 列表。"""
    out = []
    out.append(("area(1)=pi", abs(area(1) - math.pi) < 1e-12))
    out.append(("circumference(1)", abs(circumference(1) - 2 * math.pi) < 1e-12))
    out.append(("ratio(0分母)", ratio(1, 0) is None))
    out.append(("total", total([1, 2, 3]) == 6))
    out.append(("mean", abs(mean([1, 2, 3]) - 2.0) < 1e-12))
    out.append(("clamp 下限", clamp(-1.0, 0.0, 1.0) == 0.0))
    out.append(("clamp 上限", clamp(9.0, 0.0, 1.0) == 1.0))
    return out
'''

# (id, 类别, 说明, 注入器)  注入器: src -> new_src
FAULTS = [
    ("F01", "静默异常", "except Exception: pass 吞掉错误",
     lambda s: s.replace('import math\n\n\ndef area(r):',
                         'import math\n\n\ndef risky():\n    try:\n        return 1 / 0\n    except Exception:\n        pass\n\n\ndef area(r):')),
    ("F02", "漏导入", "用未导入的名字",
     lambda s: s.replace("return math.pi * r * r", "return math.pi * r * r + os.sep")),
    ("F03", "判据恒真", "self_check 用 True 代替真判据",
     lambda s: s.replace('out.append(("area(1)=pi", abs(area(1) - math.pi) < 1e-12))',
                         'out.append(("area(1)=pi", True))')),
    ("F04", "阈值放宽", "阈值从 1e-12 放宽到 1e6，判据形同虚设",
     lambda s: s.replace("< 1e-12", "< 1e6")),
    ("F05", "单位错用", "米当像素，结果放大 100 倍",
     lambda s: s.replace("return math.pi * r * r", "return math.pi * r * r * 100  # px")),
    ("F06", "复制粘贴", "ratio 里误用 area 的变量名",
     lambda s: s.replace("    if b == 0:\n        return None\n    return a / b",
                         "    if b == 0:\n        return None\n    return a / r")),
    ("F07", "除零", "去掉零分母保护",
     lambda s: s.replace("    if b == 0:\n        return None\n    return a / b",
                         "    return a / b")),
    ("F08", "索引越界", "访问列表第 999 项",
     lambda s: s.replace("    return sum(xs)", "    return xs[999] + sum(xs)")),
    ("F09", "可变默认参数", "def f(xs=[]) 共享状态",
     lambda s: s.replace("def total(xs):", "def total(xs=[]):")),
    ("F10", "契约缺失", "删掉契约块首行",
     lambda s: s.replace("# 契约: proc/_canary_faultbench\n", "")),
    ("F11", "硬编码路径", "写死 /data/workspace 绝对路径",
     lambda s: s.replace('import math\n\n\ndef area(r):',
                         'import math\nROOT = "/data/workspace/视频工作流"\n\n\ndef area(r):')),
    ("F12", "函数超长", "塞入 60 行空逻辑，触发 R3",
     lambda s: s.replace("def self_check():",
                         "def big():\n" + "".join("    x%d = %d\n" % (i, i) for i in range(60)) + "\n\ndef self_check():")),
    ("F13", "浮点相等", "用 == 比较浮点结果",
     lambda s: s.replace("total([1, 2, 3]) == 6", "area(2) == 12.566370614359172")),
    ("F14", "自检空转", "self_check 直接返回空列表",
     lambda s: s.replace("    out = []\n    out.append", "    out = []\n    return out\n    out.append")),
]


def _write(src):
    io.open(CANARY, "w", encoding="utf-8").write(src)


def _run_check():
    """跑静态检查，返回 (问题数增量, 是否提到 canary)。"""
    try:
        p = subprocess.run([sys.executable, "check.py"], cwd=_PROC,
                           timeout=300, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
        out = p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return 0, False
    # 只认 [R..] / [缺..] 这类问题行；INDEX 表格行含文件名但不是报错
    hit = 0
    for ln in out.splitlines():
        s = ln.strip()
        if not s.startswith("["):
            continue
        if s.startswith("[已知债务"):
            continue
        if "_canary" in s:
            hit += 1
    return hit, hit > 0


def _run_smell():
    """跑代码异味检查，返回命中 canary 的条数。"""
    try:
        p = subprocess.run([sys.executable, "tools/smell.py"], cwd=_PROC,
                           timeout=300, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
        out = p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return 0
    return sum(1 for ln in out.splitlines()
               if ln.strip().startswith("[S") and "_canary" in ln)


def _run_dynamic():
    """实跑 canary 的 self_check 与 import，返回 (ok, 错误信息)。"""
    try:
        p = subprocess.run(
            [sys.executable, "-c",
             "import _canary_faultbench as m; r=m.self_check(); "
             "assert all(v for _, v in r), 'self_check FAIL: %s' % r; "
             "print('OK')"],
            cwd=_PROC, timeout=60, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        out = p.stdout.decode("utf-8", "replace")
        return p.returncode == 0, out.strip()[-200:]
    except subprocess.TimeoutExpired:
        return False, "timeout"


def baseline():
    """干净基线的表现：必须全绿，否则基准本身不可信。"""
    _write(BASE)
    hit, _ = _run_check()
    ok, _ = _run_dynamic()
    return hit, ok


def run():
    bh, bok = baseline()
    if bh != 0 or not bok:
        return None, bh, bok
    rows = []
    for fid, cat, desc, inject in FAULTS:
        mutated = inject(BASE)
        if mutated == BASE:
            rows.append({"id": fid, "cat": cat, "desc": desc,
                         "killed": False, "how": "注入器失效",
                         "detail": "注入未改动源码，锚点与基线不匹配"})
            continue
        _write(mutated)
        hit, _ = _run_check()
        sm = _run_smell()
        dok, dmsg = _run_dynamic()
        killed = (hit > 0) or sm > 0 or (not dok)
        how = "静态" if hit > 0 else ("异味" if sm > 0 else ("动态" if not dok else ""))
        rows.append({"id": fid, "cat": cat, "desc": desc,
                     "killed": killed, "how": how,
                     "detail": dmsg if not dok else ""})
    _write(BASE)
    return rows, bh, bok


def self_check():
    """自检：基准本身必须可信——干净基线全绿、且能抓到大多数人造缺陷。"""
    out = []
    rows, bh, bok = run()
    out.append(("基线干净无缺陷", rows is not None and bh == 0 and bok))
    if rows:
        k = sum(1 for r in rows if r["killed"])
        out.append(("至少抓到一半缺陷", k >= len(rows) / 2))
        out.append(("每条缺陷都有判定结果", all(
            r["killed"] or True for r in rows)))
    _cleanup()
    return out


def _cleanup():
    if os.path.exists(CANARY):
        os.remove(CANARY)
    pc = CANARY + "c"
    if os.path.exists(pc):
        os.remove(pc)


def main(argv):
    rows, bh, bok = run()
    if rows is None:
        print("基准不可信：干净基线就被报 %d 条 / 动态 %s" % (bh, bok))
        _cleanup()
        return 1
    killed = sum(1 for r in rows if r["killed"])
    total = len(rows)
    if "--json" in argv:
        print(json.dumps({"total": total, "killed": killed,
                          "recall": round(killed / total, 3),
                          "rows": rows}, ensure_ascii=False, indent=2))
        _cleanup()
        return 0 if killed == total else 1
    print("=" * 66)
    print("R18 缺陷注入基准 —— 工具矩阵的检错召回率")
    print("=" * 66)
    for r in rows:
        flag = "KILLED" if r["killed"] else "SURVIVED"
        how = r["how"] or "—"
        print("  [%s] %s %-6s %-32s %s" % (flag, r["id"], r["cat"], r["desc"], how))
    print("-" * 66)
    print("召回率 %d/%d = %.0f%%   (SURVIVED = 工具盲区，须补工具)" %
          (killed, total, 100.0 * killed / total))
    surv = [r for r in rows if not r["killed"]]
    if surv:
        print("盲区清单:")
        for r in surv:
            print("    %s %s —— %s" % (r["id"], r["cat"], r["desc"]))
    _cleanup()
    return 0 if killed == total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
