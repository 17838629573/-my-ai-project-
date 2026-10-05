# 契约: proc/motion/capbridge
#   一句话: 能力表分类归一 —— 姿态/增量/物理/辅助四类分流，并把非标准签名适配成 (u,params)
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""能力桥接层：把 CAP 里混装的四类东西分开。

问题（实测 tools/capaudit.py，30 个能力只有 7 个能被 Timeline 调用）：
    CAP 名义契约是「姿态函数 (u, params) -> {关节: (u,v,w)}」，
    但实际混进了四类东西，后三类根本不满足该契约：
      POSE     姿态函数，可直接驱动骨架          ← 唯一该进 _blend_pose 的
      ADDITIVE 增量函数，返回 {"J": delta}       ← 须叠加到基础姿态，不能当绝对姿态混合
      PHYS     物理仿真，返回轨迹/标量           ← group="physics"，与时间线无关
      AUX      求解器/群体函数/状态名            ← 不是姿态，供用例直接调用

不这样做会怎样：_blend_pose 拿非姿态返回值当关节字典遍历，要么崩，
要么把物理轨迹和状态字符串混进骨架，画面直接烂掉。

出处：
[1] ADAPT (Rutgers TVCG 2013)：choreographer 各操作骨架私有副本，经 blend node 汇入
[2] UE Layered Blend per Bone / Unity Avatar Mask：additive 与 override 是两种模式，
    增量不可直接当 override 用
