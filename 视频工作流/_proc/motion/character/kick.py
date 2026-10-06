"""踢球（A6/B10 通用）

契约: motion/character/kick
  输入: t∈[0,1] 全局进度
  输出: 关节字典(u,v,w) 归一化身高；接触点/脚速(米、米每秒)
  依赖: numpy motion.character.leg motion.character.ball
  被依赖: tests/run_all
  约束: 摆动腿用两骨 IK(膝朝前) 保证骨长; 触球为"接触不穿透";
        冲击沿法向动量守恒+恢复系数; 支撑脚全程贴地
公式出处:
  · 近端到远端顺序: 髋伸→膝屈蓄势→髋屈+膝继续屈→伸膝鞭打→触球
    小腿触球瞬时角速度 ≈1891°/s, 大腿峰值 516~573°/s (Dorge 1999)
  · 触球点取脚背靠踝一侧 (Bull-Andersen 1999)
  · 足质量分数 0.0145 (Winter 1990); 足+鞋≈有效击球质量 84% (WCSF 2011)
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
from . import ball
from ..beat import capability

H_M = 1.70
G = ball.G
L1, L2 = 0.245, 0.246
ANK_N = 0.039
TOE_LEN, HEEL_LEN = 0.075, 0.038
HIP_STAND = 0.520
R_TRUNK = 0.298
_AU, _AF = 0.186, 0.146

T_BACK, T_FWD, T_FOLLOW = 0.26, 0.14, 0.20
T_TOTAL = T_BACK + T_FWD + T_FOLLOW
F_IMPACT = (T_BACK + T_FWD) / T_TOTAL

_R_IMPACT = 0.4623                       # 触球时髋踝距(膝近伸直)
_ANK_Y_IMPACT = ball.R_BALL / H_M        # 触球时踝高 = 球半径(脚背平球心)
_DY = HIP_STAND - _ANK_Y_IMPACT
_TH_IMPACT = math.acos(_DY / _R_IMPACT)  # 髋踝连线偏离竖直的角度
_C_IMPACT = np.array([_R_IMPACT * math.sin(_TH_IMPACT), _ANK_Y_IMPACT])
INSTEP_FWD = 0.045                       # 触球点相对踝前移(脚背靠踝一侧), 米
U_BALL_M = _C_IMPACT[0] * H_M + INSTEP_FWD + ball.R_BALL   # 球心初始水平位(米)
_A_START = np.array([-0.08, 0.12])
_A_BACK = np.array([-0.13, 0.30])
_A_FOLLOW = np.array([0.30, 0.28])


def _S(u, v, w=0.0):
    return np.array([float(u), float(v), float(w)])


def _ss(x):
    x = min(1.0, max(0.0, float(x)))
    return x * x * (3.0 - 2.0 * x)


def _ankle_path(t):
    """踝轨迹: 后摆(缓) → 前摆(水平加速 + 竖直先落平) → 随挥(减速)

    竖直分量用 ease-out(1-(1-u)²): 膝伸展在摆动前段完成, 触球瞬时竖直速度≈0,
    故触球速度沿水平方向(近端髋屈主导的"扫过"击球)
    """
    s = float(t) * T_TOTAL
    if s < T_BACK:
        return _A_START + (_A_BACK - _A_START) * _ss(s / T_BACK)
    if s < T_BACK + T_FWD:
        u = (s - T_BACK) / T_FWD
        eu = u * u
        ev = 1.0 - (1.0 - u) ** 2
        return np.array([_A_BACK[0] + (_C_IMPACT[0] - _A_BACK[0]) * eu,
                         _A_BACK[1] + (_C_IMPACT[1] - _A_BACK[1]) * ev])
    u = _ss((s - T_BACK - T_FWD) / T_FOLLOW)
    return _C_IMPACT + (_A_FOLLOW - _C_IMPACT) * u


def contact_point(t):
    """脚背触球点(米), 2D: (水平, 竖直)"""
    a = _ankle_path(t) * H_M
    return np.array([a[0] + INSTEP_FWD, a[1]])


def foot_vel(t, dt=1e-5):
    """触球点速度(米每秒), 后向差分

    触球是"击打瞬间": 物理上取接触前一瞬的速度(之后脚已减速/改向),
    中心差分会把随挥段的减速平均进来, 低估一半
    """
    t = float(t)
    lo = max(0.0, t - dt)
    return (contact_point(t) - contact_point(lo)) / ((t - lo) * T_TOTAL)


def ball_center(t):
    """球心(米): 触球前静止于地面, 触球后按碰撞结果飞行"""
    if t <= F_IMPACT:
        return np.array([U_BALL_M, ball.R_BALL])
    n = foot_vel(F_IMPACT)
    n = n / np.linalg.norm(n)
    vfa, vb = ball.impact(foot_vel(F_IMPACT), n)
    p0 = np.array([U_BALL_M, ball.R_BALL])
    tau = (t - F_IMPACT) * T_TOTAL + (t - F_IMPACT) * (0.0)
    # 触球后单独计时: 用与动作等长的物理时长
    tt = (t - F_IMPACT) / (1.0 - F_IMPACT) * 1.2
    _, P = ball.trajectory(p0, vb, tt, 1.0 / 120.0)
    return P[-1]


def kick(t, scale_h=1.0):
    t = min(1.0, max(0.0, float(t)))
    y = HIP_STAND
    lean = 0.10 * math.sin(math.pi * min(1.0, t / max(F_IMPACT, 1e-6)))
    out = {"pelvis": _S(0.0, y), "waist": _S(-R_TRUNK * 0.35 * lean, y + R_TRUNK * 0.35),
           "chest": _S(-R_TRUNK * lean, y + R_TRUNK),
           "neck": _S(-(R_TRUNK + 0.052) * lean, y + R_TRUNK + 0.052),
           "head": _S(-(R_TRUNK + 0.130) * lean, y + R_TRUNK + 0.130)}
    a_k = _ankle_path(t)
    hip_k = np.array([0.0, y])
    kn_k = two_bone_ik(hip_k, a_k, L1, L2, bend=(1.0, 0.0))
    pit = math.radians(45.0) * (t / F_IMPACT if t < F_IMPACT else 1.0)
    td = np.array([math.cos(pit), math.sin(pit)])
    out["hip_r"] = _S(0.0, y, -0.055)
    out["knee_r"] = _S(kn_k[0], kn_k[1], -0.055)
    out["ank_r"] = _S(a_k[0], a_k[1], -0.055)
    out["toe_r"] = _S(a_k[0] + TOE_LEN * td[0], a_k[1] + TOE_LEN * td[1], -0.055)
    out["heel_r"] = _S(a_k[0] - HEEL_LEN * td[0], a_k[1] - HEEL_LEN * td[1], -0.055)
    a_s = np.array([-0.03, ANK_N])
    hip_s = np.array([0.0, y])
    kn_s = two_bone_ik(hip_s, a_s, L1, L2, bend=(1.0, 0.0))
    out["hip_l"] = _S(0.0, y, 0.055)
    out["knee_l"] = _S(kn_s[0], kn_s[1], 0.055)
    out["ank_l"] = _S(a_s[0], a_s[1], 0.055)
    out["toe_l"] = _S(a_s[0] + TOE_LEN, 0.0, 0.055)
    out["heel_l"] = _S(a_s[0] - HEEL_LEN, 0.0, 0.055)
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        th = -0.9 * sgn if side == "l" else 0.7 * sgn
        el = -0.8 * sgn
        sh = (-(R_TRUNK - 0.02) * lean, y + R_TRUNK - 0.02)
        ex = sh[0] + _AU * math.sin(th)
        ey = sh[1] - _AU * math.cos(th)
        t2 = th + el
        wx, wy = ex + _AF * math.sin(t2), ey - _AF * math.cos(t2)
        out["sh_" + side] = _S(sh[0], sh[1], 0.08 * sgn)
        out["elb_" + side] = _S(ex, ey, 0.08 * sgn)
        out["wri_" + side] = _S(wx, wy, 0.08 * sgn)
    return out


def self_check():
    r = []
    N = 600
    mx = 0.0
    for i in range(N + 1):
        J = kick(i / N)
        for s in ("l", "r"):
            h, k, a = J["hip_" + s][:2], J["knee_" + s][:2], J["ank_" + s][:2]
            mx = max(mx, abs(np.linalg.norm(k - h) - L1), abs(np.linalg.norm(a - k) - L2))
    r.append(("骨长守恒", mx < 1e-9, "max=%.2e" % mx))
    vf = foot_vel(F_IMPACT)
    n = vf / np.linalg.norm(vf)
    r.append(("触球速度水平前向", n[0] > 0.95 and abs(n[1]) < 0.15,
              "%.2f m/s  n=(%.3f,%.3f)"
              % (np.linalg.norm(vf), n[0], n[1])))
    d = np.linalg.norm(contact_point(F_IMPACT) - np.array([U_BALL_M, ball.R_BALL]))
    r.append(("触球为接触不穿透", abs(d - ball.R_BALL) < 5e-3,
              "dist=%.4f vs R=%.4f" % (d, ball.R_BALL)))
    worst = min(np.linalg.norm(contact_point(i / N) - np.array([U_BALL_M, ball.R_BALL]))
                - ball.R_BALL for i in range(int(N * F_IMPACT)))
    r.append(("触球前不穿球", worst > -1e-3, "min gap=%.5f m" % worst))
    M = ball.strike_mass()
    vfa, vb = ball.impact(vf, n)
    p1, p2 = M * vf, M * vfa + ball.M_BALL * vb
    r.append(("碰撞动量守恒", np.linalg.norm(p2 - p1) / np.linalg.norm(p1) < 1e-12,
              "err=%.2e" % (np.linalg.norm(p2 - p1) / np.linalg.norm(p1))))
    r.append(("球被踢出", np.linalg.norm(vb) > 3.0, "v=%.2f m/s" % np.linalg.norm(vb)))
    low = 0.0
    for i in range(N + 1):
        J = kick(i / N)
        low = max(low, min(J["toe_l"][1], J["heel_l"][1], J["ank_l"][1]))
    r.append(("支撑脚贴地", low * H_M < 0.02, "%.4f m" % (low * H_M)))
    dmax = max(np.linalg.norm(kick((i + 1) / N)["ank_r"][:2] - kick(i / N)["ank_r"][:2])
               for i in range(N))
    r.append(("无跳变", dmax * H_M < 0.06, "%.4f m/frame" % (dmax * H_M)))
    ok = True
    for n_, ok_, s in r:
        print(("PASS " if ok_ else "FAIL ") + n_ + "  " + s)
        ok = ok and ok_
    return ok


@capability("kick", source="近端到远端顺序(Dorge 1999); 足质量分数0.0145(Winter 1990)",
            group="locomotion")
def _cap_kick(u, p):
    return kick(u)


@capability("ball", source="球规格(IFAB Law 2); 恢复系数 h_n=ε^{2n}h_0(UA PH125)",
            group="prop")
def _cap_ball(u, p):
    return ball_center(u)


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
