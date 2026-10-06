# 契约: proc/tools/docsync
#   一句话: 检测 README / INDEX 里的数字声明是否与脚本实测一致，抓"文档说一套、代码是另一套"
#   完整契约见 tools/__init__.py
#   依据: sybil —— pytest 官方生态的可执行文档测试工具，把 markdown 里的代码块纳入测试；
#         DriftGuard / borghei/doc-drift-detector —— README 与代码 cross-check、staleness 评分；
#         dev.to《Testing Against State Drift》—— "A drift check that can quietly discover
#         nothing is worse than no check, because it's green and wrong"（抓不到声明必须报错，
#         不得静默跳过来假装通过）。
# -*- coding: utf-8 -*-
"""文档-代码数字漂移检测（R20）。

为什么需要它：
  本项目 README 曾同时存在 5 处数字失实——PASS 21（实测 22）、活跃 49（实测 70）、
  "根目录 36 个 py 旧链路"（实测仅 1 个）、INDEX 记 rigid2d 916 行单文件（实已拆 6 个）、
  体积 7.4MB（三个口径混说）。这些都不是代码 bug，靠 check.py / 门检都抓不到——
  它们只检查代码，从不检查"文档说的话"。

机制：声明探针（claim probe）。每条探针 = 文档里的一句数字声明 + 一条实测命令。
  声称值（正则从文档提取） != 实测值（正则从命令输出提取） -> 报漂移。

fail-closed 两条硬约束：
  1. 文档里正则一个都匹配不到 -> 报"探针失效"，不是跳过。
     文档改了措辞会让探针悄悄失效，静默通过等于假绿。
  2. 实测命令跑不出数（超时/报错/输出格式变了）-> 报"实测失败"，不是跳过。
"""
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROC = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_PROC)

sys.path.insert(0, _PROC)

PY = sys.executable


def _read(rel):
    p = os.path.join(_ROOT, rel)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return f.read()


def _run(rel, timeout=900):
    """以 _PROC 为 cwd 跑脚本，返回输出文本。"""
    try:
        p = subprocess.run([PY, rel], cwd=_PROC, timeout=timeout,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return None
    except Exception:
        return None


# 不入库的产物（.gitignore 已排除），统计"入库体积"时必须剔除，
# 否则本地多跑几段视频就会把 README 里的工作树体积顶成假漂移
_SKIP_EXT = (".mp4", ".mov", ".avi", ".webm", ".mkv", ".m4v", ".flv",
             ".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp",
             ".pyc", ".so", ".zip", ".pkl", ".npz")


def _du_mb(root):
    """入库体积(MB)：排除产物与字节码，与 README「工作树体积」同口径。"""
    total = 0
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in (".git", "__pycache__")]
        for f in fn:
            try:
                if f.endswith(_SKIP_EXT):
                    continue
                total += os.path.getsize(os.path.join(dp, f))
            except OSError as e:
                # 静默 pass 会让"统计不到"伪装成"体积为 0"，与 S01 同款病
                sys.stderr.write("[warn] 体积统计跳过 %s: %s\n" % (f, e))
    return total / 1048576.0


def _index_entries(text):
    """只取「三层树」段落里的条目；说明文字里恰好同格式的行不算索引。"""
    m = re.search(r"^##\s*三层树.*?(?=^##\s|\Z)", text, re.M | re.S)
    return list(_IDX_RE.finditer(m.group(0) if m else text))


# ---------------------------------------------------------------- 探针表
# id / 文档 / 声称值正则 / 实测方式 / 是否耗时
PROBES = [
    dict(id="活跃文件数", doc="README.md",
         pat=r"活跃文件\s+(\d+)\s*个",
         cmd="tools/reach.py", grab=r"可达文件\s+(\d+)", slow=False),
    dict(id="孤立文件数", doc="README.md",
         pat=r"孤立文件\s+(\d+)\s*个",
         cmd="tools/reach.py", grab=r"孤立文件\s+(\d+)", slow=False),
    dict(id="门检 PASS", doc="README.md",
         pat=r"PASS\s+(\d+)\s*/",
         cmd="tests/run_all.py", grab=r"PASS\s+(\d+)", slow=True),
    dict(id="门检 STUB", doc="README.md",
         pat=r"STUB\s+(\d+)",
         cmd="tests/run_all.py", grab=r"STUB\s+(\d+)", slow=True),
    dict(id="工作树体积 MB", doc="README.md",
         pat=r"工作树\s+([\d.]+)\s*MB",
         cmd=None, grab=None, slow=False, tol=0.35),
]

# INDEX 行: "  - `path` 123 行 — 描述"
_IDX_RE = re.compile(r"^\s*-\s+`([^`]+)`\s+(\d+)\s*行", re.M)


