# 契约: proc/motion/character/leg
#   一句话: 腿：两骨 IK、踝高曲线、脚掌俯仰与脚部关键点
#   完整契约见 motion/character/__init__.py

import math
import numpy as np
from .proportions import *
from .joints import *



def _leg_chain(x0, y0, th_hip, th_knee, L1, L2):
    """一条腿的正向运动学。角度：0=垂直向下，正=向前(+x)"""
    d1 = np.array([np.sin(th_hip), -np.cos(th_hip)])
    knee = np.array([x0, y0]) + L1 * d1
    d2 = np.array([np.sin(th_hip + th_knee), -np.cos(th_hip + th_knee)])
    ank = knee + L2 * d2
    return knee, ank


def two_bone_ik(root, target, L1, L2, bend=(1.0, 0.0)):
    """两骨 IK 解析解（余弦定理）—— 走路脚锁定的核心。

        cosθ = (L1² + d² − L2²) / (2·L1·d)
        knee = hip + d̂·L1·cosθ + b̂·L1·sinθ
        b̂    = normalize(u⃗ − (u⃗·d̂)d̂)          Gram-Schmidt，免 pole vector

    bend 给定期望的弯曲朝向（人膝朝前 = +x）。
    dist 做 soft clamp：上限 L1+L2−ε 防超伸，下限 |L1−L2|+ε 防折叠。
    """
    root = np.asarray(root, float)
    target = np.asarray(target, float)
    v = target - root
    nv = np.linalg.norm(v)
    if nv < 1e-9:
        v = np.array([0.0, -1.0]); nv = 1.0
    dhat = v / nv
    dist = float(np.clip(nv, abs(L1 - L2) + 1e-3, L1 + L2 - 1e-3))

    u = np.asarray(bend, float)
    b = u - np.dot(u, dhat) * dhat
    nb = np.linalg.norm(b)
    if nb < 1e-9:                       # 退化：任取垂直方向
        b = np.array([-dhat[1], dhat[0]])
    else:
        b = b / nb

    ct = (L1 * L1 + dist * dist - L2 * L2) / (2.0 * L1 * dist)
    th = np.arccos(float(np.clip(ct, -1.0, 1.0)))
    return root + dhat * (L1 * np.cos(th)) + b * (L1 * np.sin(th))


# 外踝离地高度实测关键点（%GC → 米）
#   《Dynamics of Human Gait》Fig 2.9，正常男性右外踝 Z 向轨迹：
#     0~40%  脚平放，恒定 0.07
#     40~60% 足跟抬起、蹬地 → 0.18（60% 为 toe-off）
#     70%    摆动峰 0.22
#     80~100% 伸膝准备触地 → 回落 0.07
#   为什么必须用它：Della Croce (2001) 实测 30 人——
#   **heel rise 是削减 COM 垂直位移的主因，占全部削减量的 2/3**；
#   骨盆旋转约 10%、骨盆倾斜仅 2~4mm。
#   早期版本支撑期踝高取常数，等于完全没有 heel rise → COM 起伏是"圆规步态"值（约 2.5 倍）。
def ahead_for_com(leg_reach, ank_h_n, com_drop_n):
    """触地瞬间脚落在重心前方的距离（归一化身高）——由实测 COM 垂直降幅反解。

    不再手填 AHEAD_FRAC，因为固定比例会让大步走产生"圆规步态"级起伏：
        髋高几何:  hip = sqrt(L² − dx²) + ank_h
    实测 COM 垂直峰峰 ≈5 cm（Oklahoma HSC；J.Biomech 23 人实测同为 ~5 cm），
    故谷值 hip_low = hip_stand − com_drop，反解
        dx = sqrt(L² − (hip_low − ank_h)²)
    步长变化时 dx 自动重算，COM 起伏恒等于实测值——与"垂直位移对步长不敏感"一致。
    """
    # 站立(dx=0) 髋最高 = L + ank_h；触地分腿时髋最低 = sqrt(L²−dx²) + ank_h
    # 令 最低 = 最高 − com_drop  →  sqrt(L²−dx²) = L − com_drop
    L = float(leg_reach)
    d = float(com_drop_n)
    inner = L * L - (L - d) ** 2
    return math.sqrt(max(0.0, inner))


ANKLE_H_KEYS = [(0.0, 0.07), (0.40, 0.07), (0.60, 0.18),
                (0.70, 0.22), (0.80, 0.12), (1.00, 0.07)]


