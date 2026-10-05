"""原地跳跃（A3）

契约: motion/character/jump
  输入: t∈[0,1] 全局进度 → 映射 T_TOTAL 秒
  输出: 同 gait 的关节字典 (u,v,w)，归一化身高单位
  依赖: numpy motion.character.leg
  被依赖: tests/run_all
  约束: 腾空相严格弹道 y=v_to·τ−gτ²/2，Δs=g·T_F²/8；
        落地缓冲后再无第二顶点(energy_gain≤0)；|髋踝|≤L1+L2
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

from .leg import two_bone_ik
from ..beat import capability

G = 9.80665
H_M = 1.70
FT = 0.40                       # 腾空时长
V_TO = G * FT / 2.0
RISE_M = V_TO ** 2 / (2.0 * G)  # = g·FT²/8 ≈ 0.196 m
RISE_N = RISE_M / H_M
CROUCH_M = 0.20
CROUCH_N = CROUCH_M / H_M
T_CROUCH, T_PUSH, T_LAND = 0.30, 0.15, 0.25
T_TOTAL = T_CROUCH + T_PUSH + FT + T_LAND

L1, L2 = 0.245, 0.246
ANK_N = 0.039
TOE_LEN, HEEL_LEN = 0.075, 0.038
HIP_STAND = 0.520
R_TRUNK = 0.298
DIP_LAND_N = 0.08 / H_M
_LEG_FLIGHT = 0.475            # 腾空期腿接近伸直（略留膝屈）
_AU, _AF = 0.186, 0.146


def _S(u, v, w=0.0):
    return np.array([float(u), float(v), float(w)])


def _ss(x):
    return x * x * (3.0 - 2.0 * x)


def hip_h_jump(t):
    s = float(t) * T_TOTAL
    if s < T_CROUCH:
        return HIP_STAND - CROUCH_N * _ss(s / T_CROUCH)
    if s < T_CROUCH + T_PUSH:
        return HIP_STAND - CROUCH_N + CROUCH_N * _ss((s - T_CROUCH) / T_PUSH)
    if s < T_CROUCH + T_PUSH + FT:
        tau = s - T_CROUCH - T_PUSH
        return HIP_STAND + (V_TO * tau - 0.5 * G * tau * tau) / H_M
    u = (s - T_CROUCH - T_PUSH - FT) / T_LAND
    return HIP_STAND - DIP_LAND_N * math.sin(math.pi * min(1.0, max(0.0, u)))


def _phase(t):
    s = float(t) * T_TOTAL
    if s < T_CROUCH:
        return "crouch"
    if s < T_CROUCH + T_PUSH:
        return "push"
    if s < T_CROUCH + T_PUSH + FT:
        return "flight"
    return "land"


def _arm(su, sv, th_sh, th_el):
    ex = su + _AU * math.sin(th_sh)
    ey = sv - _AU * math.cos(th_sh)
    t2 = th_sh + th_el
    return (ex, ey), (ex + _AF * math.sin(t2), ey - _AF * math.cos(t2))


def jump(t, scale_h=1.0):
    t = min(1.0, max(0.0, float(t)))
    y = hip_h_jump(t)
    ph = _phase(t)
    if ph == "flight":
        ank_v = ANK_N + (y - HIP_STAND) * 0.93
        pit = math.radians(-20.0)
    else:
        ank_v = ANK_N
        pit = 0.0
    out = {"pelvis": _S(0.0, y), "waist": _S(0.0, y + R_TRUNK * 0.35),
           "chest": _S(0.0, y + R_TRUNK), "neck": _S(0.0, y + R_TRUNK + 0.052),
           "head": _S(0.0, y + R_TRUNK + 0.130)}
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        hip = np.array([0.0, y])
        ank = np.array([0.0, ank_v])
        kn = two_bone_ik(hip, ank, L1, L2, bend=(1.0, 0.0))
        w = 0.055 * sgn
        out["hip_" + side] = _S(0.0, y, w)
        out["knee_" + side] = _S(kn[0], kn[1], w)
        out["ank_" + side] = _S(0.0, ank_v, w)
        out["toe_" + side] = _S(TOE_LEN * math.cos(pit),
                                ank_v + TOE_LEN * math.sin(pit), w)
        out["heel_" + side] = _S(-HEEL_LEN * math.cos(pit),
                                 ank_v - HEEL_LEN * math.sin(pit), w)
        # 摆臂：下蹲后摆 → 起跳上摆 → 腾空回落 → 落地回摆
        if ph == "crouch":
            th = 1.0 * sgn
        elif ph == "push":
            th = -1.6 * sgn
        elif ph == "flight":
            th = -1.1 * sgn
        else:
            th = 0.15 * sgn
        el = -1.0 * sgn
        sh = (0.0, y + R_TRUNK - 0.02)
        (ex, ey), (wx, wy) = _arm(sh[0], sh[1], th, el)
        out["sh_" + side] = _S(sh[0], sh[1], 0.08 * sgn)
        out["elb_" + side] = _S(ex, ey, 0.08 * sgn)
        out["wri_" + side] = _S(wx, wy, 0.08 * sgn)
    return out


def self_check():
    r = []
    N = 1200
    Y = [hip_h_jump(i / N) for i in range(N + 1)]
    r.append(("起跳前下蹲", abs(min(Y) - (HIP_STAND - CROUCH_N)) < 1e-3,
              "最低=%.4f m" % (min(Y) * H_M)))
    r.append(("腾空顶点=gT²/8", abs((max(Y) - HIP_STAND) * H_M - RISE_M) < 2e-3,
              "%.4f m vs %.4f" % ((max(Y) - HIP_STAND) * H_M, RISE_M)))
    r.append(("落地回到站立", abs(Y[-1] - HIP_STAND) < 1e-6, "%.6f" % Y[-1]))
    ap = [Y[i] for i in range(1, N) if Y[i] > Y[i - 1] and Y[i] >= Y[i + 1]]
    r.append(("无二次弹跳增能", len(ap) <= 1, "顶点数=%d" % len(ap)))
    mx = 0.0
    worst = 0.0
    for i in range(N + 1):
        J = jump(i / N)
        for side in ("l", "r"):
            h, k, a = J["hip_" + side][:2], J["knee_" + side][:2], J["ank_" + side][:2]
            mx = max(mx, abs(np.linalg.norm(k - h) - L1),
                     abs(np.linalg.norm(a - k) - L2))
            worst = max(worst, float(np.linalg.norm(h - a)))
    r.append(("骨长守恒", mx < 1e-6, "max=%.2e" % mx))
    r.append(("髋踝距≤腿长", worst <= L1 + L2, "max=%.4f/%.3f" % (worst, L1 + L2)))
    d = max(abs(Y[i + 1] - Y[i]) for i in range(N))
    r.append(("无跳变", d < 0.01, "max=%.5f" % d))
    ok = True
    for n, ok_, s in r:
        print(("PASS " if ok_ else "FAIL ") + n + "  " + s)
        ok = ok and ok_
    return ok


@capability("jump", source="弹道 Δs=g·T_F²/8（UA PH125 抛体运动）", group="locomotion")
def _cap_jump(u, p):
    return jump(u)


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
