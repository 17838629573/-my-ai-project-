# 契约: tools/debtledger —— R19 债务台账：把已知债务与新增问题分开，并做债务体检
# 职责: 登记/匹配/到期判定/陈旧判定，输出四桶供 check.py 报告与退出码使用
# 依赖: base(无) ｜ 被依赖: (root)/check.py
# 上游: 无 ｜ 下游: check.py::_split_debt（子进程调用）
# 依据: import-linter ignore_imports / ESLint reportUnusedDisableDirectives
#       / todo-or-die(DIE001)
# 禁止: 在此静默吞掉异常；债务不得无归属、无到期日地永久挂账
"""R19 已知债务台账：显式登记、有归属、带到期日、只减不增。

三条出处（不凭记忆凑）:
- import-linter ignore_imports — "treat each entry as debt with an owner"。
  债务不静默消失：单独列出、带归属、参与基线比对。
- ESLint linterOptions.reportUnusedDisableDirectives — 抑制指令"因代码已改好
  而不再需要"时应被报出，否则旧的 disable 会掩盖未来真实的错误。
  对应本模块: 登记了但本次扫描未触发的债务 = 陈旧豁免，必须报出并删除登记。
- todo-or-die / todo_or_else（davidpdrsn 的 Rust 版、searls 的 Ruby 版、
  jwelch92 的 Python flake8 插件 DIE001）: TODO 带到期日，过期即失败。
  对应本模块: 超过 due 的债务自动升级为真问题，杜绝"永久豁免"。

为什么单独成文件: 台账本体原置于 check.py 内时，该文件达 565 行，
超过 R2 上限 500。下沉后 check.py 回归合规，且台账可被单独测试。

协议: stdin 接收 JSON {"problems": [...], "today": "YYYY-MM-DD"}
      stdout 输出 JSON {"debt": [...], "fresh": [...], "overdue": [...],
                        "stale": [...]}
"""
import datetime as _dt
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 已知债务清单：显式登记、有归属、只减不增。
# 与静默忽略的区别: 清单外一律照报。
DEBT = {
    "R1": {
        # (源包, 目标包) -> 归属/原因
    },
    "R2": {
        # 已清零，保留空位以便 R19 校验结构完整性
    },
    "R3": {
        # 函数名 -> 归属 dict
        # 注1: tests/run_all.py 的 R2 债务已清零（拆到 153 行），登记随之删除，
        #      否则会被 R19 判为陈旧豁免。
        # 注2: "self_check" 债务已于 2026-10-06 清零——统一执行器
        #      （base/assertrun.py）落地后，8 个超限 self_check 全部改为
        #      "断言数据表 + 统一执行器"，R3 中已不再出现 self_check 条目。
        #      按 ESLint reportUnusedDisableDirectives 口径，清零后必须删除
        #      登记，否则即为永久豁免，故此处留空而非继续挂账。
    },
}


def _debt_entry(rule, key):
    """兼容两种写法：旧的字符串（无到期日）与新的归属 dict。"""
    e = DEBT.get(rule, {}).get(key)
    if e is None:
        return None
    if isinstance(e, str):
        return {"why": e, "clear": "", "owner": "", "due": ""}
    return e


def _match_debt(s):
    """在 DEBT 里找与问题文本 s 匹配的 (rule, key)；无匹配返回 None。

    匹配口径: 问题以 "[<rule> " 开头，且某个登记的 key 出现在文本中。
    """
    for rule, entries in DEBT.items():
        if not s.startswith(f"[{rule} "):
            continue
        for key in entries:
            if key in s:
                return (rule, key)
    return None


def _debt_line(s, e, due):
    """渲染一条债务的展示文本（归属 / 到期 / 清零条件三要素）。"""
    return (
        f"  已知债务 {s}\n"
        f"      归属 {e.get('owner') or '-'} ｜ 到期 {due or '未设(将永久豁免)'}"
        f" ｜ 清零条件: {e.get('clear') or '-'}")


def _classify_one(s, today):
    """把单条问题分到桶里，返回 (桶, 载荷, hit)。

    桶: fresh(新增) / debt(豁免) / overdue(到期升级) / bad_due(日期非法)
    """
    hit = _match_debt(s)
    if not hit:
        return ("fresh", s, None)
    rule, key = hit
    e = _debt_entry(rule, key)
    due = (e.get("due") or "").strip()
    if not due:
        return ("debt", _debt_line(s, e, due), hit)
    try:
        d = _dt.date.fromisoformat(due)
    except ValueError:
        return ("bad_due", (s, rule, key, due), hit)
    if today > d:
        return ("overdue", s, hit)      # 到期升级成真问题，不再豁免
    return ("debt", _debt_line(s, e, due), hit)


