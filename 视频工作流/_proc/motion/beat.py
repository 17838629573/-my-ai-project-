# 契约: proc/motion/beat
#   一句话: 节拍时间线：prep→stroke→relax 三相位串多段动作，含跨段无跳变与互斥校验
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""W1 —— 动作时间线（beat timeline）。

出处（先搜证再实现，不自造）：
[1] ADAPT: The Agent Development and Prototyping Testbed (Rutgers, TVCG 2013)
    · 能力函数：ReachFor(target) / GazeAt(target) / GoTo(target)
                Gesture(name) / SitDown() / StandUp()
    · 只有 sitting 与 navigating 互斥，其余可同时执行而无视觉瑕疵
    · choreographer 各自操作骨架的私有副本，经 blend nodes 汇入 pose dataflow graph
    · 调度器按固定时钟 tick（ADAPT 为 30Hz）
[2] Behavior Markup Language (BML) 1.0
    · behavior block；composition = MERGE / APPEND / REPLACE
    · 每个 request 是一个调度边界；start / end 时间戳
    · 动作相位：ready → stroke_start → stroke → stroke_end → relax
[3] Kallmann & Thalmann, Autonomous Virtual Humans (IVA 2005)
    · 手势三相位 prep / stroke / relax，各配一个 keyframe-interpolator
    · 按 emphasis point 排入 scheduler，保证时间约束下仍连续

