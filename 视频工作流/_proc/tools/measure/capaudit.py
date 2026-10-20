# 契约: proc/tools/capaudit
#   一句话: 能力可驱动性审计：注册进 CAP 不等于能被时间线驱动
#   完整契约见 tools/__init__.py
#   依据: ADAPT blend node 分层与 UE additive/override 之分：
#         能力分 POSE/ADDITIVE/PHYS/AUX 四类，只有 POSE 能产出 21 关节供时间线合成。
# -*- coding: utf-8 -*-
"""能力可用性审计：CAP 里注册的能力，能否被 beat.Timeline 真正调用。

契约（beat.py _blend_pose）：
    CAP[name](u, params) -> {joint: (u,v) 或 (u,v,w)}
判定：
    SIG   签名能否接受 (u, params) 两个位置参数
    CALL  u=0.5 实调是否崩
    FMT   返回值是否为扁平 {关节名: 长度2/3序列}
"""
import os, sys, inspect, traceback

_H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.dirname(_H), _H):
    if p not in sys.path:
        sys.path.insert(0, p)

# 必须先关掉 motion 的「导入即注册」：
# motion/__init__ 会自动 init_capabilities()，而 capbridge.normalize 会**就地 del**
# 把非 POSE 能力从 CAP 里删掉。审计要的是全量 51 项的原始表，
# 拿到被 normalize 过的残表再归一化一次，只会把 climb/run 等进一步删没
# （2026-10-11 实测：可驱动从 10 掉到 8，纯属工具自身状态污染）。
# 因此本工具自己控制导入与归一化时机。
os.environ.setdefault("MOTION_NO_AUTOINIT", "1")

from motion import beat
import motion.character as C          # 触发子模块注册
IMPORT_ERRS = []          # 导入失败登记簿：吞掉会让能力被误报成 STUB


def _probe_imports():
    """触发子模块注册；导入失败登记而非吞掉——吞掉会让能力被误报成 STUB"""
    # 为什么改成自动遍历：2026-10-11 实测本表硬编码 13 个 character 子模块，
    # 漏了 creature/ 与 phenom/，于是 climb_rock 从未被导入、
    # 审计报「可驱动 10」而真值是 11 —— 工具清单滞后制造了假数字，
    # 与 motion/__init__ 显式清单漏同步是同一个病（本项目已复发多次）。
    # 用 pkgutil.walk_packages 自动发现，新增子包无需改本工具。
    # 出处: Python 官方 pkgutil 文档。
    import pkgutil, importlib
    import motion as _M
    errs = []
    for mi in sorted(pkgutil.walk_packages(_M.__path__, "motion."),
                     key=lambda m: m.name):
        try:
            importlib.import_module(mi.name)
        except Exception as e:
            errs.append((mi.name, repr(e)))
    return errs


def _by_design_set():
    """经 capbridge 归一化后取「设计如此」集合（ADDITIVE/PHYS/AUX）。

    出处: capbridge 按 ADAPT blend node 分层 + UE additive/override 之分做四类分流；
    直接调 CAP 表会把「设计如此」的增量/物理/求解器误判成不可用。
    """
    from motion import capbridge
    out = capbridge.normalize(beat.CAP, getattr(beat, "CAP_SRC", {}),
                              getattr(beat, "CAP_GROUP", {}), verbose=False)
    nm = lambda k: [x[0] if isinstance(x, tuple) else x for x in out[k]]
    return set(nm("ADDITIVE")) | set(nm("PHYS")) | set(nm("AUX"))


