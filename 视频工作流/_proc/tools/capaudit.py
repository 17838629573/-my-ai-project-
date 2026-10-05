# 契约: proc/tools/capaudit
#   一句话: 能力可驱动性审计：注册进 CAP 不等于能被时间线驱动
#   完整契约见 tools/__init__.py
#   依据: 依据 ADAPT blend node 分层与 UE additive/override 之分：
能力分 POSE/ADDITIVE/PHYS/AUX 四类，只有 POSE 能产出 21 关节供时间线合成。
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

from motion import beat
import motion.character as C          # 触发子模块注册
for m in ("sit", "gesture", "prop", "turn", "jump", "crouch", "run",
          "carry", "throw", "catch", "kick", "climb", "pass_ball"):
    try:
        __import__("motion.character." + m)
    except Exception:
        pass
for m in ("motion.crowd", "motion.rigid", "motion.rigid2d", "motion.rigid2d_sim"):
    try:
        __import__(m)
    except Exception:
        pass

print("CAP 共 %d 个\n" % len(beat.CAP))
print("%-14s %-6s %-6s %-6s  %s" % ("能力", "签名", "调用", "格式", "实测"))
print("-" * 78)

rows = []
for name in sorted(beat.CAP):
    fn = beat.CAP[name]
    sig_ok = call_ok = fmt_ok = False
    note = ""
    try:
        sp = inspect.signature(fn)
        ps = [p for p in sp.parameters.values()
              if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)]
        npos = len(ps)
        has_var = any(p.kind == p.VAR_POSITIONAL for p in sp.parameters.values())
        req = [p for p in ps if p.default is p.empty]
        # 能否以 (u, params) 两个位置参数调用
        sig_ok = has_var or (npos >= 2 and len(req) <= 2)
        note = "params=%s" % [p.name for p in ps][:4]
    except Exception as e:
        note = "sig err %s" % e

    if sig_ok:
        try:
            j = fn(0.5, {"body_h": 1.70, "dur": 1.0, "speed": 0.67,
                         "mileage": 0.0, "preset": "natural"})
            call_ok = True
            if isinstance(j, dict) and j:
                vals = list(j.values())[:3]
                flat = all(hasattr(v, "__len__") and not isinstance(v, (str, bytes))
                           and len(v) in (2, 3) and all(
                               isinstance(c, (int, float)) for c in v)
                           for v in j.values())
                fmt_ok = flat
                note = ("%d 关节" % len(j)) if flat else "返回非扁平: %r" % (vals[:2],)
            else:
                note = "返回 %s" % type(j).__name__
        except Exception as e:
            note = "%s: %s" % (type(e).__name__, str(e)[:44])

    rows.append((name, sig_ok, call_ok, fmt_ok, note))
    print("%-14s %-6s %-6s %-6s  %s" % (
        name, "OK" if sig_ok else "NG", "OK" if call_ok else "NG",
        "OK" if fmt_ok else "NG", note))

full = [r for r in rows if all(r[1:4])]
print("\n可被 Timeline 直接调用: %d / %d" % (len(full), len(rows)))
print("  " + ", ".join(r[0] for r in full))
bad = [r for r in rows if not all(r[1:4])]
print("不可用 %d 个:" % len(bad))
for r in bad:
    why = []
    if not r[1]: why.append("签名")
    if not r[2]: why.append("调用崩")
    if not r[3]: why.append("格式")
    print("  %-14s %s  %s" % (r[0], "+".join(why) if why else "格式", r[4]))