本模块只做「调度」，不含任何动作公式：动作一律从 CAP 注册表取。
CAP 里没有的一律报错（STUB 门禁），绝不静默降级成走路。
"""
import os as _os, sys as _sys
if __package__ in (None, ""):
    _d = _os.path.dirname(_os.path.abspath(__file__))
    while _d != _os.path.dirname(_d) and _os.path.basename(_d) != "_proc":
        _d = _os.path.dirname(_d)
    for _p in (_os.path.dirname(_d), _d):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    __package__ = _os.path.relpath(
        _os.path.dirname(_os.path.abspath(__file__)), _d).replace(_os.sep, ".")

import math
import numpy as np

CAP = {}          # name -> fn(u, params) -> J {joint: (u,v,w)}
CAP_SRC = {}      # name -> 出处
CAP_GROUP = {}    # name -> 互斥组名

# ADAPT 原文：只有 sitting 与 navigating 互斥
EXCLUSIVE = [{"sit", "navigate"}]

MISSING_HINT = {
    "sit": "sit down animation IK contact constraint biped",
    "stand_up": "stand up animation center of mass transfer STS",
    "reach_grab": "reach grasp animation inverse kinematics CCD FABRIK",
    "carry_prop": "prop handoff ownership attachment animation",
    "prop_release": "prop release placement animation",
    "gaze_shift": "gaze shift head eye movement saccade formula",
    "expression": "facial expression animation blendshape smile",
    "finger_tap": "finger tap animation hand rig joint chain",
    "legs_cross": "crossed legs sitting pose rig IK",
    "page_flip": "page flip paper deformation animation curve",
    "idle": "idle standing breathing animation procedural",
}


class CapabilityError(Exception):
    pass


def capability(name, source, group="other"):
    def deco(fn):
        CAP[name] = fn
        CAP_SRC[name] = source
        CAP_GROUP[name] = group
        return fn
    return deco


def require(name):
    """缺能力就炸，并给出该去搜什么。绝不静默返回近似动作。"""
    if name not in CAP:
        raise CapabilityError(
            "缺能力 %r，请先搜：%s" % (name, MISSING_HINT.get(name, name + " animation formula")))
    return CAP[name]


def _sstep(x):
    x = 0.0 if x < 0 else (1.0 if x > 1 else x)
    return x * x * (3 - 2 * x)


class Beat:
    """一个动作段。

    t0/t1      秒。BML 的 start / end 时间戳
    phases     (prep, stroke, relax) 归一化比例，和为 1 —— Kallmann 三相位
               持续型动作填 (0,1,0)，全程强度恒为 1
    blend_in/out  秒。与相邻段交叠淡入淡出
    root       {X0, Z0, speed, yaw}，段内匀速推进（ADAPT 的 GoTo 语义）
    """
    def __init__(self, cap, t0, t1, params=None, phases=(0.0, 1.0, 0.0),
                 blend_in=0.35, blend_out=0.35, root=None, bid=""):
        require(cap)
        if t1 <= t0:
            raise ValueError("beat %s: t1 必须大于 t0" % bid)
        s = sum(phases)
        if abs(s - 1.0) > 1e-9:
            raise ValueError("beat %s: phases 之和必须为 1，实得 %g" % (bid, s))
        self.cap, self.t0, self.t1 = cap, float(t0), float(t1)
        self.params = dict(params or {})
        self.speed = float(self.params.get("speed", 0.0))
        self.phases = tuple(phases)
        self.blend_in, self.blend_out = float(blend_in), float(blend_out)
        self.root = dict(root or {})
        self.bid = bid or cap
        self.group = CAP_GROUP.get(cap, "other")
        self.dur = self.t1 - self.t0

    def envelope(self, u):
        p, s, _ = self.phases
        if p > 0 and u < p:
            return _sstep(u / p)
        if u < p + s:
            return 1.0
        r = self.phases[2]
        return _sstep(1.0 - (u - p - s) / r) if r > 0 else 1.0

    def fade(self, t):
        """相邻段各占半个淡变区：边界处两段各 0.5，和恒为 1。

        错法（会让边界两边同时淡到 0、出现空档）：
            A 在 [t1-d, t1] 降到 0，B 在 [t0, t0+d] 从 0 升起 —— t=t1 时两者皆 0。
        """
        w = 1.0
        if self.blend_in > 0 and not getattr(self, "_first", False):
            w *= _sstep((t - (self.t0 - self.blend_in * 0.5)) / self.blend_in)
        if self.blend_out > 0 and not getattr(self, "_last", False):
            w *= 1.0 - _sstep((t - (self.t1 - self.blend_out * 0.5)) / self.blend_out)
        return w

    def weight(self, t):
        lo = self.t0 - (0.0 if getattr(self, "_first", False) else self.blend_in * 0.5)
        hi = self.t1 + (0.0 if getattr(self, "_last", False) else self.blend_out * 0.5)
        if not (lo - 1e-9 <= t <= hi + 1e-9):
            return 0.0
        u = min(1.0, max(0.0, (t - self.t0) / self.dur))
        return self.envelope(u) * self.fade(t)

    def root_at(self, t):
        r = self.root
        if not r:
            return None
        d = self.speed * (t - self.t0)
        ya = math.radians(float(r.get("yaw", 90.0)))
        return (float(r.get("X0", 0.0)) + d * math.sin(ya),
                float(r.get("Z0", 6.0)) + d * math.cos(ya),
                float(r.get("yaw", 90.0)))


class Timeline:
    def __init__(self):
        self.beats = []

    def add(self, *args, **kw):
        b = args[0] if args and isinstance(args[0], Beat) else Beat(*args, **kw)
        self.beats.append(b)
        return b

    def speed_at(self, t):
        self._prep()
        """加权平均速度：crossfade 区两段各贡献一部分。"""
        act = [(b, b.weight(t)) for b in self.beats]
        act = [(b, w) for b, w in act if w > 1e-6]
        if not act:
            return 0.0
        return sum(b.speed * w for b, w in act) / sum(w for _, w in act)

    def build_mileage(self, dt=1.0 / 120.0):
        self._prep()
        """预积分里程碑。

        相位必须由 **全局累计里程** 决定，不能每段从 0 重来 —— 否则 A 段走到
        ph=0.7、B 段从 ph=0 起算，crossfade 区是"两个无关姿态的平均"，
        看起来就是一顿。ADAPT 里走路是持续型能力，转身只改参数不改相位。
        """
        if not self.beats:
            self._mil = None
            return
        tmax = max(b.t1 for b in self.beats)
        n = int(tmax / dt) + 2
        self._dt = dt
        m = np.zeros(n)
        for i in range(1, n):
            v0 = self.speed_at((i - 1) * dt)
            v1 = self.speed_at(i * dt)
            m[i] = m[i - 1] + 0.5 * (v0 + v1) * dt
        self._mil = m

    def mileage(self, t):
        if getattr(self, "_mil", None) is None:
            self.build_mileage()
        if self._mil is None:
            return 0.0
        x = t / self._dt
        i = int(x)
        if i >= len(self._mil) - 1:
            return float(self._mil[-1])
        f = x - i
        return float(self._mil[i] * (1 - f) + self._mil[i + 1] * f)

    def _prep(self):
        if not self.beats:
            return
        tmin = min(b.t0 for b in self.beats)
        tmax = max(b.t1 for b in self.beats)
        for b in self.beats:
            b._first = abs(b.t0 - tmin) < 1e-9
            b._last = abs(b.t1 - tmax) < 1e-9

    def _active(self, t):
        """当前时刻有贡献的动作段 [(beat, weight)]。空档直接炸，不降级。"""
        act = [(b, b.weight(t)) for b in self.beats]
        act = [(b, w) for b, w in act if w > 1e-6]
        if not act:
            raise CapabilityError("t=%.2f 时间线空档：没有任何动作覆盖，"
                                  "请补 idle 或让相邻段交叠" % t)
        return act

    def _check_exclusive(self, t, act):
        groups = {b.group for b, _ in act}
        for pair in EXCLUSIVE:
            # 只有"跨组"才算冲突：两个 navigate（走路转身交叠）是合法的
            hit = [g for g in groups if g in pair]
            if len(hit) > 1:
                raise CapabilityError(
                    "t=%.2f 互斥冲突：%s（ADAPT：只有 sitting 与 navigating 互斥）"
                    % (t, "+".join(sorted(hit))))

    def solve(self, t):
        """t → 混合后的姿态。返回 (J, Xc, Zc, yaw)。

        编排：取活跃段 → 互斥校验 → 位置/朝向混合 + 姿态混合。
        """
        self._prep()
        act = self._active(t)
        self._check_exclusive(t, act)
        tot = sum(w for _, w in act)
        Xc, Zc, yaw = _blend_root(act, tot, t)
        return _blend_pose(act, tot, t, self.mileage(t)), Xc, Zc, yaw


def _pad3(v):
    """关节值补齐三元 (u, v, w)：CAP 允许动作只给 (u, v)。"""
    return (v[0], v[1], v[2] if len(v) > 2 else 0.0)


def _blend_root(act, tot, t):
    """位置/朝向按权重加权 —— 走路类动作必须这样才不会在段边界跳。"""
    Xc = Zc = yaw = 0.0
    got = False
    for b, w in act:
        r = b.root_at(t)
        if r is None:
            continue
        Xc += r[0] * w; Zc += r[1] * w; yaw += r[2] * w
        got = True
    if got:
        Xc /= tot; Zc /= tot; yaw /= tot
    return Xc, Zc, yaw


def _blend_pose(act, tot, t, mil):
    """姿态：各能力各算一份，按权重混合（ADAPT 的 blend node）。"""
    J = None
    for b, w in act:
        p = dict(b.params)
        p["mileage"] = mil          # 持续型动作共用同一条相位链
        jj = CAP[b.cap]((t - b.t0) / b.dur, p)
        if J is None:
            J = {k: tuple(c * w for c in _pad3(v)) for k, v in jj.items()}
            continue
        for k, v in jj.items():
            if k in J:
                a, c = J[k], _pad3(v)
                J[k] = (a[0] + c[0] * w, a[1] + c[1] * w, a[2] + c[2] * w)
    for k in J:
        J[k] = (J[k][0] / tot, J[k][1] / tot, J[k][2] / tot)
    return J


# ---------------------------------------------------------------- 已注册能力
@capability("walk", "character.gait（四相位走路循环，Drillis&Contini 比例，已修）", group="navigate")
def _walk(u, params):
    from motion import character as C
    body_h = float(params.get("body_h", 1.70))
    speed = float(params.get("speed", 0.67))
    dur = float(params.get("dur", 1.0))
    preset = params.get("preset", "natural")
    phase0 = float(params.get("phase0", 0.0))
    stride = C.gait_params(preset)["stride"] * body_h
    d = params.get("mileage")               # 全局里程优先（跨段相位连续）
    if d is None:
        d = speed * u * dur                 # 退化：段内里程
    ph = (phase0 + (d / stride) / 2.0) % 1.0
    return C.gait(ph, preset)


# ---------------------------------------------------------------- 自检
if __name__ == "__main__":
    import numpy as np
    ok = True

    def chk(name, cond, detail=""):
        global ok
        ok = ok and bool(cond)
        print("  %-26s %s  %s" % (name, "PASS" if cond else "FAIL", detail))

    print("SELF_CHECK beat.py")
    chk("walk 已注册", "walk" in CAP, "group=%s" % CAP_GROUP["walk"])

    # 1 单段等效性：走时间线 == 直接调 gait
    tl = Timeline()
    tl.add("walk", 0.0, 6.0, params={"speed": 0.67, "dur": 6.0, "body_h": 1.70},
           bid="a", root={"X0": 0.0, "Z0": 6.0, "speed": 0.67, "yaw": 90.0},
           blend_in=0.0, blend_out=0.0)
    from motion import character as C
    worst = 0.0
    for i in range(60):
        t = i * 0.1
        J, Xc, Zc, yaw = tl.solve(t)
        d = 0.67 * t
        ph = ((d / (C.gait_params("natural")["stride"] * 1.70)) / 2.0) % 1.0
        Jd = C.gait(ph, "natural")
        for k in Jd:
            worst = max(worst, float(np.linalg.norm(np.array(J[k]) - np.array(Jd[k]))))
    chk("单段等效直接 gait", worst < 1e-9, "最大差 %.2e" % worst)

    # 2 三相位 envelope
    b = Beat("walk", 0, 3, phases=(0.2, 0.6, 0.2), blend_in=0.0, blend_out=0.0, bid="p")
    e0, e1, e2, e3 = (b.envelope(x) for x in (0.0, 0.1, 0.5, 1.0))
    chk("三相位 prep→stroke→relax", e0 < 1e-9 and 0.4 < e1 < 0.6 and e2 == 1.0 and e3 < 1e-9,
        "0/0.1/0.5/1 = %.2f/%.2f/%.2f/%.2f" % (e0, e1, e2, e3))

    # 3 跨段边界连续（关键：没有这条，12 秒会一顿一顿）
    tl2 = Timeline()
    tl2.add("walk", 0.0, 6.0, params={"speed": 0.67, "dur": 6.0}, bid="A",
            root={"X0": 0.0, "Z0": 6.0, "speed": 0.67, "yaw": 180.0})
    tl2.add("walk", 6.0, 12.0, params={"speed": 0.67, "dur": 6.0, "phase0": 0.0}, bid="B",
            root={"X0": 0.0, "Z0": 1.98, "speed": 0.67, "yaw": 90.0})
    # 判据：段边界处的帧间位移，不能显著大于段内正常走路的帧间位移。
    # （绝对阈值没意义 —— 走路本身就快，0.1s 关节走 0.06 身高单位是正常的）
    jumps = []
    for i in range(0, 118):
        t0, t1 = i * 0.1, i * 0.1 + 0.1
        J0, *_ = tl2.solve(t0)
        J1, *_ = tl2.solve(t1)
        jumps.append((t0, max(float(np.linalg.norm(np.array(J1[k]) - np.array(J0[k])))
                             for k in J0)))
    med = float(np.median([j for _, j in jumps]))
    edge = max(j for t, j in jumps if 5.4 <= t <= 6.6)
    chk("跨段无跳变", edge <= med * 2.0 + 0.01,
        "边界 %.4f vs 段内中位 %.4f（比值 %.2f）" % (edge, med, edge / med))

    # 4 缺能力必须报错
    try:
        Timeline().add("sit", 0, 1)
        chk("缺能力报错", False, "竟然没报错")
    except CapabilityError as ex:
        chk("缺能力报错", True, str(ex)[:46])

    # 5 互斥检查（ADAPT：sit 与 navigate 互斥）
    CAP["sit"] = lambda u, p: CAP["walk"](u, p)
    CAP_GROUP["sit"] = "sit"
    tl3 = Timeline()
    tl3.add("walk", 0, 4, params={"dur": 4.0}, bid="nav")
    try:
        b = Beat("sit", 1, 3, bid="s"); b.blend_in = b.blend_out = 0.0
        tl3.beats.append(b)
        tl3.solve(2.0)
        chk("互斥拦截", False, "sit+walk 竟然共存")
    except CapabilityError as ex:
        chk("互斥拦截", True, str(ex)[:46])
    del CAP["sit"]

    # 6 空档必须报错
    tl4 = Timeline(); tl4.add("walk", 0, 2, params={"dur": 2.0}, bid="x")
    try:
        tl4.solve(5.0); chk("空档报错", False)
    except CapabilityError:
        chk("空档报错", True, "t=5 无覆盖")

    print("\nSELF_CHECK:", "PASS" if ok else "FAIL")