[3] Box2D Lite (Catto GDC2006)：物理仿真独立于角色动画层，两者不同步长
"""
import inspect

# 工厂解包失败登记簿（绝不静默吞掉）
UNWRAP_ERRS = []

# 必填参数默认值（这些能力注册时没给默认，时间线无法直接调）
DEFAULTS = {"t_contact": 0.6, "gap": 0.18, "H": 1.70, "duration": 1.2}
# 返回 {"J":...} 但 J 是绝对姿态（不是增量）的能力
ABS_WITH_J = {"carry_box"}
# 明确不是姿态的（标量求解器），强制归 AUX
AUX_FORCE = {"brake", "ball", "high5"}

def _is_J(d):
    """J 必须是 {关节名: (2或3元坐标)}；标量求解器（brake 返回 v/d/u/T）不算。"""
    if not isinstance(d, dict) or not d:
        return False
    vs = list(d.values())[:4]
    return all(hasattr(v, "__len__") and not isinstance(v, (str, bytes))
               and len(v) in (2, 3) for v in vs)


def _take_J(fn):
    def w(u, params=None):
        return fn(u, params).get("J", {})
    w.__name__ = getattr(fn, "__name__", "take_J") + "_J"
    return w

# 四类注册表
POSE = {}       # name -> fn(u, params) -> {关节: (u,v,w)}
ADDITIVE = {}   # name -> fn(u, params) -> {关节: delta}   须叠加
PHYS = {}       # name -> fn(...) 物理仿真，返回轨迹/标量
AUX = {}        # name -> 原对象（求解器/群体函数/状态名），用例直接用


def _kind(fn):
    """判定一个已注册对象的类别。返回 (类别, 说明)。"""
    if not callable(fn):
        return "AUX", "非可调用"
    try:
        sp = inspect.signature(fn)
    except Exception:
        return "AUX", "取不到签名"
    ps = list(sp.parameters.values())
    names = [p.name for p in ps]
    if not ps:
        # 零参数 = 工厂，调用一次拿真实实现
        try:
            r = fn()
        except Exception as e:
            return "AUX", "工厂调用失败 %s" % type(e).__name__
        if callable(r):
            return _kind(r)
        return "AUX", "工厂返回 %s（状态名/常量，非姿态）" % type(r).__name__
    # 群体/求解器：第一参数名不是 u/ph/t 之一的，判 AUX
    if names[0] not in ("u", "ph", "phase", "t"):
        return "AUX", "首参 %r 不是 u/ph/t（求解器或群体函数）" % names[0]
    # 双参且首参 u → 姿态契约
    if names[0] == "u" and len(ps) >= 2:
        return "POSE", ""
    return "POSE", "单时间参，需适配成 (u, params)"


def _adapt(fn):
    """把 (ph, ...) / (t, ...) 等非标准签名包成 (u, params)。

    依据：时间线统一以 u∈[0,1] 段内归一化 + params 传参；
    持续型动作相位必须走全局 mileage（beat.Timeline.build_mileage），
    否则跨段重算相位会在边界一顿（见 beat.py 注释）。
    """
    ps = list(inspect.signature(fn).parameters.values())
    n0 = ps[0].name
    rest = [p.name for p in ps[1:]]
    rest = {p.name: p.default for p in ps[1:] if p.default is not inspect.Parameter.empty}

    def wrapped(u, params=None):
        params = dict(params or {})
        d = params.get("dur", 1.0)
        if n0 in ("ph", "phase"):
            # 相位驱动（如 run(ph, v, H)）：由全局里程反算相位
            mil = params.get("mileage")
            if mil is None:
                mil = float(params.get("speed", 3.2)) * float(u) * float(d)
            stride = params.get("stride", 0.1394 + 0.00465 * float(params.get("speed", 3.2)))
            arg = (mil / stride) % 1.0
        else:
            arg = float(u) * float(d)      # 时间驱动（如 brake(t,...)）
        kw = {}
        for k in rest:
            if k in params:
                kw[k] = params[k]
            elif k in DEFAULTS:
                kw[k] = DEFAULTS[k]
        return fn(arg, **kw)
    wrapped.__wrapped__ = fn
    wrapped.__name__ = getattr(fn, "__name__", "adapted")
    return wrapped


def normalize(cap, cap_src, cap_group, verbose=True):
    """就地归一化：按类别分流，能适配成 POSE 的适配后归入 POSE。返回分类字典。"""
    out = {"POSE": [], "ADDITIVE": [], "PHYS": [], "AUX": []}
    for name in sorted(list(cap)):
        fn = cap[name]
        grp = cap_group.get(name, "other")
        # 1) 物理组：直接分流，不进姿态表
        if grp == "physics":
            PHYS[name] = fn
            AUX.pop(name, None)
            out["PHYS"].append(name)
            del cap[name]
            continue
        if name in AUX_FORCE:
            AUX[name] = fn; out["AUX"].append((name, "非姿态（求解器/道具轨迹/群体）"))
            del cap[name]; continue
        kind, why = _kind(fn)
        if kind == "AUX":
            AUX[name] = fn
            out["AUX"].append((name, why))
            del cap[name]
            continue
        # 2) 姿态类：零参数工厂先解包成真实实现，再统一适配
        real = fn
        try:
            if len(inspect.signature(fn).parameters) == 0:
                r = fn()
                if callable(r):
                    real = r
        except Exception as _e:
            # 不静默：工厂解包失败会让能力被错误归类，登记后可见
            UNWRAP_ERRS.append((k, repr(_e)))
        try:
            nps = len(inspect.signature(real).parameters)
        except Exception:
            nps = 0
        nm = [p.name for p in inspect.signature(real).parameters.values()] if nps else []
        strict = (nps >= 2 and nm[0] == "u")
        probe = real if strict else _adapt(real)
        try:
            j = probe(0.5, {"dur": 1.0, "body_h": 1.70, "speed": 0.67, "mileage": 0.0})
        except Exception as e:
            AUX[name] = fn
            out["AUX"].append((name, "试调失败 %s" % type(e).__name__))
            del cap[name]
            continue
        if isinstance(j, dict) and "J" in j and isinstance(j["J"], dict) and _is_J(j["J"]):
            if name in ABS_WITH_J:          # 复合结构里 J 是绝对姿态
                cap[name] = _take_J(probe); POSE[name] = cap[name]
                out["POSE"].append(name); continue
            ADDITIVE[name] = probe
            out["ADDITIVE"].append(name)
            del cap[name]
            continue
        if isinstance(j, dict) and j and all(
                hasattr(v, "__len__") and not isinstance(v, (str, bytes))
                and len(v) in (2, 3) for v in j.values()):
            POSE[name] = probe
            cap[name] = probe
            out["POSE"].append(name)
            continue
        AUX[name] = fn
        out["AUX"].append((name, "返回 %s 不是关节字典" % type(j).__name__))
        del cap[name]

    if verbose:
        print("能力分类（capbridge.normalize）")
        print("  POSE     %2d  可直接驱动时间线: %s" % (len(out["POSE"]), ", ".join(out["POSE"])))
        print("  ADDITIVE %2d  增量叠加: %s" % (len(out["ADDITIVE"]), ", ".join(out["ADDITIVE"])))
        print("  PHYS     %2d  物理仿真: %s" % (len(out["PHYS"]), ", ".join(out["PHYS"])))
        print("  AUX      %2d  非姿态（求解器/群体/状态名）" % len(out["AUX"]))
        for n, w in out["AUX"]:
            print("      %-14s %s" % (n, w))
    return out


def add_pose(base, delta, weight=1.0):
    """增量叠加：base + delta*weight（UE additive / layer.py 同语义）。

    additive 类能力若被当成绝对姿态混合，会把偏移量当位置，骨架直接扭曲。
    """
    out = {k: tuple(v) for k, v in base.items()}
    for k, v in delta.items():
        v = tuple(v) + (0.0,) * (3 - len(v))
        if k in out:
            a = tuple(out[k]) + (0.0,) * (3 - len(out[k]))
            out[k] = (a[0] + v[0] * weight, a[1] + v[1] * weight, a[2] + v[2] * weight)
        else:
            out[k] = v
    return out