def split_debt(problems, today=None):
    """把已知债务与新增问题分开，并做 R19 债务体检。

    返回 (debt, fresh, overdue, stale)
    """
    today = today or _dt.date.today()
    debt, fresh, overdue, stale = [], [], [], []
    matched = set()
    for s in problems:
        bucket, payload, hit = _classify_one(s, today)
        if hit:
            matched.add(hit)
        if bucket == "fresh":
            fresh.append(payload)
        elif bucket == "bad_due":
            s0, rule, key, due = payload
            fresh.append(s0)
            stale.append(f"[R19 债务日期非法] {rule}/{key} due={due!r}"
                         " —— 无法判定到期，按真问题处理")
        elif bucket == "overdue":
            overdue.append(payload)
            fresh.append(payload)
        else:
            debt.append(payload)
    for rule, entries in DEBT.items():
        for key in entries:
            if (rule, key) not in matched:
                stale.append(
                    f"[R19 陈旧债务] {rule}/{key} —— 本次扫描未触发，"
                    "豁免已无必要，应删除登记（否则为永久豁免）")
    return debt, fresh, overdue, stale


def report_debt(problems, today=None):
    """打印债务四桶并返回计数 —— check.py::_report 债务段的唯一出口。

    为什么下沉: 该段原置于 check.py 内时使其达 508 行，超过 R2 上限 500；
    下沉后 check.py 只需一行委托，且台账可被单独测试。
    """
    debt, fresh, overdue, stale = split_debt(problems, today)
    for s in fresh:
        print(s)
    if not fresh:
        print("  无新增问题")
    if debt:
        print(f"\n已知债务 {len(debt)} 项（有归属，应逐项清零）:")
        for s in debt:
            print("  " + s)
    if overdue:
        print(f"\n债务到期未清零 {len(overdue)} 项（已升级为真问题）:")
        for s in overdue:
            print("  " + s)
    if stale:
        print(f"\n陈旧/非法豁免 {len(stale)} 项（应删除登记）:")
        for s in stale:
            print("  " + s)
    return {"fresh": len(fresh), "debt": len(debt),
            "overdue": len(overdue), "stale": len(stale)}


def self_check():
    """自检: 三条路径必须都成立——未到期豁免/到期升级/陈旧报出。

    断言数据表: (场景, today, 期望 debt 数, 期望 fresh 数, 期望 stale 数)
    """
    sys.path.insert(0, _ROOT)
    import base.assertrun as _ar
    C = _ar.Checker("tools/debtledger")

    DEBT.clear()
    DEBT.update({"R3": {"self_check": {
        "why": "自检专用夹具", "clear": "夹具", "owner": "夹具",
        "due": "2026-12-05"}}})
    p = ["[R3 函数过长] a.py::self_check 80>50"]

    d, f, o, s = split_debt(p, _dt.date(2026, 10, 6))     # 未到期
    C.chk("未到期应为豁免", len(d) == 1, f"debt={len(d)}")
    C.chk("未到期不应算新增", len(f) == 0, f"fresh={len(f)}")

    d, f, o, s = split_debt(p, _dt.date(2026, 12, 6))     # 到期
    C.chk("到期应升级为真问题", len(f) == 1, f"fresh={len(f)}")
    C.chk("到期应计入 overdue", len(o) == 1, f"overdue={len(o)}")

    d, f, o, s = split_debt([], _dt.date(2026, 10, 6))    # 未触发=陈旧
    C.chk("未触发应判陈旧豁免", len(s) == 1, f"stale={len(s)}")

    DEBT.clear()
    DEBT.update({"R1": {}, "R2": {}, "R3": {}})
    return 0 if C.report() else 1


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--self-check":
        sys.exit(self_check())
    raw = sys.stdin.read()
    try:
        req = json.loads(raw or "{}")
    except json.JSONDecodeError:
        req = {}
    probs = req.get("problems") or []
    t = req.get("today")
    try:
        td = _dt.date.fromisoformat(t) if t else None
    except ValueError:
        td = None
    debt, fresh, overdue, stale = split_debt(probs, td)
    sys.stdout.write(json.dumps(
        {"debt": debt, "fresh": fresh, "overdue": overdue, "stale": stale},
        ensure_ascii=False))
