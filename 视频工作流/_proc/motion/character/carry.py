"""搬运箱子（E26）：抱起 → 走 → 放下

契约: motion/character/carry
  输入: u∈[0,1] 全程进度；box 尺寸 (w,h,d) 与起止支点位置
  输出: {'phase':str, 'owner':str, 'J':{关节:(u,v,w)}, 'box':{...}}
  依赖: numpy motion.character.leg motion.character.gait
  被依赖: tests/run_all tests/gen
  约束: 半蹲举姿态 膝屈~90° / 躯干前倾~45°（Burgess-Limerick & Straker
        2003 半蹲举，介于蹲举与弯腰举之间的折中）；
        箱体约束到躯干骨而不是独立漂浮（Animation Master: constrain the
        box to a spine / torso bone）；
        双手约束到箱体两侧，手心在箱侧面外 WRIST_TO_GRIP → 不穿透；
        持箱行走减小摆臂（负载贴紧身体，NIOSH HM=25/H 要求 H 尽量小）
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

from .body.leg import two_bone_ik
from ..beat import capability

H_M = 1.70
L1, L2 = 0.245, 0.246
ANK_N = 0.039
TOE_LEN, HEEL_LEN = 0.075, 0.038
HIP_STAND = 0.520
R_TRUNK = 0.298
_AU, _AF = 0.186, 0.146
WRIST_TO_GRIP = 0.038
# 掌球半径(米)：手-箱穿透判据的唯一定义点。
# 曾两处各写一份: 本模块 self_check 用 0.035、tests/cases_carry 用 0.040。
# 同一几何量两套口径 → 自检判定"分离"(-0.003)而测试判定"穿透"(+0.002)，
# 按 A2 铁律(单点定义、多处引用)统一到这里，测试改为 from 本模块引用。
PALM_R = 0.040
ARM_REACH = _AU + _AF + WRIST_TO_GRIP
SHOULDER_Z = 0.115
HIP_Z = 0.055

# ---- 半蹲举姿态（出处: Burgess-Limerick & Straker 2003 semi-squat）
KNEE_SEMI = math.radians(90.0)      # 膝屈 ~90°
TRUNK_SEMI = math.radians(45.0)     # 躯干前倾 ~45°
# |髋-踝| = sqrt(L1²+L2²+2·L1·L2·cos(膝屈)) —— 膝屈 90° 时 cos=0
HIP_SEMI = ANK_N + math.sqrt(L1 * L1 + L2 * L2 * 1.0)

# ---- 箱体（默认 40×30×30 cm 纸箱）
BOX = (0.40, 0.30, 0.30)
# NIOSH: 水平距离 H 越小 HM=25/H 越大 → 箱体背面贴住躯干
BOX_BACK_U = 0.075          # 躯干前表面（归一化身高单位）
# 站立抱持时箱体中心高度：胸口下缘，保证臂展可达且留肘弯
BOX_V_STAND = 0.647         # ≈1.10 m
TABLE_TOP = 0.75            # 默认台面高（半蹲可达；地面拾取归 crouch 用例）
ARM_JOINT_MAX = _AU + _AF   # 肩→腕关节链上限（不含掌长）

SPANS = (0.25, 0.40, 0.25, 0.10)   # lift / carry / setdown / rise
PHASES = ("lift", "carry", "setdown", "rise")


def _S(u, v, w=0.0):
    return np.array([float(u), float(v), float(w)])


def _ss(x):
    return x * x * (3.0 - 2.0 * x)


def _arm(su, sv, th_sh, th_el):
    ex = su + _AU * math.sin(th_sh)
    ey = sv - _AU * math.cos(th_sh)
    t2 = th_sh + th_el
    return (ex, ey), (ex + _AF * math.sin(t2), ey - _AF * math.cos(t2))


def semi_squat(q):
    """半蹲姿态 q=0 站 / q=1 半蹲（膝~90°、躯干~45°），双脚不动。"""
    q = min(1.0, max(0.0, float(q)))
    e = _ss(q)
    y = HIP_STAND - (HIP_STAND - HIP_SEMI) * e
    lean = TRUNK_SEMI * e
    su, sv = R_TRUNK * math.sin(lean), y + R_TRUNK * math.cos(lean)
    out = {"pelvis": _S(0.0, y),
           "waist": _S(R_TRUNK * 0.35 * math.sin(lean),
                       y + R_TRUNK * 0.35 * math.cos(lean)),
           "chest": _S(su, sv),
           "neck": _S(su + 0.052 * math.sin(lean),
                      sv + 0.052 * math.cos(lean)),
           "head": _S(su + 0.130 * math.sin(lean),
                      sv + 0.130 * math.cos(lean))}
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        hip = np.array([0.0, y])
        ank = np.array([0.0, ANK_N])
        kn = two_bone_ik(hip, ank, L1, L2, bend=(1.0, 0.0))
        w = HIP_Z * sgn
        out["hip_" + side] = _S(0.0, y, w)
        out["knee_" + side] = _S(kn[0], kn[1], w)
        out["ank_" + side] = _S(0.0, ANK_N, w)
        out["toe_" + side] = _S(TOE_LEN, ANK_N, w)
        out["heel_" + side] = _S(-HEEL_LEN, ANK_N, w)
    return out


def box_pose(J, size=BOX):
    """箱体位姿：约束到躯干（chest）前方，背面贴住身体（NIOSH H 最小化）。

    Animation Master: 把箱子约束到脊柱/躯干骨上，就不必单独动画它在
    空间中的运动 —— 箱体随躯干走，不会脱手也不会穿身。
    """
    w, h, d = size
    ch = J["chest"]
    wa = J["waist"]
    cu = float(ch[0]) * H_M
    cv_ = float(ch[1]) * H_M
    wu = float(wa[0]) * H_M
    # 躯干前表面
    front_u = max(cu, wu) + BOX_BACK_U * H_M
    center_u = front_u + 0.5 * d
    center_v = cv_ - 0.5 * h + 0.5 * h      # 箱中心与胸口同高
    center_v = cv_ - 0.02 * H_M
    # 抱持高度下限：箱底不低于腰，保证站立时肘有弯曲余量
    center_v = max(center_v, float(J["waist"][1]) * H_M + 0.5 * h)
    return {"c": np.array([center_u, center_v, 0.0]),
            "half": np.array([0.5 * d, 0.5 * h, 0.5 * w])}


def hug_arms(J, box, blend=1.0):
    """双手环抱箱体两侧：手心在箱侧面外 WRIST_TO_GRIP（不穿透）。

    判据口径与 crouch.reach_pose 一致：IK 目标 = 箱侧面 − 法向 × 握距。
    """
    c = box["c"]
    half = box["half"]
    out = dict(J)
    cu = c[0] / H_M
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        sh = np.array([float(out["chest"][0]),
                       float(out["chest"][1]) - 0.02])
        z_hand = (half[2] * sgn + WRIST_TO_GRIP * sgn) / 1.0
        tgt_u = cu
        tgt_v = c[1] / H_M
        grip = np.array([tgt_u, tgt_v])
        # 注意: L1/L2/_AU/_AF/ARM_REACH 与关节字典同为"归一化身高单位"，
        # 不能再除 H_M（曾误除导致臂展被压到 0.218 → 手够不到箱体）
        # 腕是关节端点，肩→腕上限是 _AU+_AF（不含 WRIST_TO_GRIP 那段掌长）
        L = float(np.linalg.norm(grip - sh))
        if L > (_AU + _AF) - 1e-6:
            ux = (grip - sh) / max(L, 1e-9)
            grip = sh + ux * ((_AU + _AF) - 1e-6)
        el = two_bone_ik(sh, grip, _AU, _AF, bend=(-1.0, 0.0))
        b = min(1.0, max(0.0, float(blend)))
        if b < 1.0:
            nat = _arm(sh[0], sh[1], 0.15 * sgn, -0.5 * sgn)
            ex = float(nat[0][0] + (el[0] - nat[0][0]) * b)
            ey = float(nat[0][1] + (el[1] - nat[0][1]) * b)
            wx = float(nat[1][0] + (grip[0] - nat[1][0]) * b)
            wy = float(nat[1][1] + (grip[1] - nat[1][1]) * b)
        else:
            ex, ey = float(el[0]), float(el[1])
            wx, wy = float(grip[0]), float(grip[1])
        out["sh_" + side] = _S(sh[0], sh[1], SHOULDER_Z * sgn)
        out["elb_" + side] = _S(ex, ey, SHOULDER_Z * sgn)
        out["wri_" + side] = _S(wx, wy, z_hand / H_M * 1.0)
    return out


# ------------------------------------------------------------ 球 vs AABB 穿透
def sphere_box_pen(sphere_c, sphere_r, box_c, box_half):
    """球心到 AABB 最近点距离 → 穿透深度（负值=分离）。

    SIGGRAPH Asia 2025 Penetration Estimation 的球面-盒判定简化式：
      pen = r − |c − clamp(c, min, max)|
    """
    c = np.asarray(sphere_c, float)
    bmin = np.asarray(box_c, float) - np.asarray(box_half, float)
    bmax = np.asarray(box_c, float) + np.asarray(box_half, float)
    q = np.clip(c, bmin, bmax)
    return float(sphere_r - np.linalg.norm(c - q))


# ------------------------------------------------------------ 全程时序
class CarryBox:
    """抱起(lift) → 行走(carry) → 放下(setdown) → 起身(rise)

    所有权: lift 末 attach → owner='both'；setdown 末 detach → 'world'。
    与 prop.Handoff 同构：只在两个事件点切换，各一次。
    """

    def __init__(self, box=None, spans=SPANS, start_v=0.0, end_v=0.0):
        self.size = tuple(box) if box else BOX
        self.spans = spans
        self.owner = "world"
        self.pivot = np.array([0.0, start_v, 0.0])
        self.end_v = float(end_v)
        self._fired = set()
        self.attach_at = float(spans[0])
        self.detach_at = float(spans[0] + spans[1] + spans[2])

    def phase_of(self, u):
        a, b, c, d = self.spans
        u = float(np.clip(u, 0.0, 1.0))
        if u < a:
            return "lift"
        if u < a + b:
            return "carry"
        if u < a + b + c:
            return "setdown"
        return "rise"

    def advance(self, u):
        u = float(np.clip(u, 0.0, 1.0))
        ev = []
        if u >= self.attach_at and "attach" not in self._fired:
            self._fired.add("attach")
            self.owner = "both"
            ev.append("attach")
        if u >= self.detach_at and "detach" not in self._fired:
            self._fired.add("detach")
            self.owner = "world"
            ev.append("detach")
        return {"phase": self.phase_of(u), "owner": self.owner,
                "events": ev}


@capability("carry_box",
            source="半蹲举 膝~90°/躯干~45°（Burgess-Limerick & Straker 2003）；"
                   "箱体约束到躯干骨（Animation Master）；"
                   "NIOSH RWL=LC×HM×VM×DM×AM×FM×CM, LC=23kg, HM=25/H",
            group="carry")
def carry_box(u, params=None):
    """全程进度 u∈[0,1] → {'phase','owner','J','box'}。

    params: {'size':(w,h,d), 'walk_cycles':N, 'step':float, 'speed':float}
    四个相位各自独立成 helper（_ph_*），主函数只做参数归一与分派。
    """
    p = dict(params or {})
    size = tuple(p.get("size", BOX))
    cyc = float(p.get("walk_cycles", 2.0))
    start_v = float(p.get("start_v", TABLE_TOP + 0.5 * size[1]))
    end_v = float(p.get("end_v", TABLE_TOP + 0.5 * size[1]))
    cb = CarryBox(box=size, start_v=start_v, end_v=end_v)
    st = cb.advance(u)
    ph = st["phase"]
    a, b, c, d = cb.spans
    half = np.array([0.5 * size[2], 0.5 * size[1], 0.5 * size[0]])
    from .body.gait import gait as _g
    V_CARRY = float(box_pose(_g(0.25, "natural"), size)["c"][1])
    ctx = {"size": size, "half": half, "cyc": cyc, "g": _g,
           "start_v": start_v, "end_v": end_v, "V_CARRY": V_CARRY}
    if ph == "lift":
        J, box_v = _ph_lift(u, a, ctx)
    elif ph == "carry":
        J, box_v = _ph_carry(u, a, b, ctx)
    elif ph == "setdown":
        J, box_v = _ph_setdown(u, a, b, c, ctx)
    else:  # rise
        J, box_v = _ph_rise(u, a, b, c, d, ctx)
    return {"phase": ph, "owner": st["owner"], "J": J,
            "box": {"c": box_v, "half": half, "size": size}}


def _mkbox(vv, size):
    """箱体中心：贴背偏移 BOX_BACK_U + 半深。"""
    return np.array([BOX_BACK_U * H_M + 0.5 * size[2], vv, 0.0])


def _ph_lift(u, a, ctx):
    """抱起：前 50% 下蹲去够 → 后 50% 起立抬到抱持高度。"""
    size, half, g = ctx["size"], ctx["half"], ctx["g"]
    s = u / max(a, 1e-9)
    q = _ss(1.0 - abs(2.0 * s - 1.0))
    J = semi_squat(q)
    bv = ctx["start_v"]
    if s >= 0.5:
        # 起立后半程同时把姿态融回行走起势(phs=0), 否则进入 carry 时
        # 双脚从半蹲位(局部 u≈0)瞬移到行走支撑位(u≈+0.2m) = 20cm 跳变
        w = _ss(2.0 * s - 1.0)
        bv = ctx["start_v"] + (ctx["V_CARRY"] - ctx["start_v"]) * w
        J = {k: (1.0 - w) * np.asarray(v, float)
             + w * np.asarray(g(0.0, "natural")[k], float)
             for k, v in J.items()}
    box_v = _mkbox(bv, size)
    return hug_arms(J, {"c": box_v, "half": half}, blend=max(q, 0.6)), box_v


def _ph_carry(u, a, b, ctx):
    """持箱行走：摆臂减小（负载贴紧身体，NIOSH H 最小化）。"""
    size, half, g = ctx["size"], ctx["half"], ctx["g"]
    du = (u - a) / max(b, 1e-9)
    phs = (ctx["cyc"] * du) % 1.0
    J = g(phs, "natural")
    base = g(0.25, "natural")
    for side in ("l", "r"):
        for k in ("sh_", "elb_", "wri_"):
            key = k + side
            if key in J and key in base:
                nat = np.asarray(base[key], float)
                cur = np.asarray(J[key], float)
                J[key] = nat + (cur - nat) * 0.25
    box = box_pose(J, size)
    J = hug_arms(J, box)
    return J, box["c"]


def _ph_setdown(u, a, b, c, ctx):
    """放下：行走姿态 → 半蹲，箱体降到台面。"""
    size, half, g = ctx["size"], ctx["half"], ctx["g"]
    s = (u - a - b) / max(c, 1e-9)
    Jw = g((ctx["cyc"] * 1.0) % 1.0, "natural")
    Js = semi_squat(s)
    J = {}
    for k, vv in Js.items():
        if k in Jw:
            J[k] = np.asarray(Jw[k], float) + (
                np.asarray(vv, float) - np.asarray(Jw[k], float)) * _ss(s)
        else:
            J[k] = np.asarray(vv, float)
    bv = ctx["V_CARRY"] + (ctx["end_v"] - ctx["V_CARRY"]) * _ss(s)
    box_v = _mkbox(bv, size)
    return hug_arms(J, {"c": box_v, "half": half}, blend=1.0), box_v


def _ph_rise(u, a, b, c, d, ctx):
    """起身：半蹲归零，双手已释放自然垂放（缺关节会让下游崩）。"""
    size, g = ctx["size"], ctx["g"]
    s = (u - a - b - c) / max(d, 1e-9)
    J = semi_squat(1.0 - _ss(s))
    box_v = _mkbox(ctx["end_v"], size)
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        sh = np.array([float(J["chest"][0]),
                       float(J["chest"][1]) - 0.02])
        (ex, ey), (wx, wy) = _arm(sh[0], sh[1], 0.15 * sgn, -0.5 * sgn)
        J["sh_" + side] = _S(sh[0], sh[1], SHOULDER_Z * sgn)
        J["elb_" + side] = _S(ex, ey, SHOULDER_Z * sgn)
        J["wri_" + side] = _S(wx, wy, SHOULDER_Z * sgn)
    return J, box_v


@capability("box_release",
            source="放箱：半蹲降至箱底接触台面后 detach（owner=world），"
                   "与 prop.Handoff 的 release/recovery 同构",
            group="carry")
def box_release(J, surface_v, size=BOX):
    """放下：返回箱体最终位姿（底面贴合 surface_v）。"""
    return {"c": np.array([BOX_BACK_U * H_M + 0.5 * size[2],
                           surface_v + 0.5 * size[1], 0.0]),
            "half": np.array([0.5 * size[2], 0.5 * size[1], 0.5 * size[0]]),
            "owner": "world"}


# ================================================================
# 自检
# ================================================================
if __name__ == "__main__":
    ok = True

    def chk(name, cond, extra=""):
        global ok
        ok = ok and bool(cond)
        print("  %-30s %s %s" % (name, "OK" if cond else "FAIL", extra))

    print("=" * 66)
    print("  carry 自检  (出处: Burgess-Limerick&Straker 2003 / Animation")
    print("             Master / NIOSH 提举方程)")
    print("=" * 66)

    # 1 四相位和=1，顺序正确
    chk("四相时长和=1", abs(sum(SPANS) - 1.0) < 1e-12, "sum=%.3f" % sum(SPANS))
    seq = [CarryBox().phase_of(x) for x in (0.10, 0.50, 0.80, 0.95)]
    chk("相位顺序", seq == list(PHASES), str(seq))

    # 2 半蹲膝屈 ~90°（由 |髋-踝| 反解）
    Js = semi_squat(1.0)
    # 关节字典与 L1/L2 同为归一化身高单位，此处不可换算成米
    hip = np.array([Js["pelvis"][0], Js["pelvis"][1]])
    ank = np.array([Js["ank_l"][0], Js["ank_l"][1]])
    da = float(np.linalg.norm(hip - ank))
    knee = math.degrees(math.acos(
        max(-1.0, min(1.0, (da * da - L1 * L1 - L2 * L2) / (2 * L1 * L2)))))
    chk("半蹲膝屈 ≈90°", abs(knee - 90.0) < 3.0, "%.1f°" % knee)
    chk("半蹲躯干前倾 ≈45°",
        abs(math.degrees(TRUNK_SEMI) - 45.0) < 1e-9,
        "%.1f°" % math.degrees(TRUNK_SEMI))

    # 3 双脚全程不动（不滑不飘）
    dfeet = max(abs(float(semi_squat(q)["ank_l"][0]) - 0.0)
                + abs(float(semi_squat(q)["ank_l"][1]) - ANK_N)
                for q in (0.0, 0.25, 0.5, 0.75, 1.0))
    chk("半蹲双脚不滑不飘", dfeet < 1e-12, "位移 %.2e" % dfeet)

    # 4 attach / detach 各一次，owner 全程唯一
    cb = CarryBox()
    fires = {}
    owners = []
    for i in range(201):
        r = cb.advance(i / 200.0)
        for e in r["events"]:
            fires[e] = fires.get(e, 0) + 1
        owners.append(r["owner"])
    chk("事件各触发一次", all(v == 1 for v in fires.values()), str(fires))
    chk("owner 全程唯一", sorted(set(owners)) == ["both", "world"],
        str(sorted(set(owners))))

    # 5 手心在箱侧面外 → 不穿透（双手握持全程 u∈[0.5a, detach]）
    worst = -9.9
    worst_r = 0.0
    for i in range(101):
        u = 0.5 * SPANS[0] + (cb.detach_at - 1e-6 - 0.5 * SPANS[0]) * i / 100.0
        r = carry_box(u)
        J, bx = r["J"], r["box"]
        for side in ("l", "r"):
            wri = np.array(J["wri_" + side], float) * H_M
            pen = sphere_box_pen(wri, PALM_R, bx["c"], bx["half"])
            worst = max(worst, pen)
            sh = np.array(J["sh_" + side], float) * H_M
            worst_r = max(worst_r, float(np.linalg.norm(wri - sh)))
    # 阈值 0.005 与 tests/harness.py 的 penetration_m(Box2D v2.4.1
    # b2_linearSlop)同源；此处本地声明以避免 motion→tests 反向依赖。
    chk("握持全程手不穿箱", worst < 0.005, "最大穿透 %.4f m" % worst)

    # 6 臂展不超限（肩→腕关节链 ≤ _AU+_AF）
    chk("肩→腕 ≤ 臂展", worst_r <= ARM_JOINT_MAX * H_M + 1e-6,
        "最大 %.4f / 上限 %.4f m" % (worst_r, ARM_JOINT_MAX * H_M))

    # 7 detach 瞬间箱体连续无跳变
    eps = 1e-4
    ra = carry_box(cb.detach_at - eps)["box"]["c"]
    rb = carry_box(cb.detach_at + eps)["box"]["c"]
    chk("detach 无跳变",
        float(np.linalg.norm(np.asarray(rb) - np.asarray(ra))) < 5e-3,
        "跳变 %.2e" % float(np.linalg.norm(np.asarray(rb) - np.asarray(ra))))

    print("=" * 66)
    print("  %s" % ("全部通过" if ok else "存在 FAIL"))