def _probe_index():
    """INDEX 新鲜度：逐个比对 INDEX.md 记录的路径与行数是否与实际一致。"""
    issues = []
    src = _read("_proc/INDEX.md")
    if src is None:
        return ["[R20 INDEX 失效] _proc/INDEX.md 不存在，无法校验新鲜度"]
    n_checked = 0
    for m in _index_entries(src):
        rel, lines = m.group(1), int(m.group(2))
        real = os.path.join(_PROC, rel)
        if not os.path.exists(real):
            issues.append(
                "[R20 INDEX 漂移] %s: INDEX 记录 %s 行，但文件已不存在（拆分/改名未重跑 gen_index.py）"
                % (rel, lines))
            n_checked += 1
            continue
        with open(real, encoding="utf-8") as f:
            actual = sum(1 for _ in f)
        n_checked += 1
        if abs(actual - lines) > max(5, lines * 0.15):
            issues.append(
                "[R20 INDEX 漂移] %s: INDEX 记录 %d 行，实际 %d 行（差 %d）"
                % (rel, lines, actual, actual - lines))
    if n_checked == 0:
        issues.append("[R20 INDEX 失效] 未能从 INDEX.md 解析出任何条目，探针失效（不得静默通过）")
    return issues


def run(skip_slow=False, verbose=True):
    issues = []
    cache = {}
    for pb in PROBES:
        src = _read(pb["doc"])
        if src is None:
            issues.append("[R20 探针失效] %s 不存在" % pb["doc"])
            continue
        claims = [int(float(x)) if pb["id"] != "工作树体积 MB" else float(x)
                  for x in re.findall(pb["pat"], src)]
        if not claims:
            issues.append(
                "[R20 探针失效] %s 中未匹配到「%s」的声明值——文档措辞变了，探针需同步，不得静默通过"
                % (pb["doc"], pb["id"]))
            continue

        if pb["slow"] and skip_slow:
            continue

        # 实测
        if pb["cmd"] is None:  # 体积
            actual = round(_du_mb(os.path.join(_ROOT, "_proc")), 2)
        else:
            if pb["cmd"] not in cache:
                cache[pb["cmd"]] = _run(pb["cmd"])
            out = cache[pb["cmd"]]
            if out is None:
                issues.append("[R20 实测失败] %s 跑超时/报错，无法取得「%s」真值" % (pb["cmd"], pb["id"]))
                continue
            g = re.search(pb["grab"], out)
            if not g:
                issues.append(
                    "[R20 实测失败] %s 输出中未找到 /%s/ ，输出格式变了，无法校验「%s」"
                    % (pb["cmd"], pb["grab"], pb["id"]))
                continue
            actual = float(g.group(1))

        tol = pb.get("tol", 0)
        for c in set(claims):
            if abs(c - actual) > tol:
                issues.append(
                    "[R20 文档漂移] %s 声称「%s」= %s，脚本实测 = %s"
                    % (pb["doc"], pb["id"], c, actual))

    if not skip_slow or True:
        issues.extend(_probe_index())
    return issues


def self_check():
    """自检：造一个必然失配的文档，验证工具真能报警（不静默跳过）。"""
    import base.assertrun as _ar
    chk = _ar.Checker("tools/docsync")
    import tempfile
    d = tempfile.mkdtemp()
    f = os.path.join(d, "README.md")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write("活跃文件  999 个\n孤立文件  1 个\n")
    old_root, old_probe = _ROOT, None
    # 直接验证正则提取 + 失配判定，不依赖真实项目
    src = open(f, encoding="utf-8").read()
    got = re.findall(PROBES[0]["pat"], src)
    chk.eq("能提取到声明值", len(got), 1)
    chk.eq("提取值正确", int(got[0]), 999)
    bad = re.findall(PROBES[0]["pat"], "活跃文件  70 个")
    chk.eq("正常文档可提取", int(bad[0]), 70)
    # 探针失效必须可检出：措辞变了匹配不到
    chk.eq("措辞变化后匹配为空", len(re.findall(PROBES[0]["pat"], "活跃模块数量：70")), 0)
    # INDEX 正则
    chk.eq("INDEX 正则能解析", len(_IDX_RE.findall("  - `a.py` 12 行 — x\n  - `b.py` 30 行 — y")), 2)
    chk.eq("INDEX 正则对非条目行不误报", len(_IDX_RE.findall("# 标题\n普通文字")), 0)
    # 端到端：把 _ROOT 临时指向夹具（声称 999 且无 INDEX.md），必须报出问题而非静默通过
    import sys as _s
    _me = _s.modules[__name__]
    _o_root, _o_proc = _me._ROOT, _me._PROC
    try:
        _me._ROOT = d
        _me._PROC = os.path.join(d, "_proc")
        r = run(skip_slow=True)
        n = (len(r[1]) if isinstance(r, (tuple, list)) and len(r) > 1
             else (len(r) if isinstance(r, (list, tuple)) else -1))
        chk.chk("失配文档必须报出问题(不静默通过)", n > 0, "issues=%s" % n)
    except Exception as e:
        chk.chk("失配文档必须报出问题(不静默通过)", False,
                "EXC %s: %s" % (type(e).__name__, e))
    finally:
        _me._ROOT, _me._PROC = _o_root, _o_proc
    return 0 if chk.report(verbose=True) else 1


def main():
    if "--self-check" in sys.argv:
        sys.exit(self_check())
    skip_slow = "--quick" in sys.argv
    issues = run(skip_slow=skip_slow)
    print("=== R20 文档-代码漂移检测 ===")
    if skip_slow:
        print("(--quick: 已跳过耗时探针)")
    if not issues:
        print("OK  文档声明与脚本实测一致")
        return 0
    for s in issues:
        print(s)
    print("共 %d 条" % len(issues))
    return 1


if __name__ == "__main__":
    sys.exit(main())
