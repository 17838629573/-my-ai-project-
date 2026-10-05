# -*- coding: utf-8 -*-
"""R14 三表一致性 —— 能力注册表 / 用例执行表 / 桥接器 交叉校验。

为什么需要它（历史事故，全部是"单看一个文件都对，交叉起来崩"）:
  1. climb.py 197 行写完、self_check 通过，但 run_all 的导入表没有它
     → 对外显示"STUB 缺能力"，一个已实现的能力被自己的门禁误报成缺失
  2. EXEC = {"F35": case_A1} 两个用例 ID 指向同一函数
     → F35「60 秒漂移」实际只跑了 A1 的 48 帧，还报 PASS
  3. CAP 注册 30 项，能被时间线真正驱动的只有 7 项
     → README 写"17 项已实现"，实际能串成片的不到一半

方法论来源: 交叉引用完整性 (cross-reference integrity)。
  单一视图自洽不等于系统自洽；注册/接线/执行三处必须互为闭包。
  与 R11（出处不可缺失）互补：R11 管"有没有写依据"，R14 管"有没有真接上"。

用法:
    python3 _proc/tools/consistency.py
"""
import ast
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RUN_ALL = os.path.join(ROOT, "tests", "run_all.py")


def _parse(path):
    with open(path, "r", encoding="utf-8") as f:
        return ast.parse(f.read(), filename=path)


def exec_table():
    """从 run_all.py 抽 EXEC 字典：{用例ID: 函数名}。"""
    tree = _parse(RUN_ALL)
    out = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Name) and tgt.id in ("EXEC", "CASES", "TABLE"):
                if isinstance(node.value, ast.Dict):
                    for k, v in zip(node.value.keys, node.value.values):
                        if isinstance(k, ast.Constant) and isinstance(v, ast.Name):
                            out[str(k.value)] = v.id
    return out


def case_funcs():
    """tests/ 下所有 case_XX 函数名（含 cases_*.py 里定义的）。"""
    tdir = os.path.join(ROOT, "tests")
    out = set()
    for fn in sorted(os.listdir(tdir)):
        if not fn.endswith(".py"):
            continue
        try:
            tree = _parse(os.path.join(tdir, fn))
        except SyntaxError:
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.FunctionDef) and n.name.startswith("case_"):
                out.add(n.name)
    return out


def import_list():
    """tests/ 下所有用例文件导入的模块名集合。

    只扫 run_all.py 会大量误报：throw / catch 等由 cases_*.py 内部导入，
    能力名也未必等于模块名（walk 能力定义在 gait.py）。
    扫整个 tests 包才是"有没有真接上"的正确粒度。

    三种写法都要抽，漏一种就满屏假阳性:
      1. from x.y import z        （静态）
      2. __import__("motion.character.gait")   （循环动态导入）
      3. 字符串元组 ("gait","run",...) 供上面循环遍历
    """
    tdir = os.path.join(ROOT, "tests")
    trees = []
    for fn in sorted(os.listdir(tdir)):
        if fn.endswith(".py"):
            try:
                trees.append(_parse(os.path.join(tdir, fn)))
            except SyntaxError:
                pass
    names = set()
    for tree in trees:
        for n in ast.walk(tree):
            if isinstance(n, ast.ImportFrom):
                for a in n.names:
                    names.add(a.name)
            elif isinstance(n, ast.Import):
                for a in n.names:
                    names.add(a.name.split(".")[-1])
            elif isinstance(n, ast.Call):
                f = getattr(n.func, "id", None)
                if f in ("__import__", "import_module") and n.args:
                    a = n.args[0]
                    if isinstance(a, ast.Constant) and isinstance(a.value, str):
                        names.add(a.value.split(".")[-1])
        # 字符串元组 / 列表（动态导入的遍历源）
        for n in ast.walk(tree):
            if isinstance(n, (ast.Tuple, ast.List)):
                for e in n.elts:
                    if isinstance(e, ast.Constant) and isinstance(e.value, str):
                        names.add(e.value.split(".")[-1])
    return names


def cap_registered():
    """AST 扫描 @capability 装饰器登记的能力名（不 import，避免导入不全）。"""
    names = set()
    for dirpath, _dn, files in os.walk(ROOT):
        if "__pycache__" in dirpath or "_bak" in dirpath:
            continue
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                tree = _parse(p)
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                for d in node.decorator_list:
                    call = d if isinstance(d, ast.Call) else None
                    if call is None:
                        continue
                    fname = getattr(call.func, "id", None) or getattr(call.func, "attr", None)
                    if fname == "capability" and call.args:
                        a = call.args[0]
                        if isinstance(a, ast.Constant):
                            names.add(str(a.value))
    return names


def bridge_kinds():
    """capbridge 的分类结果 {能力名: POSE/ADDITIVE/PHYS/AUX}。

    只有 POSE / ADDITIVE 需要被 run_all 接线才谈得上"能出片"；
    PHYS（物理仿真）与 AUX（群体/求解器）根本不产生姿态，
    把它们算进"未接线"就是纯噪音 —— 会像 R1 的假阳性一样把真问题埋掉。
    """
    try:
        from motion import capbridge
        _ok, res = capbridge.audit()
        return res if isinstance(res, dict) else {}
    except Exception:                                  # noqa: BLE001
        return {}


def run():
    """返回问题列表。"""
    ex = exec_table()
    cf = case_funcs()
    imp = import_list()
    cap = cap_registered()
    kinds = bridge_kinds()
    pose = {n for n, k in kinds.items() if k == "POSE"}
    issues = []

    # 1) 别名映射：多个用例 ID 指向同一函数 —— F35 事故的直接探测
    rev = {}
    for cid, fn in ex.items():
        rev.setdefault(fn, []).append(cid)
    for fn, cids in rev.items():
        if len(cids) > 1:
            issues.append("[R14 别名映射] 用例 %s 全部指向 %s —— "
                          "疑似复制粘贴假通过，需确认各自真的跑了不同数据"
                          % ("/".join(sorted(cids)), fn))

    # 2) 用例 ID 有但没有对应 case_ 函数体
    for cid, fn in ex.items():
        if fn not in cf:
            issues.append("[R14 用例无实现] %s -> %s 在 run_all 里找不到该函数" % (cid, fn))

    # 3) 已注册能力但 run_all 没导入 —— climb 事故
    unimported = sorted(c for c in cap if c not in imp and c not in pose)
    for c in unimported:
        issues.append("[R14 注册未接线] 能力 %r 已注册但 run_all 未导入 —— "
                      "已实现的能力会被门禁误报成 STUB" % c)

    # 4) 注册了但桥接器判定不可驱动
    if pose:
        undrivable = sorted(c for c in cap if c in imp and c not in pose)
        for c in undrivable:
            issues.append("[R14 注册不可驱动] 能力 %r 进了导入表，"
                          "但签名/返回格式无法被时间线驱动" % c)
    return issues


def self_check():
    issues = run()
    ex = exec_table()
    print("三表一致性")
    print("  EXEC 用例 %d 个   注册能力 %d 项" % (len(ex), len(cap_registered())))
    if not issues:
        print("  无交叉不一致")
        return 0
    for s in issues:
        print("  " + s)
    return 1


if __name__ == "__main__":
    sys.exit(self_check())
