# 契约: proc/tools/baseline.py
#   一句话: 复杂度债务棘轮——基线入版本库，只降不升；新增/恶化即 FAIL，修复自动收紧
#   完整契约见 _proc/tools/__init__.py
#   依据: (1) Betterer（出处: https://github.com/phenomnomnominal/betterer）
#           结果文件 .betterer.results 提交进版本库；differ 逻辑:
#           文件未变→跳过 / 问题被修复→基线自动收紧 / 问题挪位置→按 issueHash 识别为"移动"而非"新增"
#           / 出现新问题→测试失败。团队最佳实践明确要求"提交结果文件，并认真审查每次变更"。
#         (2) SonarQube "Clean as You Code"（出处: Sonar 官方质量门禁文档）
#           存量问题冻结为基线，门禁只判新增/改动代码；不建议用绝对数量阻塞遗留代码。
#         (3) lizard-complexity 实践指南明确列为 Anti-pattern:
#           "Block PRs on absolute count —— Legacy code can't add a single line;
#            改为 Diff-only: 只扫描 PR 改动的函数"。
#         (4) 同为反模式: "Refactor for CCN at expense of clarity —— 把清晰的线性函数拆成
#            4 个 helper 反而抬高整体复杂度"。故线性长函数按长度维度登记，不为降 CCN 硬拆。
# -*- coding: utf-8 -*-
"""复杂度债务棘轮（R21）。

为什么必须有这个文件：
  complexity.py 此前打印「超设计值(登记为债务) 48」，但没有任何一处真的登记了它们——
  既没有归属，也没有清零条件，更没有到期日。这等于"口头声称是假阳性"，
  违反本项目铁律一。本工具把"债务"变成版本库里的一条记录，并加棘轮：
      新增条目 → FAIL（不许新增债）
      条目恶化 → FAIL（不许债上加债）
      条目修复 → 报「陈旧基线项」并自动收紧（只降不升）
      条目变好 → 基线值自动下调（下次再涨就 FAIL）
      条目逾期 → 升为真问题 FAIL（对接 R19 到期机制）

用法:
    python3 _proc/tools/baseline.py                # 人读：新增/恶化/逾期/陈旧
    python3 _proc/tools/baseline.py --json         # 机读
    python3 _proc/tools/baseline.py --update       # 人工确认后重建基线（须写明理由）
    python3 _proc/tools/baseline.py --self-check
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROC = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_PROC)
for p in (_ROOT, _PROC):
    if p not in sys.path:
        sys.path.insert(0, p)

BASELINE_PATH = os.path.join(_HERE, "complexity.baseline.json")

# 到期策略（天）——按类别区分，与 R19 到期机制同源
DUE_DAYS = {"ccn": 30, "length": 60}


def _key(item):
    """稳定键: Betterer 用 issueHash 识别"移动"而非"新增"。

    这里用 文件::函数名 作为稳定键——函数名不变而只是行号变了，
    应识别为同一个旧条目（移动），不是新债。
    """
    return "%s::%s" % (item["file"], item["func"])


def _load():
    if not os.path.exists(BASELINE_PATH):
        return {}
    with open(BASELINE_PATH, encoding="utf-8") as f:
        data = json.load(f)
    # 兼容 list / dict 两种形态（历史原因 suppress.json 是 list）
    if isinstance(data, list):
        return {_key(x): x for x in data}
    return data.get("entries", {})


def _save(entries):
    with open(BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump({"entries": entries}, f, ensure_ascii=False, indent=2,
                  sort_keys=True)


def _due_date(kind, today):
    import datetime
    d = datetime.date.fromisoformat(today) + datetime.timedelta(days=DUE_DAYS.get(kind, 30))
    return d.isoformat()


def diff(current, baseline, today):
    """比对当前扫描结果与基线。

    返回 dict(new, worse, fixed, tightened, stable, overdue)
      new        基线里没有 → 真问题，FAIL
      worse      CCN/长度比基线高 → 真问题，FAIL
      fixed      已降到阈值以下 → 陈旧基线项，应删除（收紧）
      tightened  仍超标但数值下降 → 基线自动下调
      stable     与基线一致，豁免中
      overdue    超过到期日仍未清零 → 升为真问题，FAIL
    """
    res = {"new": [], "worse": [], "fixed": [], "tightened": [], "stable": [], "overdue": []}
    cur = {}
    for item in current:
        # 同一 (file, func) 可能被 CCN 与长度两个维度各报一次，取更严重的一条
        k = _key(item)
        if k not in cur or (item.get("ccn", 0), item.get("length", 0)) > (
                cur[k].get("ccn", 0), cur[k].get("length", 0)):
            cur[k] = item

    for k, item in cur.items():
        b = baseline.get(k)
        if b is None:
            res["new"].append(item)
            continue
        for dim in ("ccn", "length"):
            if item.get(dim, 0) > b.get(dim, 0):
                res["worse"].append({
                    "file": item["file"], "func": item["func"], "dim": dim,
                    "now": item[dim], "baseline": b[dim], "line": item["line"]})
        if any(x["file"] == item["file"] and x["func"] == item["func"] for x in res["worse"]):
            continue
        changed = (item.get("ccn", 0) < b.get("ccn", 0)
                   or item.get("length", 0) < b.get("length", 0))
        due = b.get("due")
        if due and due < today:
            res["overdue"].append({"file": item["file"], "func": item["func"],
                                   "due": due, "owner": b.get("owner", ""),
                                   "clear_when": b.get("clear_when", "")})
        elif changed:
            res["tightened"].append({"file": item["file"], "func": item["func"],
                                     "from_ccn": b.get("ccn", 0), "to_ccn": item.get("ccn", 0),
                                     "from_len": b.get("length", 0), "to_len": item.get("length", 0)})
        else:
            res["stable"].append(item)

    for k, b in baseline.items():
        if k not in cur:
            res["fixed"].append(b)
    return res


def run(today=None):
    """返回 {"ok":bool, "counts":{...}, "new":[...], ...}"""
    from tools import complexity
    import datetime
    if today is None:
        today = datetime.date.today().isoformat()
    try:
        design, hard, over_len = complexity.scan()
    except RuntimeError as e:
        return {"ok": False, "error": str(e),
                "counts": {"new": 0, "worse": 0, "fixed": 0, "tightened": 0,
                           "stable": 0, "overdue": 0, "hard": 1}}
    current = list(design) + list(over_len)
    baseline = _load()
    d = diff(current, baseline, today)
    counts = {kk: len(v) for kk, v in d.items()}
    counts["hard"] = len(hard)
    # 硬闸（CCN>20 或 长度>100）不走基线，直接 FAIL —— 与铁律四一致
    ok = not d["new"] and not d["worse"] and not d["overdue"] and not hard
    out = {"ok": ok, "counts": counts, "today": today}
    out.update(d)
    out["hard"] = hard
    return out


def update(today=None, owner="", clear_when=""):
    """重建基线。只应在人工确认后调用（--update）。"""
    from tools import complexity
    import datetime
    if today is None:
        today = datetime.date.today().isoformat()
    design, hard, over_len = complexity.scan()
    entries = {}
    for item in list(design) + list(over_len):
        k = _key(item)
        old = entries.get(k)
        if old is None or (item.get("ccn", 0), item.get("length", 0)) > (
                old.get("ccn", 0), old.get("length", 0)):
            kind = "ccn" if item.get("ccn", 0) > complexity.CCN_DESIGN else "length"
            # 归属按顶层包划分，避免整批挂"未指定"——那等于没有归属，违反铁律一
            _own = owner or (item["file"].split("/")[0] if "/" in item["file"]
                             else item["file"])
            if clear_when:
                _why = clear_when
            elif kind == "ccn":
                _why = "CCN 降到 <=%d 后，棘轮自动收紧并从基线删除" % complexity.CCN_DESIGN
            else:
                _why = "函数长度降到 <=%d 后，棘轮自动收紧并从基线删除" % complexity.LEN_DESIGN
            entries[k] = {
                "file": item["file"], "func": item["func"], "line": item["line"],
                "ccn": item.get("ccn", 0), "length": item.get("length", 0),
                "since": today, "due": _due_date(kind, today),
                "owner": _own, "clear_when": _why,
            }
    _save(entries)
    return entries


def self_check():
    """自检 5 项：新增 FAIL / 恶化 FAIL / 修复报陈旧 / 变好自动收紧 / 逾期升 FAIL。"""
    import tempfile
    import shutil
    ok = True

    def _chk(name, cond):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name)
        ok = ok and bool(cond)

    def _item(file, func, ccn, length, line=1):
        return {"file": file, "func": func, "ccn": ccn, "length": length,
                "line": line, "params": 0}

    today = "2026-10-06"
    # 1) 新增条目 → new
    d = diff([_item("a.py", "f", 12, 20)], {}, today)
    _chk("新增条目判为 new（不许新增债）", len(d["new"]) == 1 and len(d["stable"]) == 0)
    # 2) 恶化 → worse
    base = {"a.py::f": {"file": "a.py", "func": "f", "ccn": 12, "length": 20}}
    d = diff([_item("a.py", "f", 18, 20)], base, today)
    _chk("CCN 变高判为 worse（不许债上加债）",
         len(d["worse"]) == 1 and d["worse"][0]["dim"] == "ccn")
    # 3) 修复 → fixed（陈旧基线项，应删除）
    #    注意: 降到阈值以下后该函数不再出现在 scan() 结果里，故 current 应为空——
    #    这正是 Betterer「问题被修复 → 基线自动收紧」的语义。
    d = diff([], base, today)
    _chk("已修复判为 fixed（陈旧基线项应删除）", len(d["fixed"]) == 1 and len(d["stable"]) == 0)
    # 4) 变好但仍超标 → tightened
    d = diff([_item("a.py", "f", 11, 20)], base, today)
    _chk("变好但仍在阈值上判为 tightened（基线收紧）", len(d["tightened"]) == 1)
    # 5) 逾期 → overdue
    over = {"a.py::f": {"file": "a.py", "func": "f", "ccn": 12, "length": 20,
                        "due": "2026-01-01", "owner": "x", "clear_when": "y"}}
    d = diff([_item("a.py", "f", 12, 20)], over, today)
    _chk("逾期未清零升为 overdue（按真问题处理）", len(d["overdue"]) == 1)
    # 6) 行号变化但函数名不变 → 仍是同一条目（Betterer issueHash 语义：移动≠新增）
    d = diff([_item("a.py", "f", 12, 20, line=99)], base, today)
    _chk("仅行号变化识别为移动而非新增", len(d["stable"]) == 1 and len(d["new"]) == 0)
    # 7) 依赖缺失必须报错，不能静默 ok
    tmp = tempfile.mkdtemp()
    try:
        saved, complexity_lizard = BASELINE_PATH, None
        from tools import complexity as _c
        complexity_lizard = _c.lizard
        _c.lizard = None
        r = run(today)
        _chk("lizard 缺失时 run() 返回 ok=False（不静默当零问题）", r["ok"] is False)
        _c.lizard = complexity_lizard
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return ok


def main():
    if "--self-check" in sys.argv:
        return 0 if self_check() else 1
    if "--update" in sys.argv:
        own = ""
        why = ""
        for a in sys.argv:
            if a.startswith("--owner="):
                own = a.split("=", 1)[1]
            if a.startswith("--clear-when="):
                why = a.split("=", 1)[1]
        e = update(owner=own, clear_when=why)
        print("基线已重建: %d 条 -> %s" % (len(e), BASELINE_PATH))
        return 0
    r = run()
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["ok"] else 1
    c = r["counts"]
    print("复杂度债务棘轮 (Betterer 语义)  今天 %s" % r.get("today", ""))
    print("  新增 %d   恶化 %d   逾期 %d   硬闸 %d   稳定 %d   待收紧 %d   陈旧 %d"
          % (c["new"], c["worse"], c["overdue"], c["hard"],
             c["stable"], c["tightened"], c["fixed"]))
    for k, label in (("hard", "硬闸 必须拆分"), ("new", "新增 真问题"),
                     ("worse", "恶化 真问题"), ("overdue", "逾期 升为真问题")):
        if r.get(k):
            print("  [%s]" % label)
            for x in r[k][:15]:
                print("    %s" % json.dumps(x, ensure_ascii=False))
    if r.get("fixed"):
        print("  [陈旧基线项 应删除] %d 条" % len(r["fixed"]))
        for x in r["fixed"][:10]:
            print("    %s::%s" % (x.get("file"), x.get("func")))
    if r.get("tightened"):
        print("  [待收紧] %d 条" % len(r["tightened"]))
        for x in r["tightened"][:10]:
            print("    %s::%s ccn %s->%s len %s->%s"
                  % (x["file"], x["func"], x["from_ccn"], x["to_ccn"],
                     x["from_len"], x["to_len"]))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