def ankle_h_curve(phs):
    """外踝离地高度（归一化身高）。直接插值实测表，不手填系数。"""
    ks = ANKLE_H_KEYS
    phs = float(phs) % 1.0
    for i in range(len(ks) - 1):
        a, va = ks[i]
        b, vb = ks[i + 1]
        if a <= phs <= b:
            t = 0.0 if b == a else (phs - a) / (b - a)
            t = t * t * (3.0 - 2.0 * t)      # smoothstep
            return (va + (vb - va) * t) / _H_REF
    return ks[-1][1] / _H_REF


def foot_local(phs, stride=0.828, stance=0.62, lift=0.10, ank_h=0.040,
               step_len=0.414):
    """脚踝相对身体中心的位置。phs=0 为刚着地。

    支撑相：脚在**世界**里静止 → 相对身体严格匀速后退（线性！这是不滑的关键）
    摆动相：从后向前 smoothstep 推进。
    高度：一律走 ankle_h_curve（实测表），支撑期含 heel rise、摆动期含抬腿。
    边界连续：phs=stance⁻ 与 u=0 同为 −0.5·stance·stride；phs→1 回到 +ahead。
    """
    # 脚在支撑期相对重心前后**不对称**（这是早期版本 COM 起伏 2.5 倍的第二个病根）：
    #   触地(foot ahead) 脚在重心前 0.40×步长
    #   离地(foot behind) 脚在重心后 = stance×stride − ahead
    # 对称假设(±0.5·stance·stride)会把触地点推到重心前 0.44 m，
    # 几何上强迫重心掉到 0.446H，峰峰 12 cm —— 正是"圆规步态"的预测值；
    # 真实脚前后分布不对称，重心只需降 3 cm。
    span = PROP["thigh"] + PROP["shank"]
    ahead = ahead_for_com(span * STRAIGHT, ankle_h_curve(0.0), COM_AMP_N)   # 实测 COM 降幅反解，非手填
    if phs < stance:
        x = ahead - stride * phs        # ← 线性，业界要求重心/脚位移必须 Linear
    else:
        u = (phs - stance) / (1.0 - stance)
        s = u * u * (3.0 - 2.0 * u)     # smoothstep
        x = ahead + stride * s - stride * phs
    y = ankle_h_curve(phs)
    return x, y


# 脚掌**绝对**俯仰角（foot-to-floor angle，相对地面；正=脚尖朝上/背屈）
# 出处：Perry 1992 触地足-地面角 25°；Vette 等 15-20°，临床达标区间 10-25°；
#       Winter 1995 摆动期踝背屈回中立 0° 以清地；AFO 对齐指南 mid-swing 保 1-2cm 趾间隙。
# 旧实现病根：phs>0.446 走 `-0.55*u²`，而 u=(phs-0.446)/0.174 在 toe off(0.62) 之后
#   没有上界 → phs=0.95 时 pitch 外推到 -265°，脚翻转近一整圈再瞬间弹回 +26°
#   （即用户看到的「脚走到后尾朝后、然后又旋转过来」）。
# 新实现：整周期查表插值，表覆盖 0~1 且首尾闭合，并有生理护栏，绝不外推。
FOOT_PITCH_KEYS = [
    (0.00,  20.0),   # 脚跟着地：跟先触地，脚尖翘起
    (0.12,   0.0),   # foot flat：全脚掌落地
    (0.45,   0.0),   # 支撑中期：脚平放不动
    (0.55, -12.0),   # heel off：绕前掌向前转
    (0.60, -28.0),   # toe off：脚跟最高，脚尖朝下蹬地
    (0.70,  -8.0),   # 蹬离后快速回升
    (0.78,   0.0),   # 摆动中期：踝回中立，脚基本水平（清地）
    (0.90,  14.0),   # 摆动末期：摆到脚跟着地角
    (1.00,  20.0),   # 闭合回触地
]
_FP_PH = np.array([k[0] for k in FOOT_PITCH_KEYS])
_FP_DEG = np.array([k[1] for k in FOOT_PITCH_KEYS])
FP_LO, FP_HI = -35.0, 30.0     # 生理区间；越界即说明脚要翻转，护栏强制夹回


def foot_pitch(phs, stance=0.62):
    """脚掌绝对俯仰角（rad，正=脚尖朝上）。查表+线性插值，首尾闭合，绝不外推。"""
    p = float(phs) % 1.0
    deg = float(np.interp(p, _FP_PH, _FP_DEG))
    return math.radians(float(np.clip(deg, FP_LO, FP_HI)))

__all__ = [n for n in dir() if not n.startswith("__")]
