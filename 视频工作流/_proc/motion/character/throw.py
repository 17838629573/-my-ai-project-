"""投掷（B10 / D22 / E27 通用）

契约: motion/character/throw
  输入: t∈[0,1] 全局进度
  输出: 关节字典(u,v,w 归一化身高); 球心(米); 出手速度(米每秒)
  依赖: numpy motion.character.leg motion.character.ball ..beat
  被依赖: tests/run_all  motion/character/catch
  约束: 加速段末端速度最大(动力链鞭打), 释放取前一瞬手速(后向差分);
        球释放后走解析抛物线, 不做数值积分; 臂展不超 0.377H
公式出处:
  · 动力链顺序 stride→pelvis rotation→upper torso rotation→elbow extension
    →shoulder internal rotation→wrist flexion; 肩外旋最大 ≈180°;
    出手后用全身减速 (Fleisig et al. Sports Medicine 1996,
    DOI 10.2165/00007256-199621060-00004)
  · 抛体 R = u²sin2θ/g, 同高度时 45° 射程最大
  · 臂展 ARM17.3+FOREARM15.5+WRIST-TO-GRIP3.8 = 36.6%H (Dempster 0.3767H)
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
from . import ball
from ..beat import capability

H_M = 1.70
G = ball.G
_AU, _AF = 0.186, 0.146
_GRIP = 0.038
HIP_STAND = 0.520
R_TRUNK = 0.298
L1, L2 = 0.245, 0.246
ANK_N = 0.039
TOE_LEN, HEEL_LEN = 0.075, 0.038

T_WIND, T_COCK, T_ACC, T_FOL = 0.28, 0.12, 0.10, 0.50
T_TOTAL = 1.60
F_REL = T_WIND + T_COCK + T_ACC
T_FLIGHT = 2.60

_SH = np.array([0.0, HIP_STAND + R_TRUNK - 0.02])
_A0 = np.array([-0.02, -0.12])     # 持球于胸前
_A1 = np.array([-0.22, 0.02])      # 后摆(肩外旋最大)
_A2 = np.array([0.12, 0.14])       # 出手(前上方)
_A3 = np.array([0.10, -0.24])      # 随挥(全身减速)
_TRAJ = None


def _S(u, v, w=0.0):
    return np.array([float(u), float(v), float(w)])


def _ss(x):
    x = min(1.0, max(0.0, float(x)))
    return x * x * (3.0 - 2.0 * x)


def _wrist_path(t):
    """腕相对肩(归一化身高): 后摆→最大外旋保持→加速鞭打(ease-in)→随挥"""
    if t < T_WIND:
        return _A0 + (_A1 - _A0) * _ss(t / T_WIND)
    if t < T_WIND + T_COCK:
        u = (t - T_WIND) / T_COCK
        return _A1 + np.array([0.012 * math.sin(math.pi * u), -0.006 * _ss(u)])
    if t < F_REL:
        u = (t - T_WIND - T_COCK) / T_ACC
        return _A1 + (_A2 - _A1) * (u * u)
    u = _ss((t - F_REL) / T_FOL)
    return _A2 + (_A3 - _A2) * u


def _shoulder(t):
    """肩位(归一化): 躯干旋转令投掷侧肩先后撤再前送

    两分支在 t=F_REL 处必须取同一值 P_REL, 否则后向差分出手速度会被
    肩位跳变放大成数百 m/s(Fleisig 动力链的肩位是连续量)
    """
    if t < F_REL:
        u = _ss(t / F_REL)
        return _SH + np.array([-0.045 * math.sin(math.pi * u), 0.004 * u])
    u = _ss((t - F_REL) / T_FOL)
    return _SH + np.array([0.030 * u, 0.004 - 0.014 * u])


def hand_center(t):
    """手心(米): 腕 + 抓握偏移(沿前臂方向)"""
    t = min(1.0, max(0.0, float(t)))
    sh = _shoulder(t)
    wr = sh + _wrist_path(t)
    el = two_bone_ik(sh, wr, _AU, _AF, bend=(1.0, 0.0))
    d = wr - el
    n = max(np.linalg.norm(d), 1e-12)
    return (wr + (_GRIP / n) * d) * H_M


def release_vel(dt=1e-5):
    """出手速度(米每秒): 释放前一瞬手速, 后向差分(与 kick.foot_vel 同口径)"""
    lo = max(0.0, F_REL - dt)
    return (hand_center(F_REL) - hand_center(lo)) / ((F_REL - lo) * T_TOTAL)


def _traj():
    global _TRAJ
    if _TRAJ is None:
        T, P = ball.trajectory(hand_center(F_REL), release_vel(),
                               T_FLIGHT, 1.0 / 240.0)
        _TRAJ = (T, P)
    return _TRAJ


def ball_center(t):
    """球心(米): 释放前被握住(随手), 释放后解析抛物线"""
    t = min(1.0, max(0.0, float(t)))
    if t <= F_REL:
        return hand_center(t)
    T, P = _traj()
    tt = (t - F_REL) / (1.0 - F_REL) * T[-1]
    i = min(len(T) - 1, max(0, int(round(tt * 240.0))))
    return P[i]


def _stance(t):
    """躯干/双腿(站立): 投掷时重心随躯干旋转微前送"""
    y = HIP_STAND
    u = _ss(min(1.0, t / max(F_REL, 1e-6)))
    lean = 0.06 * math.sin(math.pi * u)
    out = {"pelvis": _S(0.0, y),
           "waist": _S(-R_TRUNK * 0.35 * lean, y + R_TRUNK * 0.35),
           "chest": _S(-R_TRUNK * lean, y + R_TRUNK),
           "neck": _S(-(R_TRUNK + 0.052) * lean, y + R_TRUNK + 0.052),
           "head": _S(-(R_TRUNK + 0.130) * lean, y + R_TRUNK + 0.130)}
    for side, ax, sgn in (("l", -0.03, 0.055), ("r", 0.05, -0.055)):
        a = np.array([ax, ANK_N])
        kn = two_bone_ik(np.array([0.0, y]), a, L1, L2, bend=(1.0, 0.0))
        out["hip_" + side] = _S(0.0, y, sgn)
        out["knee_" + side] = _S(kn[0], kn[1], sgn)
        out["ank_" + side] = _S(a[0], a[1], sgn)
        out["toe_" + side] = _S(a[0] + TOE_LEN, 0.0, sgn)
        out["heel_" + side] = _S(a[0] - HEEL_LEN, 0.0, sgn)
    return out


def _arm_left(t):
    """左臂: 与投掷反向的平衡摆"""
    y = HIP_STAND
    u = _ss(min(1.0, t / F_REL))
    sx = -(R_TRUNK - 0.02) * (0.06 * math.sin(math.pi * u))
    sh = np.array([sx, y + R_TRUNK - 0.02])
    th = -0.55 - 0.25 * u
    el = -0.70
    ex, ey = sh[0] + _AU * math.sin(th), sh[1] - _AU * math.cos(th)
    t2 = th + el
    return sh, np.array([ex, ey]), np.array([ex + _AF * math.sin(t2),
                                             ey - _AF * math.cos(t2)])


def throw(t):
    """投掷: 返回关节字典(归一化身高)"""
    t = min(1.0, max(0.0, float(t)))
    out = _stance(t)
    sh, el, wr = _arm_left(t)
    out["sh_l"] = _S(sh[0], sh[1], 0.08)
    out["elb_l"] = _S(el[0], el[1], 0.08)
    out["wri_l"] = _S(wr[0], wr[1], 0.08)
    sr = _shoulder(t)
    wr_r = sr + _wrist_path(t)
    el_r = two_bone_ik(sr, wr_r, _AU, _AF, bend=(1.0, 0.0))
    out["sh_r"] = _S(sr[0], sr[1], -0.08)
    out["elb_r"] = _S(el_r[0], el_r[1], -0.08)
    out["wri_r"] = _S(wr_r[0], wr_r[1], -0.08)
    return out


def self_check():
    r = []
    N = 400
    mx = 0.0
    for i in range(N + 1):
        J = throw(i / N)
        sh, el, w = J["sh_r"][:2], J["elb_r"][:2], J["wri_r"][:2]
        mx = max(mx, abs(np.linalg.norm(el - sh) - _AU),
                 abs(np.linalg.norm(w - el) - _AF))
    r.append(("骨长守恒", mx < 1e-9, "max=%.2e" % mx))
    sp = [np.linalg.norm(hand_center(F_REL - T_ACC + T_ACC * k / 20.0)
                         - hand_center(F_REL - T_ACC + T_ACC * (k - 1) / 20.0))
          for k in range(1, 21)]
    mono = all(sp[i + 1] >= sp[i] - 1e-12 for i in range(len(sp) - 1))
    r.append(("加速段末端最快", mono and sp[-1] > 1.5 * sp[0],
              "首%.4f 末%.4f" % (sp[0], sp[-1])))
    v = release_vel()
    r.append(("出手速度合理", 3.0 < np.linalg.norm(v) < 30.0,
              "%.2f m/s %.1f°" % (np.linalg.norm(v),
                                  math.degrees(math.atan2(v[1], v[0])))))
    d = np.linalg.norm(hand_center(F_REL) - ball_center(F_REL))
    r.append(("出手瞬间球在手", d < 1e-6, "dist=%.2e" % d))
    T, P = _traj()
    r.append(("不穿地", P[:, 1].min() >= ball.R_BALL - 1e-6,
              "min y=%.4f" % P[:, 1].min()))
    i0, i1 = int(round(0.05 * 240)), min(len(T), int(round(0.60 * 240)))
    c = np.polyfit(T[i0:i1] - T[i0], P[i0:i1, 1] - ball.R_BALL, 2)
    err = abs(-2.0 * c[0] - G) / G
    r.append(("弹道 a=-g/2", err < 0.02, "err=%.4f a=%.4f" % (err, c[0])))
    dm = max(np.linalg.norm(throw((i + 1) / N)["wri_r"][:2]
                            - throw(i / N)["wri_r"][:2]) for i in range(N))
    r.append(("无跳变", dm * H_M < 0.10, "%.4f m/frame" % (dm * H_M)))
    low = max(min(throw(i / N)["toe_l"][1], throw(i / N)["heel_l"][1])
              for i in range(N + 1))
    r.append(("支撑脚贴地", low * H_M < 0.02, "%.4f m" % (low * H_M)))
    ok = True
    for n_, ok_, s in r:
        print(("PASS " if ok_ else "FAIL ") + n_ + "  " + s)
        ok = ok and ok_
    return ok


@capability("throw", source="动力链顺序(Fleisig et al.1996 Sports Medicine DOI 10.2165/00007256-199621060-00004); 抛体 R=u²sin2θ/g",
            group="prop")
def _cap_throw(u, p):
    return throw(u)


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