def _sig_check(fn):
    """签名能否以 (u, params) 两个位置参数调用"""
    try:
        sp = inspect.signature(fn)
        ps = [p for p in sp.parameters.values()
              if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        has_var = any(p.kind == p.VAR_POSITIONAL
                      for p in sp.parameters.values())
        req = [p for p in ps if p.default is p.empty]
        ok = has_var or (len(ps) >= 2 and len(req) <= 2)
        return ok, "params=%s" % [p.name for p in ps][:4]
    except Exception as e:
        return False, "sig err %s" % e


def _call_check(fn):
    """实调是否崩 + 返回值是否为扁平关节表 {关节名: 长度2/3序列}"""
    try:
        j = fn(0.5, {"body_h": 1.70, "dur": 1.0, "speed": 0.67,
                     "mileage": 0.0, "preset": "natural"})
    except Exception as e:
        return False, False, "%s: %s" % (type(e).__name__, str(e)[:44])
    if not (isinstance(j, dict) and j):
        return True, False, "返回 %s" % type(j).__name__
    vals = list(j.values())[:3]
    flat = all(hasattr(v, "__len__") and not isinstance(v, (str, bytes))
               and len(v) in (2, 3)
               and all(isinstance(c, (int, float)) for c in v)
               for v in j.values())
    note = ("%d 关节" % len(j)) if flat else "返回非扁平: %r" % (vals[:2],)
    return True, flat, note


def _audit_one(fn):
    """单能力三查：签名 → 实调 → 返回格式，任一环失败即不可用"""
    sig_ok, note = _sig_check(fn)
    if not sig_ok:
        return sig_ok, False, False, note
    call_ok, fmt_ok, note = _call_check(fn)
    return sig_ok, call_ok, fmt_ok, note


def _why(r):
    """不可用原因拼接: 签名 / 调用崩 / 格式（三者可并存）。"""
    why = []
    if not r[1]:
        why.append("签名")
    if not r[2]:
        why.append("调用崩")
    if not r[3]:
        why.append("格式")
    return "+".join(why) if why else "格式"


def _report(rows):
    """打印审计结论；返回 (可驱动列表, 不可用列表)"""
    full = [r for r in rows if all(r[1:4])]
    bad = [r for r in rows if not all(r[1:4])]
    print("\n可被 Timeline 直接调用: %d / %d" % (len(full), len(rows)))
    print("  " + ", ".join(r[0] for r in full))
    print("不可用 %d 个:" % len(bad))
    for r in bad:
        print("  %-14s %s  %s" % (r[0], _why(r), r[4]))
    return [r[0] for r in full], [r[0] for r in bad]


def run():
    """执行审计并打印结果；返回 (可驱动列表, 不可用列表)。

    为什么包成函数: 原来是顶层裸脚本，import 本模块就会跑一遍审计并打印，
    违反「工具必须可安全导入」的契约。
    """
    IMPORT_ERRS.extend(_probe_imports())
    if IMPORT_ERRS:
        print("[capaudit] 子模块导入失败 %d 项:" % len(IMPORT_ERRS))
        for _n, _e in IMPORT_ERRS:
            print("   %s -> %s" % (_n, _e))
    # normalize 会就地 del，必须先记录总数
    _TOTAL = len(beat.CAP)
    try:
        _BY_DESIGN = _by_design_set()
    except Exception:
        _BY_DESIGN = set()
    print("CAP 共 %d 个" % _TOTAL)
    print("正确口径(capbridge): POSE 可驱动 %d / ADDITIVE+PHYS+AUX 设计如此 %d\n"
          % (_TOTAL - len(_BY_DESIGN), len(_BY_DESIGN)))
    print("%-14s %-6s %-6s %-6s  %s" % ("能力", "签名", "调用", "格式", "实测"))
    print("-" * 78)
    rows = []
    for name in sorted(beat.CAP):
        if name in _BY_DESIGN:
            continue
        sig_ok, call_ok, fmt_ok, note = _audit_one(beat.CAP[name])
        rows.append((name, sig_ok, call_ok, fmt_ok, note))
        print("%-14s %-6s %-6s %-6s  %s" % (
            name, "OK" if sig_ok else "NG", "OK" if call_ok else "NG",
            "OK" if fmt_ok else "NG", note))
    return _report(rows)


def self_check():
    """自检：走 capbridge 正确口径后，POSE 类应全部可驱动，不可用为 0。

    断言「不可用==0」而非「可驱动==总数」：后者会把设计如此的
    ADDITIVE/PHYS/AUX 也算进来，口径错。
    """
    full, bad = run()
    ok = (not bad) and len(full) >= 1
    print("[capaudit self_check] 可驱动=%d 不可用=%d -> %s"
          % (len(full), len(bad), "PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    sys.exit(0 if self_check() else 1)
