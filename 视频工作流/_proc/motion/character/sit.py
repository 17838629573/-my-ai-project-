# 契约: proc/motion/character/sit
#   一句话: 坐下/站起动作 —— 7 关键姿态 + 三相位，输出与 gait 同构的关节字典
#   完整契约见 motion/character/__init__.py
"""坐下 / 站起（W2）

与 gait 同构：输入相位 p∈[0,1)，输出 {关节名: (u, v, w)}（归一化身高单位）。
因此 render/cloth/beat 全链路无需改动即可复用。

数据来源（不手填系数）：
  时序  Cursa Body Mechanics Mini-Shots：
        坐下 18~28 帧（预备 6-10 / 动作 8-12 / 沉降 4-6）
        保持 6~10 帧
        站起 18~28 帧（同结构）
        取 24 / 8 / 24 = 56 帧 @24fps ≈ 2.33s
  关节角 MDPI Sensors 2026 STS 实测（%STS 周期）：
        预备相 0-20%    髋屈 10~30°  踝背屈 5~15°  躯干屈 20~45°
        上升相 20-50%   躯干伸 15~35° 髋伸 70~90° 膝伸 60~80° 踝跖屈 15~20°
        50% 达完全直立峰值
        下降相 50-80%   反向，80% 触椅
        恢复相 80-100%  躯干伸/髋伸/踝跖屈回起始
  约束  Cursa 自检四条：
        ① 能指出确切的触椅帧与离椅帧
        ② 脚在承重时刻不得漂移
        ③ 髋走出"下/后"弧线入座、"前/上"弧线离座
        ④ 胸/头滞后于髋，再回稳
"""
import math
import numpy as np
from typing import NamedTuple

from .body.proportions import PROP, STANCE_FRAC
from .body.leg import two_bone_ik

# ------------------------------------------------------------------
# 时序（Cursa：24 / 8 / 24 = 56 帧 @24fps）
# ------------------------------------------------------------------
SIT_F   = 24 / 56
HOLD_F  = 8 / 56
STAND_F = 24 / 56
# 段内三相位（预备 / 动作 / 沉降）
PREP_A  = 8 / 24
ACT_A   = 10 / 24
SET_A   = 6 / 24

# ------------------------------------------------------------------
# 几何（归一化身高单位）
# ------------------------------------------------------------------
SEAT_V    = 0.2647   # 标准椅座高 0.45m / 1.70m
THIGH_R   = 0.052    # 大腿半径（与 BODY_SPEC 一致）→ 髋中心离座面
CHAIR_U   = -0.155   # 坐姿髋踝水平距：大腿0.245 水平投影（小腿略前倾）
LAT_HIP   = 0.085    # 髋半宽
LAT_KNEE  = 0.075
LAT_ANK   = 0.070
TOE_LEN   = 0.075
HEEL_LEN  = 0.055
TOE_OFF   = 0.030    # 脚尖相对踝的前伸（平放时）

# 躯干前屈角（度，前屈为正）—— MDPI：预备 20~45°，取中 40°；坐定残余 3°
LEAN_SIT_PREP = 40.0
LEAN_SEATED   = 3.0
LEAN_STD_PREP = 40.0
LEAN_OVERSHOOT = -3.0   # 站起过冲（躯干伸），再回稳到 0

_SEAT_HIP_V = SEAT_V + THIGH_R      # 坐姿髋高 ≈ 0.317
_STAND_HIP_V = PROP["hip"]          # 0.520


def _S(a, b, c=0.0):
    """构造关节向量（模块级，供脊柱/臂复用）。"""
    return np.array([a, b, c], dtype=np.float64)


def _ease(x):
    """smoothstep 缓动（业界标准 ease-in-out）：位置过零时速度也为零。"""
    x = min(1.0, max(0.0, x))
    return x * x * (3.0 - 2.0 * x)


def _phase_split(p):
    """把 p∈[0,1) 拆成 (段名, 段内归一化进度 q, 段内子相位)。"""
    p = p % 1.0
    if p < SIT_F:
        return "sit", p / SIT_F
    if p < SIT_F + HOLD_F:
        return "hold", (p - SIT_F) / HOLD_F
    return "stand", (p - SIT_F - HOLD_F) / STAND_F


def _sub(q):
    """段内三相位：预备 / 动作 / 沉降 → (子阶段, 子进度)。"""
    if q < PREP_A:
        return "prep", q / PREP_A
    if q < PREP_A + ACT_A:
        return "act", (q - PREP_A) / ACT_A
    return "set", (q - PREP_A - ACT_A) / SET_A



