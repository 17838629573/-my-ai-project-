"""下蹲（A7）

契约: motion/character/crouch
  输入: q∈[0,1] 下蹲进度；obj 物体 (u,v,r) 归一化
  输出: 同 gait 的关节字典 (u,v,w)，归一化身高单位
  依赖: numpy motion.character.leg
  被依赖: tests/run_all
  约束: 双脚全程贴地不滑不飘；躯干前倾由"够到物体"的臂展反解；
        |髋踝|≤L1+L2；|肩→握心| ≤ 臂展+握距
"""
import math
import numpy as np

from .leg import two_bone_ik
from ..beat import capability

H_M = 1.70
L1, L2 = 0.245, 0.246
ANK_N = 0.039
TOE_LEN, HEEL_LEN = 0.075, 0.038
HIP_STAND = 0.520
R_TRUNK = 0.298
_AU, _AF = 0.186, 0.146
WRIST_TO_GRIP = 0.038
ARM_REACH = _AU + _AF + WRIST_TO_GRIP

HIP_PICK_N = 0.30       # 拾取姿态髋高（0.51 m）
LEAN_PICK = math.radians(78.0)
OBJ_R_N = 0.02 / H_M    # 地面物体半径 2 cm
OBJ_U = R_TRUNK * math.sin(LEAN_PICK)
OBJ_V = OBJ_R_N


def _S(u, v, w=0.0):
    return np.array([float(u), float(v), float(w)])


def _ss(x):
    return x * x * (3.0 - 2.0 * x)


def _arm(su, sv, th_sh, th_el):
    ex = su + _AU * math.sin(th_sh)
    ey = sv - _AU * math.cos(th_sh)
    t2 = th_sh + th_el
    return (ex, ey), (ex + _AF * math.sin(t2), ey - _AF * math.cos(t2))


def crouch(q, with_arms=True):
    q = min(1.0, max(0.0, float(q)))
    e = _ss(q)
    y = HIP_STAND - (HIP_STAND - HIP_PICK_N) * e
    lean = LEAN_PICK * e
    su, sv = R_TRUNK * math.sin(lean), y + R_TRUNK * math.cos(lean)
    out = {"pelvis": _S(0.0, y), "waist": _S(R_TRUNK * 0.35 * math.sin(lean),
                                             y + R_TRUNK * 0.35 * math.cos(lean)),
           "chest": _S(su, sv), "neck": _S(su + 0.052 * math.sin(lean),
                                           sv + 0.052 * math.cos(lean)),
           "head": _S(su + 0.130 * math.sin(lean), sv + 0.130 * math.cos(lean))}
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        hip = np.array([0.0, y])
        ank = np.array([0.0, ANK_N])
        kn = two_bone_ik(hip, ank, L1, L2, bend=(1.0, 0.0))
        w = 0.055 * sgn
        out["hip_" + side] = _S(0.0, y, w)
        out["knee_" + side] = _S(kn[0], kn[1], w)
        out["ank_" + side] = _S(0.0, ANK_N, w)
        out["toe_" + side] = _S(TOE_LEN, ANK_N, w)
        out["heel_" + side] = _S(-HEEL_LEN, ANK_N, w)
        if with_arms:
            # 下蹲时双臂自然下垂前摆，末端随进度前伸
            th = (0.15 + 0.85 * e) * sgn
            el = -0.5 * sgn
            (ex, ey), (wx, wy) = _arm(su, sv - 0.02, th, el)
            out["sh_" + side] = _S(su, sv - 0.02, 0.08 * sgn)
            out["elb_" + side] = _S(ex, ey, 0.08 * sgn)
            out["wri_" + side] = _S(wx, wy, 0.08 * sgn)
    return out


