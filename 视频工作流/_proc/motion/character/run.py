"""跑步与急停（A2）

契约: proc/motion/character/run
  输入: 步相ph、速度v(m/s)、身高H(m)；急停为时间t(s)
  输出: run -> 归一化关节字典；brake -> {'v':速度,'d':已行距离,'J':关节}
  依赖: numpy, proportions, gait
  被依赖: tests/run_all, tests/gen
  约束: 支撑占比(占空比)β=0.35，腾空占比 1-2β；
        步长由回归式给出而非手填；急停距离取 sprint-to-stop 实测

出处:
  - 占空比 β: 跑 support 35% / swing 65%（Novacheck 1998）；
    duty factor ≈0.35（Minetti & Alexander 1997）；腾空期占比 1-2β
  - 步长: sl = 0.1394 + 0.00465·v(m/min)，乘 sqrt(H/1.8) 归一化
    （Graphics Interface 1996, Knowledge-Driven Animation of Human Running,
     n=80, r²=0.94442）；v>400m/min 后步长封顶只提频
  - 步频: v = sl · sf
  - 走跑转换: Froude 数 Fr=v²/(g·L)≈0.5（Alexander），v≈1.9 m/s @ H=1.70
  - 躯干前倾: 精英马拉松 2~4°（Kyröläinen 2005）；冲刺 10~20°
  - 急停距离: 5m/20m sprint-to-stop 减速距离 2.39~7.93 m（Graham-Smith），
    占总程 40~58%；峰值 GRF 可达 5.9 BW
  - 急停姿态: 降 COM（屈髋后坐）、脚置于 COM 前方、躯干直立或略后倾
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

import importlib
from ..beat import capability
from .body import MOVED_TO_BODY
from .body.leg import two_bone_ik
from .body.proportions import PROP

def _m(n):
    """同包子模块：优先相对导入，避免依赖 _proc 在 sys.path 上

    历史坑: 曾写死绝对导入 "_proc.motion.character."+n，
    当入口只把 _proc 自身放进 sys.path 时（tests/run_all 即如此）
    直接 ModuleNotFoundError，A3/A7 全部 ERROR。
    """
    if n in MOVED_TO_BODY:      # 形体核心层已下沉到 body/ 子包（拆 motion 上帝包）
        return importlib.import_module(".body." + n, __package__)
    return importlib.import_module("." + n, __package__)

G = _m("gait")

BETA = 0.35                 # 占空比：单脚支撑占周期比例（跑）
FLIGHT_FRAC = 1.0 - 2 * BETA   # 腾空期占比 0.30
V_NORM = 400.0 / 60.0       # 6.667 m/s，步长封顶速度
SL_A = 0.1394               # 步长回归截距 (m)
SL_B = 0.00465              # 步长回归斜率 (m per m/min)

TRUNK_LEAN_JOG = 3.0        # 慢跑前倾 1~3°（取上限）
TRUNK_LEAN_SPRINT = 15.0    # 全速冲刺 10~20°（取中值）
BRAKE_LEAN = -4.0           # 急停躯干直立或略后倾
D_STOP = 2.39               # 5m sprint-to-stop 减速距离 (m)
G_ACC = 9.80665



def step_len(v, H=1.70):
    """步幅(m)。v: m/s。sl = (0.1394 + 0.00465·v_min)·sqrt(H/1.8)。"""
    v = min(float(v), V_NORM)
    vmin = v * 60.0
    sl = (SL_A + SL_B * vmin) * np.sqrt(H / 1.80)
    return float(sl)


def step_freq(v, H=1.70):
    """步频(步/秒)。v = sl·sf → sf = v/sl。"""
    sl = step_len(v, H)
    return float(v) / sl if sl > 1e-9 else 0.0


def trunk_lean(v):
    """躯干前倾角(度)。慢跑 3°，冲刺 15°，线性插值。"""
    u = min(max((float(v) - 1.9) / (V_NORM - 1.9), 0.0), 1.0)
    return TRUNK_LEAN_JOG + u * (TRUNK_LEAN_SPRINT - TRUNK_LEAN_JOG)


def _foot_y(ph, beta):
    """摆动腿竖直轨迹：支撑段贴地，腾空段抬摆。返回抬起高度(归一化身高)。"""
    if ph < beta:                      # 支撑（含缓冲与蹬伸）
        return 0.0
    u = (ph - beta) / (1.0 - beta)     # 摆动段 0→1
    return float(np.sin(np.pi * u)) * 0.16


V_RUN = 3.2                 # 默认跑速 (m/s)
DUTY_RUN = BETA             # 占空比（步态学惯例称 duty factor）
T_STRIDE = 1.0 / step_freq(V_RUN)      # 单步周期 (s)
T_FLIGHT = (0.5 - BETA) * T_STRIDE     # 单次腾空时长 (s)
T_BRAKE = 2.0 * D_STOP / V_RUN         # 匀减速至 0 所需时间 (s)
ANK_N = float(_m("gait").gait(0.0, "natural")["ank_l"][1])
# 地面基准必须是"最低关节触地"时的 v，而不是踝高：
# 实测一个跑步周期内最低点 0.0281797 出现在 heel（脚跟先着地），
# 用 ANK_N(0.0412) 当基准会让脚掌整体陷进地面 0.022 m
GROUND_V = 0.0281797
FOOT_HEEL_U = 0.0357083     # 脚跟相对踝的后向偏移（归一化身高）
FOOT_TOE_U = 0.0704769      # 脚尖相对踝的前向偏移
FOOT_ANK_H = 0.0129968      # 踝高于脚底
FP_STRIKE_DEG = 8.0         # 触地：脚尖上翘（脚跟先着地）
FP_TOE_OFF_DEG = -28.0      # 蹬离：脚跟抬起（脚尖最后离地）


def _foot_pitch_run(p):
    """跑的脚掌俯仰：支撑段 触地(+8°)→平放(0°)→蹬离(-28°)；摆动段回到 +8°。

    姿态角取自正常步态实测关键点表，摆动段用 smoothstep 回位保证一阶连续。
    """
    sw = 1.0 - BETA
    if p < BETA:
        s = p / BETA
        if s < 0.3:                      # 触地 → 全脚放平
            return math.radians(FP_STRIKE_DEG * (1.0 - s / 0.3))
        s2 = (s - 0.3) / 0.7             # 放平 → 脚跟抬起蹬离
        return math.radians(FP_TOE_OFF_DEG * s2)
    u = min((p - BETA) / sw, 1.0)        # 摆动：蹬离角 → 触地角
    t = u * u * (3.0 - 2.0 * u)
    return math.radians(FP_TOE_OFF_DEG + (FP_STRIKE_DEG - FP_TOE_OFF_DEG) * t)


def run(ph, v=3.2, H=1.70):
    """跑步步态。ph: 步相 0~1（单腿周期）。返回归一化关节字典。

    脚下落采用"绝对赋值"而非增量叠加——这是修掉单腿跳的关键：
    旧版以 gait(0.0) 为基准做增量，右脚在 p=0.5 时 lift=0 却抬着，
    永远回不到地面。现按每只脚各自的相位独立算贴地高度。
    """
    ph = float(ph) % 1.0
    base = G.gait(0.0, "natural")
    J = {k: np.asarray(x, dtype=float) for k, x in base.items()}
    sl = step_len(v, H)
    half = sl / (2.0 * H)              # 单步幅度（归一化身高）
    swing = 1.0 - BETA
    L1 = float(PROP["thigh"])
    L2 = float(PROP["shank"])

    # 腾空段整体抬升（先算，脚部继承）
    hw = 0.5 - BETA
    T_STRIDE = 1.0 / step_freq(v, H)
    T_F = hw * T_STRIDE
    apex = G_ACC * T_F * T_F / 8.0 / H
    tau = None
    if BETA <= ph < 0.5:
        tau = (ph - BETA) / hw
    elif 0.5 + BETA <= ph < 1.0:
        tau = (ph - 0.5 - BETA) / hw
    body = 4.0 * apex * tau * (1.0 - tau) if tau is not None else 0.0

    cu = 0.5 * (base["ank_l"][0] + base["ank_r"][0])
    for side, off in (("l", 0.0), ("r", 0.5)):
        p = (ph + off) % 1.0
        if p < BETA:                                  # 支撑：脚从前滑到后
            ahead = half * (1.0 - 2.0 * p / BETA)
        else:                                         # 摆动：脚从后摆回前
            ahead = -half + 2.0 * half * (p - BETA) / swing
        th = _foot_pitch_run(p)
        st, ct = np.sin(th), np.cos(th)
        # 脚掌绕踝旋转后，脚跟/脚尖相对踝的 v 偏移；低者即为接地点
        hv = -FOOT_HEEL_U * st - FOOT_ANK_H * ct
        tv = FOOT_TOE_U * st - FOOT_ANK_H * ct
        low = min(hv, tv)
        ank_u = cu + ahead
        ank_v = GROUND_V + _foot_y(p, BETA) + body - low
        hip = np.array([base["hip_" + side][0],
                        base["hip_" + side][1] + body])
        knee = two_bone_ik(hip, np.array([ank_u, ank_v]), L1, L2,
                           bend=(1.0, 0.0))
        J["ank_" + side][0] = ank_u
        J["ank_" + side][1] = ank_v
        J["knee_" + side][0] = knee[0]
        J["knee_" + side][1] = knee[1]
        J["heel_" + side][0] = ank_u + (-FOOT_HEEL_U * ct + FOOT_ANK_H * st)
        J["heel_" + side][1] = ank_v + hv
        J["toe_" + side][0] = ank_u + (FOOT_TOE_U * ct + FOOT_ANK_H * st)
        J["toe_" + side][1] = ank_v + tv

    for k in ("pelvis", "hip_l", "hip_r", "waist", "chest", "neck", "head",
              "sh_l", "sh_r", "elb_l", "elb_r", "wri_l", "wri_r"):
        if k in J:
            J[k] = J[k] + np.array([0.0, body, 0.0])
    lean = np.deg2rad(trunk_lean(v))
    for k in ("waist", "chest", "neck", "head"):
        if k in J:
            J[k] = J[k] + np.array([np.sin(lean) * 0.08, 0.0, 0.0])
    return J


def brake(t, v0=3.2, D=D_STOP, H=1.70):
    """急停。返回 {'v':当前速度, 'd':已行距离, 'u':进度, 'J':关节}。"""
    a = v0 * v0 / (2.0 * D)            # 匀减速：v0² = 2aD
    T = v0 / a
    u = min(max(float(t) / T, 0.0), 1.0)
    v = v0 * (1.0 - u)
    d = v0 * T * u - 0.5 * a * (T * u) ** 2
    ph = (d / max(step_len(v0, H), 1e-6)) % 1.0
    J = run(ph, max(v, 0.05), H)
    # 制动姿态：降 COM（后坐）、躯干直立略后倾、脚置于 COM 前方
    drop = 0.06 * np.sin(np.pi * min(u, 1.0))
    lean = np.deg2rad(BRAKE_LEAN) * np.sin(np.pi * min(u, 1.0))
    for k in J:
        if k not in ("toe_l", "toe_r", "heel_l", "heel_r", "ank_l", "ank_r"):
            J[k] = J[k] + np.array([np.sin(lean) * 0.08, -drop, 0.0])
    for s in ("l", "r"):
        if "ank_" + s in J:
            J["ank_" + s] = J["ank_" + s] + np.array([0.0, 0.0, 0.03 * u])
    return {"v": float(v), "d": float(d), "u": float(u), "T": float(T),
            "a": float(a), "ph": float(ph % 1.0), "J": J}


@capability("run", group="locomotion",
            source="Novacheck 1998 / Minetti-Alexander 1997 (β=0.35); "
                   "GI 1996 步长回归 sl=0.1394+0.00465v")
def _c_run():
    return run


@capability("brake", group="locomotion",
            source="Graham-Smith sprint-to-stop DTS 2.39m; "
                   "Harper 制动姿态:降COM/脚前置/躯干直立略后倾")
def _c_brake():
    return brake


def self_check():
    def chk(n, c, e=""):
        print("  %-26s %s%s" % (n, "PASS" if c else "FAIL",
                                "" if c else "  <- " + str(e)))
        return bool(c)

    ok = True
    sl3 = step_len(3.2, 1.70)
    ok &= chk("占空比=0.35", abs(BETA - 0.35) < 1e-12)
    ok &= chk("腾空占比=1-2β", abs(FLIGHT_FRAC - 0.30) < 1e-9)
    ok &= chk("步长随速度增", step_len(4.0) > sl3 > step_len(2.0),
              (step_len(2.0), sl3, step_len(4.0)))
    ok &= chk("步长量级(3.2m/s 1.0~1.9m)", 1.0 < sl3 < 1.9, sl3)
    ok &= chk("步频 v=sl·sf", abs(step_freq(3.2) * step_len(3.2) - 3.2) < 1e-9)
    ok &= chk("前倾 慢跑<冲刺", trunk_lean(2.0) < trunk_lean(6.0),
              (trunk_lean(2.0), trunk_lean(6.0)))
    ok &= chk("前倾在 1~20°", 1.0 <= trunk_lean(2.0) <= 20.0)
    ok &= chk("急停末速=0", abs(brake(99.0)["v"]) < 1e-12)
    ok &= chk("急停距离=D", abs(brake(99.0)["d"] - D_STOP) < 1e-9,
              brake(99.0)["d"])
    ok &= chk("减速 a=v²/2D", abs(brake(0.0)["a"] - 3.2 ** 2 / (2 * 2.39)) < 1e-12)
    lows = []
    for i in range(60):
        J = run(i / 60.0, 3.2)
        lows.append(min(v[1] for v in J.values()))
    ok &= chk("跑步不穿地", min(lows) > -1e-9, min(lows))
    ok &= chk("跑步有腾空帧", max(lows) > 1e-6, max(lows))
    print("run/brake 自检:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    self_check()
