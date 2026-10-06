# 契约: proc/tools/provenance
#   一句话: 核验判据阈值与其出处自洽、并探测"先调阈值让它过、后补出处"的 HARKing 行为
#   完整契约见 tools/__init__.py
#   依据: Kerr(1998) HARKing —— Hypothesizing After the Results are Known，先出结果再补假设；
#         arXiv:2104.08878《Leakage and the Reproducibility Crisis》—— 调参/选阈值依赖测试集
#         信息即数据泄露，报告指标不再可信；Simmons et al.(2011) 研究者自由度 —— 同一份数据
#         经不同阈值筛选可得到相反结论，阈值必须独立于本次结果事先定标；
#         Pylint/ESLint magic-number 规则与 thailint —— 硬编码常量须可追溯到声明来源。
# -*- coding: utf-8 -*-
"""阈值溯源与 HARKing 探测（R22）。

两件事：

A. 出处自洽（静态，不联网，每次都能跑）
   判据表里写 `"penetration_m": (0.01, "<", "Box2D linear slop=0.01")` 这种格式时，
   出处字符串里**自己声明了上游值**。若声明值 != 实际阈值，说明两处至少一处是错的。
   本项目 C1-1/1-2 就是这么被发现的：判据写 0.01，而它自己引的 Box2D 官方值是 0.005。
   —— 这不需要联网，因为矛盾写在项目自己的文件里。

B. HARKing 探测（读 git 历史）
   同一 commit 里既改了某判据的阈值数字、又改了它的出处字符串 —— 这是"先跑不过、
   再调阈值、然后补（或改）出处"的典型指纹。阈值应从独立来源先定标再跑测试，
   反过来做就是数据泄露。
"""
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROC = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_PROC)

sys.path.insert(0, _PROC)

# 出处里"自己声明了某个上游常量数值"的可信锚点
_ANCHOR = ("Box2D", "b2_", "linearSlop", "官方", "默认", "源码", "slop",
           "默认值", "官方源码")
# 出处里形如  name = 0.005  /  name<0.1  /  name 0.005
_CONST_RE = re.compile(r"([A-Za-z][A-Za-z0-9_ ]{0,24}?)\s*[=<>]\s*\(?\s*([0-9]*\.?[0-9]+)")
# 锚点常量名后紧跟的数值：覆盖 `#define b2_linearSlop 0.005` / `slop=0.005` 两种写法
_ANCHOR_NUM_RE = re.compile(r"(?:linearSlop|linear_slop|slop)\s*[=:]?\s*\(?\s*(\d*\.?\d+)", re.I)
# 判据表条目:  "name": (0.005, "<", "出处...")
_CRIT_RE = re.compile(r"[\"']([\w]+)[\"']\s*:\s*\(\s*([0-9eE+\-.]+)\s*,.+?[\"'](.+?)[\"']\s*\)")
_SRC_MARK = ("依据", "出处", "arXiv", "DOI", "ISBS", "Box2D", "SMPTE", "官方", "文献", "论文")


def _roots():
    """git 仓库根可能在 _ROOT 或其上级。"""
    for c in (_ROOT, os.path.dirname(_ROOT)):
        if os.path.isdir(os.path.join(c, ".git")):
            return c
    return None


# ---------------------------------------------------------------- A. 出处自洽
def check_selfconsistency(crit=None):
    """crit: [(name, thr, src)]，默认从 harness.CRIT 读。返回 (issues, compared, uncompared)。"""
    if crit is None:
        sys.path.insert(0, _PROC)
        try:
            from tests.harness import CRIT
        except Exception as e:
            return (["[R22 探针失效] 无法读取 harness.CRIT：%s" % e], 0, [])
        crit = []
        for name, v in (CRIT or {}).items():
            crit.append((name, v[0], v[2] if len(v) > 2 else ""))
    if not crit:
        return (["[R22 探针失效] harness.CRIT 为空，无法溯源"], 0, [])

    issues, compared, uncompared = [], 0, []
    for name, thr, src in crit:
        src = src or ""
        if not any(a in src for a in _ANCHOR):
            uncompared.append(name)
            continue
        hits = _CONST_RE.findall(src)
        # 优先信"锚点名自己带的值"（如 #define b2_linearSlop 0.005 / slop=0.005），
        # 这样 b2_common.h:65 这类行号不会把取值搅浑
        anchor = _ANCHOR_NUM_RE.search(src)
        if anchor:
            vals = set([float(anchor.group(1))])
        elif hits:
            # 只信"单一明确声明"的：多处数值无法判断哪个是声称值，计入未比对
            vals = set(float(v) for _, v in hits if _is_num(v))
        else:
            vals = set()
        if len(vals) != 1:
            uncompared.append(name)
            continue
        declared = vals.pop()
        compared += 1
        try:
            thr_f = float(thr)
        except Exception:
            uncompared.append(name)
            compared -= 1
            continue
        if abs(declared - thr_f) > 1e-12:
            issues.append(
                "[R22 出处自相矛盾] 判据 %s 阈值 = %s，但它的出处里自己写的是 %s —— 两处必有一错"
                % (name, thr, declared))
    return issues, compared, uncompared