# ================================================================
# 拆分子函数（Composed Method：顶层讲故事，边界隐藏有意义决策）
#   拆分依据  Composed Method（Beck）：函数只讲一个层次的故事
#   参数对象  Hip(u, v, lean) —— 参数超 3 个时收敛为 NamedTuple
#   同构      与 gait.py 的 solve_root/solve_legs/solve_spine/solve_arms 对齐
# ================================================================

class Hip(NamedTuple):
    """髋状态参数对象（u=前后, v=高, lean=躯干前屈角(度)）"""
    u: float
    v: float
    lean: float


def solve_hip(seg, sub, e):
    """髋高 / 前后位移 / 躯干前倾 —— 三相位查表（Cursa 7 关键姿态 + MDPI 实测角）。

    坐下：预备"load back" → 动作沿"下/后"弧线入座 → 沉降压缩回弹
    站起：预备"gather" → 动作沿"前/上"弧线离座 → 沉降过冲回稳
    """
    if seg == "sit":
        if sub == "prep":
            # 预备：髋略升后开始后移，高度几乎不动
            return Hip(0.0, _STAND_HIP_V - 0.010 * math.sin(math.pi * e),
                       LEAN_SIT_PREP * e)
        if sub == "act":
            # 动作：髋沿"下/后"弧线入座；lean 全程前屈以抵消髋后移
            return Hip(CHAIR_U * (e * e),
                       _STAND_HIP_V + (_SEAT_HIP_V - _STAND_HIP_V) * e,
                       LEAN_SIT_PREP)
        # 沉降：小幅压缩再回弹
        return Hip(CHAIR_U, _SEAT_HIP_V - 0.008 * math.sin(math.pi * e),
                   LEAN_SEATED + (0.0 - LEAN_SEATED) * e * 0.4)
    if seg == "hold":
        return Hip(CHAIR_U, _SEAT_HIP_V, LEAN_SEATED)
    if sub == "prep":
        # 站起预备：躯干前倾 + 髋移向脚（Cursa Key5 "gather"）
        return Hip(CHAIR_U * (1.0 - 0.45 * e),
                   _SEAT_HIP_V + 0.012 * math.sin(math.pi * e),
                   LEAN_SEATED + (LEAN_STD_PREP - LEAN_SEATED) * e)
    if sub == "act":
        # 动作：离座，髋沿"前/上"弧线；lean 由前屈过冲到伸展
        return Hip(CHAIR_U * (1.0 - 0.45) * (1.0 - e),
                   _SEAT_HIP_V + (_STAND_HIP_V - _SEAT_HIP_V) * e,
                   LEAN_STD_PREP + (LEAN_OVERSHOOT - LEAN_STD_PREP) * e)
    # 沉降：上半身过冲后回稳（Cursa Key7 "overshoot and settle"）
    return Hip(0.0, _STAND_HIP_V + 0.006 * math.sin(math.pi * e),
               LEAN_OVERSHOOT * (1.0 - e))


def solve_legs(hip_uv):
    """腿与脚 —— 脚先锁定，膝由两骨 IK 反求（膝弯多少是几何后果，不手填）。

    Cursa 第②条：脚在承重时刻不得漂移；故踝恒定在 (0, PROP['ankle'])。
    """
    L1, L2 = PROP["thigh"], PROP["shank"]     # two_bone_ik(root, target, L1, L2)
    ank = np.array([0.0, PROP["ankle"]])
    knee_uv = two_bone_ik(hip_uv, ank, L1, L2, bend=(1.0, 0.0))  # 膝朝前
    out = {}
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        # 脚掌：坐下/站起全程平放（pit=0）
        out["hip_" + side] = np.array([hip_uv[0], hip_uv[1], LAT_HIP * sgn])
        out["knee_" + side] = np.array([knee_uv[0], knee_uv[1], LAT_KNEE * sgn])
        out["ank_" + side] = np.array([ank[0], ank[1], LAT_ANK * sgn])
        out["toe_" + side] = np.array([ank[0] + TOE_OFF + TOE_LEN,
                                       ank[1], LAT_ANK * sgn])
        out["heel_" + side] = np.array([ank[0] - HEEL_LEN, ank[1], LAT_ANK * sgn])
    return out