def reach_pose(q, obj_u=OBJ_U, obj_v=OBJ_V, obj_r=OBJ_R_N, arm=1.0):
    """下蹲 + 手臂两骨 IK 伸向物体（肩固定、肘向后弯）

    arm: 伸手程度 0=自然下垂（随蹲姿摆动） 1=完全抓握到物体
    """
    qq = min(1.0, max(0.0, float(q)))
    a = min(1.0, max(0.0, float(arm)))
    J = crouch(qq, with_arms=False)
    nat = crouch(qq, with_arms=True)
    sh = np.array([J["chest"][0], J["chest"][1] - 0.02])
    tgt = np.array([float(obj_u), float(obj_v)])
    d = tgt - sh
    L = float(np.linalg.norm(d))
    ux = d / L if L > 1e-9 else np.array([0.0, -1.0])
    grip = tgt - ux * (float(obj_r) + WRIST_TO_GRIP)
    side = "r"
    sgn = -1.0
    el = two_bone_ik(sh, grip, _AU, _AF, bend=(-1.0, 0.0))
    # 由自然下垂线性混合到 IK 抓握位，保证中途不跳变
    ne, nw = nat["elb_" + side][:2], nat["wri_" + side][:2]
    ex = float(ne[0] + (el[0] - ne[0]) * a)
    ey = float(ne[1] + (el[1] - ne[1]) * a)
    wx = float(nw[0] + (grip[0] - nw[0]) * a)
    wy = float(nw[1] + (grip[1] - nw[1]) * a)
    J["sh_" + side] = _S(sh[0], sh[1], 0.08 * sgn)
    J["elb_" + side] = _S(ex, ey, 0.08 * sgn)
    J["wri_" + side] = _S(wx, wy, 0.08 * sgn)
    other = "l"
    J["sh_" + other] = _S(sh[0], sh[1], -0.08)
    (lx, ly), (lw_x, lw_y) = _arm(sh[0], sh[1], 0.55, -0.7)
    J["elb_" + other] = _S(lx, ly, -0.08)
    J["wri_" + other] = _S(lw_x, lw_y, -0.08)
    return J


def self_check():
    r = []
    J0, J1 = crouch(0.0), crouch(1.0)
    r.append(("站立髋高", abs(J0["pelvis"][1] - HIP_STAND) < 1e-9, "%.4f" % J0["pelvis"][1]))
    r.append(("拾取髋高", abs(J1["pelvis"][1] - HIP_PICK_N) < 1e-9,
              "%.4f m" % (J1["pelvis"][1] * H_M)))
    mx = 0.0
    sk = 0.0
    prev = None
    for i in range(201):
        J = crouch(i / 200.0)
        for side in ("l", "r"):
            h, k, a = J["hip_" + side][:2], J["knee_" + side][:2], J["ank_" + side][:2]
            mx = max(mx, abs(np.linalg.norm(k - h) - L1),
                     abs(np.linalg.norm(a - k) - L2))
        cur = float(J["ank_l"][0])
        if prev is not None:
            sk = max(sk, abs(cur - prev))
        prev = cur
    r.append(("骨长守恒", mx < 1e-6, "max=%.2e" % mx))
    r.append(("双脚不打滑", sk < 1e-9, "max=%.2e" % sk))
    J = reach_pose(1.0)
    sh = np.array([J["sh_r"][0], J["sh_r"][1]])
    wr = np.array([J["wri_r"][0], J["wri_r"][1]])
    reach = float(np.linalg.norm(wr - sh)) + WRIST_TO_GRIP
    r.append(("臂展不超限", reach <= ARM_REACH + 1e-9,
              "%.4f/%.4f" % (reach, ARM_REACH)))
    elb = np.array([J["elb_r"][0], J["elb_r"][1]])
    fore = float(np.linalg.norm(elb - wr))
    r.append(("前臂长度守恒", abs(fore - _AF) < 1e-6, "%.4f/%.4f" % (fore, _AF)))
    ok = True
    for n, ok_, s in r:
        print(("PASS " if ok_ else "FAIL ") + n + "  " + s)
        ok = ok and ok_
    return ok


@capability("crouch", source="深蹲膝~124°/髋~124°（Cursa / Kinetech 解剖）", group="posture")
def _cap_crouch(u, p):
    return crouch(u)


@capability("reach_grab", source="Fitts 定律 ID=log2(2A/W)；两骨 IK 伸向目标", group="grasp")
def _cap_reach(u, p):
    return reach_pose(u)


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