def _is_num(s):
    try:
        float(s)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------- B. HARKing
def _git_log_patch(relpath):
    root = _roots()
    if root is None:
        return None
    try:
        p = subprocess.run(["git", "log", "-p", "-U0", "--follow", "--", relpath],
                           cwd=root, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                           timeout=60)
        return p.stdout.decode("utf-8", "replace")
    except Exception:
        return None


def _crit_of(lines):
    """从 diff 的 -/+ 行里抽出 {判据名: 阈值字面量}。"""
    return dict((m.group(1), m.group(2))
                for m in (_CRIT_RE.search(l) for l in lines) if m)


def _harking_one(old, new, minus, plus):
    """单个 commit：阈值字面量变化是否伴随出处字符串改动。"""
    if not any(any(k in l for k in _SRC_MARK) for l in (minus + plus)):
        return []
    out = []
    for name in sorted(set(old) & set(new)):
        if old[name] == new[name]:
            continue
        # 阈值的字面量变了
        out.append(
            "[R22 HARKing 嫌疑] 判据 %s 阈值 %s -> %s 与出处字符串改动发生在同一 commit —— "
            "阈值应先从独立来源定标再跑测试，而不是先跑不过再调阈值" % (
                name, old[name], new[name]))
    return out


def check_harking(relpath="tests/harness.py"):
    """返回 (issues, n_commits, note)。

    判据: 同一 commit 里既改阈值字面量、又改出处字符串 → 疑似"先调参后补出处"。
    """
    txt = _git_log_patch(relpath)
    if txt is None:
        return [], 0, "无 git 仓库或取不到历史，本项未核验（不冒充通过）"
    commits = re.split(r"^commit [0-9a-f]{7,}", txt, flags=re.M)[1:]
    if not commits:
        return [], 0, "该文件无历史改动，本项不适用"
    issues, n = [], 0
    for body in commits:
        lines = body.splitlines()
        minus = [l[1:] for l in lines if l.startswith("-") and not l.startswith("---")]
        plus = [l[1:] for l in lines if l.startswith("+") and not l.startswith("+++")]
        n += 1
        issues.extend(_harking_one(_crit_of(minus), _crit_of(plus), minus, plus))
    return issues, n, ""


def run(crit=None):
    issues, compared, uncompared = check_selfconsistency(crit)
    h, ncommits, note = check_harking()
    issues.extend(h)
    return issues, dict(compared=compared, uncompared=uncompared,
                        commits=ncommits, note=note)


def self_check():
    import base.assertrun as _ar
    chk = _ar.Checker("tools/provenance")
    # A: 造一个自相矛盾的条目，必须被抓到
    bad = [("penetration_m", 0.01, "Box2D 官方 b2_common.h: linearSlop = 0.005")]
    iss, _, _ = check_selfconsistency(bad)
    chk.eq("自相矛盾必须被抓到", len(iss), 1)
    # A: 自洽的不应报
    good = [("penetration_m", 0.005, "Box2D 官方源码 b2_common.h: #define b2_linearSlop 0.005")]
    iss2, cmp2, _ = check_selfconsistency(good)
    chk.eq("自洽不应报", len(iss2), 0)
    chk.eq("自洽计入已比对", cmp2, 1)
    # A: 无锚点 -> 未比对，不误报
    iss3, cmp3, unc3 = check_selfconsistency([("jitter_px", 0.1, "工程经验值")])
    chk.eq("无锚点不误报", len(iss3), 0)
    chk.eq("无锚点计入未比对", ("jitter_px" in unc3), True)
    # B: 正则能解析判据条目
    m = _CRIT_RE.search('"penetration_m": (0.005, "<", "Box2D slop=0.005")')
    chk.eq("判据条目可解析", (m.group(1), m.group(2)), ("penetration_m", "0.005"))
    return 0 if chk.report(verbose=True) else 1


def main():
    if "--self-check" in sys.argv:
        sys.exit(self_check())
    issues, info = run()
    print("=== R22 阈值溯源与 HARKing 探测 ===")
    print("出处自洽：已比对 %d 条，未比对 %d 条（无锚点/多值，不冒充通过）：%s"
          % (info["compared"], len(info["uncompared"]),
             ", ".join(info["uncompared"][:8]) or "无"))
    if info["note"]:
        print("HARKing：%s" % info["note"])
    else:
        print("HARKing：扫描 %d 个 commit" % info["commits"])
    if not issues:
        print("OK  未发现自相矛盾或先调参后补出处")
        return 0
    for s in issues:
        print(s)
    print("共 %d 条" % len(issues))
    return 1


if __name__ == "__main__":
    sys.exit(main())