def solve_spine(hip, lag, seg):
    """脊柱堆叠 —— lean 是角度，位移 = 倾角 × 力臂；胸/头滞后于髋（Cursa 第④条）。"""
    lean_rad = math.radians(hip.lean)
    u, base_v = hip.u, hip.v
    out = {"pelvis": _S(u, base_v, 0.0)}
    for name, frac, lagw in (("waist", 0.30, 0.4),
                             ("chest", 0.70, 0.7),
                             ("neck", 1.00, 1.0)):
        seg_v = PROP[name] - PROP["hip"]
        out[name] = _S(u + frac * seg_v * math.sin(lean_rad),
                       base_v + seg_v + lag * lagw)
    seg_v3 = PROP["neck"] - PROP["hip"]
    out["head"] = _S(u + 1.15 * seg_v3 * math.sin(lean_rad),
                     base_v + seg_v3 + PROP["head_r"] * 0.95 + lag * 1.2)
    return out


def solve_arms(hip, seg, sub, e, shoulder_v, chest_u):
    """臂 —— 坐下时向后撑（髋后移的反相），站起时前摆；周期起止回到自然下垂。"""
    AU, AF = PROP["upperarm"], PROP["forearm"]
    out = {}
    ARM_REST = 0.05      # 自然下垂（周期起止都回到这里，保证闭合）
    if seg == "sit":
        th_sh = (ARM_REST + (0.55 - ARM_REST) * e) if sub == "prep" else (
                 0.55 if sub == "act" else 0.55 + (0.22 - 0.55) * e)
    elif seg == "hold":
        th_sh = 0.22
    elif sub == "prep":
        th_sh = 0.22 + (-0.15 - 0.22) * e
    elif sub == "act":
        th_sh = -0.15 + (-0.60 + 0.15) * e
    else:
        th_sh = -0.60 + (ARM_REST + 0.60) * e
    th_elb = -0.35 - 0.25 * max(0.0, -th_sh)
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        sh_u = chest_u + sgn * 0.070 * 0.3
        sw = sgn * 0.070
        elb_u = sh_u + AU * math.sin(th_sh)
        elb_v = shoulder_v - AU * math.cos(th_sh)
        wri_u = elb_u + AF * math.sin(th_sh + th_elb)
        wri_v = elb_v - AF * math.cos(th_sh + th_elb)
        out["sh_" + side] = _S(sh_u, shoulder_v, sw)
        out["elb_" + side] = _S(elb_u, elb_v, sw)
        out["wri_" + side] = _S(wri_u, wri_v, sw)
    return out


def _lag_of(seg, sub, e):
    """胸/头相对髋的滞后量 —— 沉降时上半身还在追，站定回稳时还在过冲。"""
    if seg == "sit" and sub == "set":
        return 0.006 * (1.0 - e)
    if seg == "stand" and sub == "set":
        return -0.006 * (1.0 - e)
    return 0.0


def sit_pose(p, preset="natural"):
    """坐下/站起主函数 —— 返回与 gait 同构的关节字典（Composed Method 顶层）。

    驱动顺序沿用 gait 的物理口径：**脚先锁定，髋由动作曲线给出，膝由 IK 反求**。
    """
    seg, q = _phase_split(p)
    sub, sq = _sub(q)
    e = _ease(sq)

    hip = solve_hip(seg, sub, e)                       # 髋：站位 → 入座 → 保持 → 离座
    out = solve_legs(np.array([hip.u, hip.v]))         # 腿：脚锁定，膝 IK 反求
    out.update(solve_spine(hip, _lag_of(seg, sub, e), seg))   # 脊柱：倾角×力臂 + 滞后
    shoulder_v = hip.v + (PROP["shoulder"] - PROP["hip"])
    out.update(solve_arms(hip, seg, sub, e, shoulder_v, out["chest"][0]))
    return out


# ------------------------------------------------------------------
# 触椅 / 离椅的确切帧（Cursa 第①条：必须能指出来）
# ------------------------------------------------------------------
def contact_frames(fps=24.0):
    """返回 (触椅帧, 离椅帧) —— 坐下动作段结束即触椅，站起段开始即离椅。"""
    total = 56.0 / 24.0 * fps
    return int(round(SIT_F * total)), int(round((SIT_F + HOLD_F) * total))


def com_u(p, **kw):
    """近似 CoM 前后位置：躯干四点平均（含头前伸 —— 坐下时头前伸正是平衡髋后移的关键）。"""
    J = sit_pose(p, **kw)
    return float(np.mean([J[k][0] for k in ("pelvis", "waist", "chest", "head")]))


def support_polygon_u(seg):
    """支撑多边形前后范围：站定=双脚；坐下全过程与坐姿=脚∪椅。"""
    if seg == "hold" or seg == "sit":
        return (CHAIR_U - 0.05, TOE_OFF + TOE_LEN)
    return (-HEEL_LEN, TOE_OFF + TOE_LEN)

__all__ = [n for n in dir() if not n.startswith("__")]
