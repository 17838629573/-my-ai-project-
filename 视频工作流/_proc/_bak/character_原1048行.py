# 契约: proc/motion/character
#   一句话: 【超标·冻结封存·待下沉】旧人物渲染，依赖相机与背景，故归 motion 层
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""character —— 人物包（L-C 每帧全算层）

核心决策：**用 SDF 场构造形体，不做部件拼接。**

这与本项目早期"拆 10 块再拼"彻底分道：
    部件拼接   每块独立 → 要锚点、要旋转、要绘制顺序覆盖 → 关节必错位
    SDF        同一标量场做平滑并集 → 无锚点、无缝、关节自动过渡

SDF 一次性给出四样东西（Lumo 要反推，我们是正算）：
    轮廓   d = 0 的等值线
    法线   n = normalize(∇d)
    深度   d 本身（越负越"深"）
    混合   smin() 平滑并集 —— 关节处自动圆滑

立体感用 **inflate 模型**（比 Lumo 强的地方）：
    Lumo 要从轮廓反推法线（不适定，需求解拉普拉斯方程）
    我们已知 SDF，可直接构造伪 3D 法线：
        t   = clamp(-d / d_max)          归一化内距
        nz  = sqrt(1 - (1-t)^2)          边缘 0，中心 1
    一个圆会被着色成一个球 —— 正是 Lumo 的效果，但无需迭代求解
"""

import math
import numpy as np
from PIL import Image, ImageDraw
from motion import camera

# ================================================================
# 一、SDF 原语（形状层）
# ================================================================

def sd_capsule(px, py, ax, ay, bx, by, r):
    """胶囊 SDF。px,py 可以是数组。负=内部"""
    pax, pay = px - ax, py - ay
    bax, bay = bx - ax, by - ay
    bb = bax * bax + bay * bay
    h = np.clip((pax * bax + pay * bay) / max(bb, 1e-9), 0.0, 1.0)
    dx, dy = pax - bax * h, pay - bay * h
    return np.sqrt(dx * dx + dy * dy) - r


def sd_circle(px, py, cx, cy, r):
    dx, dy = px - cx, py - cy
    return np.sqrt(dx * dx + dy * dy) - r


def sd_ellipse(px, py, cx, cy, rx, ry):
    """近似椭圆 SDF（精确解要解五次方程，此处用缩放近似，够用）"""
    dx, dy = (px - cx) / max(rx, 1e-9), (py - cy) / max(ry, 1e-9)
    k = np.sqrt(dx * dx + dy * dy)
    return (k - 1.0) * min(rx, ry)


def smin(a, b, k=0.0):
    """多项式平滑并集（polynomial smooth min）

    k=0 退化为普通 min（硬边，会有折角）
    k>0 在两形状交界处生成圆滑过渡 —— 这就是"关节"的来源
    """
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


# ================================================================
# 二、骨架与步态（运动层）
# ================================================================

# ------------------------------------------------------------------
# 人体比例：Drillis & Contini (1966)，Winter (1990) 转引
#   段长直接给成身高 H 的分数，是学界沿用半个世纪的"比例常数"表。
#   单位一律归一化身高：y=0 脚底，y=1 头顶。
# ------------------------------------------------------------------
_DC = {                      # Drillis & Contini 1966 实测段长/身高
    "foot_h":   0.039,       # 足高
    "foot_len": 0.152,       # 足长
    "shank":    0.246,       # 小腿
    "thigh":    0.245,       # 大腿
    "trunk":    0.288,       # 躯干
    "upperarm": 0.186,       # 上臂
    "forearm":  0.146,       # 前臂
    "hand":     0.108,
    "neck":     0.052,
    "head":     0.130,       # 头高（非半径）
    "shoulder_h": 0.818,     # 肩高（站立）
    "elbow_h":  0.630,       # 肘高（站立）
    "knee_h":   0.285,       # 膝高
    "hip_h":    0.520,       # 髋高（大转子）
    "eye_h":    0.936,
    "sitting_h": 0.520,
}

PROP = {
    # —— 直接取自 D&C 表 ——
    "thigh":   _DC["thigh"],        # 0.245
    "shank":   _DC["shank"],        # 0.246
    "upperarm": _DC["upperarm"],    # 0.186
    "forearm": _DC["forearm"],      # 0.146
    "head_r":  _DC["head"] * 0.5,   # 0.065（头高→半径）
    "ankle":   _DC["foot_h"],       # 0.039 踝离地＝足高
    "hip":     _DC["hip_h"],        # 0.520
    "knee":    _DC["knee_h"],       # 0.285
    # —— 由表推导，不手填 ——
    # 肩高 0.818 是"肩点离地"；胸取肩与髋之间按躯干比例插值
    "shoulder": _DC["shoulder_h"],                       # 0.818
    "chest":    _DC["hip_h"] + 0.68 * _DC["trunk"],      # 0.716
    "waist":    _DC["hip_h"] + 0.14 * _DC["trunk"],      # 0.560
    "neck":     _DC["hip_h"] + _DC["trunk"],             # 0.808
}

# ------------------------------------------------------------------
# 步态时间与幅度：不再手填系数，改由文献公式/实测关键点驱动
# ------------------------------------------------------------------
STEP_RATIO   = 0.414   # 步长/身高（biomechanics 通用值，男 .415 女 .413，±3cm）
CADENCE_SPM  = 110.0   # 正常步频 步/分（成人自然行走 100~120）
STANCE_FRAC  = 0.62    # 支撑相占比（成人平地常速 = 62% GC）
TOE_CLEAR    = 0.013   # 摆动中期足趾离地间隙 ≈1.3cm → /H = 0.0076

# 关节角实测关键点（%GC → 角度°，矢状面，屈为正）
#  髋: 触地 25-30°屈 → 50%GC 10°伸 → 摆动 25°屈
#  膝: 触地 0-5° → 10%GC 15°屈 → 摆动峰 60°(实测 50.34°±2.23 @75.8%GC)
#  踝: 触地 0° → 44%GC 背屈 5.57° → 68.5%GC 跖屈 15.51°
GAIT_KEYS = {
    "hip":   [(0.0, 27.5), (0.30, 0.0), (0.50, -10.0), (0.75, 15.0), (1.0, 27.5)],
    "knee":  [(0.0, 5.0), (0.104, 15.0), (0.40, 0.0), (0.758, 50.34), (1.0, 5.0)],
    "ankle": [(0.0, 0.0), (0.44, 5.57), (0.60, -10.0), (0.685, -15.51), (1.0, 0.0)],
}


def joint_angle(joint, ph):
    """实测关节角关键点 → 线性插值出任意相位的角度（弧度）。

    以前 GAIT_PRESETS 里的 hip_swing/knee_bend 是我拍的系数，
    现在换成文献实测表插值，改风格只需换表不必重调系数。
    """
    ks = GAIT_KEYS[joint]
    ph = float(ph) % 1.0
    for i in range(len(ks) - 1):
        a, va = ks[i]
        b, vb = ks[i + 1]
        if a <= ph <= b:
            t = 0.0 if b == a else (ph - a) / (b - a)
            t = t * t * (3.0 - 2.0 * t)          # smoothstep，避免折角
            return math.radians(va + (vb - va) * t)
    return math.radians(ks[-1][1])


# ------------------------------------------------------------------
# 重心位移与骨盆运动：Saunders / Inman / Eberhart (1953) 六决定因素
# 与 Oklahoma HSC《Kinematics of human gait》实测值（工具优先：全部取自文献）
#
#   垂直位移   ~5 cm，每周期 2 次（双支撑期最低，midstance/midswing 最高）
#   侧向位移   骨盆左右各 2.5 cm → 峰峰 ~5 cm，每周期 1 次（midstance 末最大）
#   骨盆旋转   4°/侧（横断面，摆动侧向前）—— 减少垂直位移 9.5 mm
#   骨盆倾斜   5°（冠状面，摆动侧下降）—— 减少垂直位移 ~3 mm
#
# 【关键】侧向位移必须落在 w（左右）轴上。早期版本把它加进了 u（前后）轴，
# 于是前进方向叠了个正弦 → 人一冲一冲、看着重心不稳。前后方向本就该匀速。
# ------------------------------------------------------------------
_H_REF = 1.70            # 归一化身高基准（m）
STRAIGHT = 0.975
# 可达性反解还要预留的额外余量（归一化）。来源：摆动腿抬升 + 骨盆旋转/倾斜
# 联合偏移，解析式耦合，改由参数扫描实测确定：+0.020 时小腿误差从 1.2e-02
# 掉到 1.9e-16 且髋踝距(0.486)回到腿长(0.491)以内。
LIFT_ROOM = 0.020         # 腿常备微屈：髋到踝 = (thigh+shank)×straight，永不锁死
COM_VERT_CM   = 5.0      # 垂直位移峰峰（cm），每周期 2 次
COM_AMP_N     = (COM_VERT_CM / 2.0) / 100.0 / _H_REF   # 余弦幅度（归一化身高）
PELVIS_LAT_CM = 2.5      # 骨盆侧向位移（cm/侧），每周期 1 次
PELVIS_ROT_DEG = 4.0     # 骨盆旋转（横断面，度）
PELVIS_LIST_DEG = 5.0    # 骨盆倾斜（冠状面，度）

# ---- 上身在矢状/横断面的真实幅度（工具优先：全部取自文献实测）----
# 早期版本把「胸椎扭转角」当成位移直接加到 chest 的 u 上：
#   twist = -0.30 × hip_swing(0.48 rad) = 0.144 归一化 = 24.5 cm/侧
# 于是躯干前后摆 49 cm、头 62 cm（身高才 170 cm）—— 这就是"左右摇摆、重心不稳"。
# 角度≠位移：扭转是绕竖直轴转，躯干中心线在轴上，位移≈0；
# 真正产生位移的是偏离轴的点（肩，半径 = 肩半宽 SH_W）。
THORAX_ROT_DEG  = 7.0    # 胸-骨盆横断面扭转 ROM/侧（正常速，健康人）
TRUNK_PITCH_DEG = 3.35   # 躯干前后倾半幅 = SwayStar 实测 pitch 6.7°±2.2° 的一半
SHOULDER_AP_CM  = 4.0    # 肩前后摆幅校验目标（自然行走 3~5 cm）


def _cm_to_norm(cm):
    """cm（真实人体量）→ 归一化身高单位。"""
    return (cm / 100.0) / _H_REF


# 三种走路预设：幅度倍率 + 步频，绝对量全部来自上面那张表
GAIT_PRESETS = {
    "natural": dict(cadence=CADENCE_SPM,      amp=1.00, lean_deg=TRUNK_PITCH_DEG, style="walk"),
    "stroll":  dict(cadence=85.0,             amp=0.80, lean_deg=2.5, style="walk"),
    "march":   dict(cadence=120.0,            amp=1.35, lean_deg=-TRUNK_PITCH_DEG, style="march"),
    "brisk":   dict(cadence=130.0,            amp=1.20, lean_deg=5.0, style="walk"),
}
# 兼容旧调用：步长/支撑等标量参数
# 脚相对髋的水平跨度 = 一个「步」= STEP_RATIO（0.414 归一化）。
# 早期写成 2×STEP_RATIO（0.828，那是一个周期两走步的行程）→ 脚跨度大一倍，
# 髋踝距 0.5745 远超腿长 0.4910，IK 只能 clamp 截断，小腿被硬拉长 8.4cm
# （表现为膝盖不会弯、人一冲一冲）。
# foot_local 里支撑相推进量 = stride × stance，而这必须等于「一个步长」(STEP_RATIO)，
# 所以 stride 本身要除以支撑占比：0.414/0.62 = 0.668（归一化/周期）。
# 直接拿 STEP_RATIO 当 stride 会让脚只走 62% 步长（实测两脚前后差 35cm，
# 真实应为步长 70.4cm）；同理拿 2×STEP_RATIO 会让髋踝距超腿长、IK 截断。
STRIDE_N   = 0.66   # 扫描上限：>0.66 髋踝距超腿长，IK 只能拉长小腿
LIFT_N     = 0.055                 # 摆动期踝抬升（归一化），足趾间隙 ≈1.3cm


def gait_params(preset="natural", body_h=1.70):
    """由文献公式推出该预设的全部时间/幅度量。

    步长 = 0.414 × 身高（独立公式，与骨架解算出的步长互为校验）
    速度 = 步长 × 步频/60
    周期 = 2 × 步长 / 速度
    """
    P = GAIT_PRESETS[preset]
    step_m = STEP_RATIO * body_h * P["amp"]      # 一步米数
    spm = P["cadence"]
    speed = step_m * spm / 60.0                  # m/s
    dur = 60.0 / spm * 2.0                       # 一个步态周期（两步）秒数
    return dict(step_m=step_m, speed=speed, dur=dur, cadence=spm,
                stance=STANCE_FRAC, stride=STRIDE_N * P["amp"],
                lift=LIFT_N * P["amp"], lean_deg=P["lean_deg"],
                thorax_rom=math.radians(THORAX_ROT_DEG) * P["amp"],
                hip_swing=math.radians(27.5) * P["amp"],
                arm_swing=math.radians(24.0) * P["amp"],
                hip_sway=_cm_to_norm(PELVIS_LAT_CM) * P["amp"],   # 侧向，不再用于前后
                lateral=_cm_to_norm(PELVIS_LAT_CM) * P["amp"],
                knee_bend=0.0)

# 骨架输出顺序 = 绘制无关，仅用于取关节
JOINTS = ["pelvis", "waist", "chest", "neck", "head",
          "sh_l", "sh_r", "elb_l", "elb_r", "wri_l", "wri_r",
          "hip_l", "hip_r", "knee_l", "knee_r", "ank_l", "ank_r"]

# 侧向宽度（归一化身高）。这是"只能画侧面"的病根所在：
# 2D 时代没有 w 这一维，髋/肩的左右宽度只能塞进 u（前后）里假装，
# 于是人永远只能侧着站——一旦想让他沿路走远（背视），就无处安放。
# 3D 后 u/v/w 各归各位，同一套 gait() 可以投成任意朝向。
LAT = {"hip": 0.055, "knee": 0.055, "ank": 0.055}   # 同侧三关节同宽 → 腿在矢状面内，骨长精确守恒
SH_W = 0.115          # 肩半宽
SOLE_LIFT = 0.024     # 脚底胶囊最低点（ank 下方 r）抬到 v=0 → 脚真正踩在地面
TOE_LEN = 0.075       # 踝 → 脚尖
HEEL_LEN = 0.038      # 踝 → 脚跟（踝约在脚长后 25% 处，Drillis & Contini 1966）


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


def _arm_chain(x0, y0, th_sh, th_elb, L1, L2):
    """一条手臂。0=垂直向下，正=向前"""
    d1 = np.array([np.sin(th_sh), -np.cos(th_sh)])
    elb = np.array([x0, y0]) + L1 * d1
    d2 = np.array([np.sin(th_sh + th_elb), -np.cos(th_sh + th_elb)])
    wri = elb + L2 * d2
    return elb, wri


def _cyc(a, b):
    """相位循环距离 ∈ [-0.5, 0.5)

    直接用 (a-b)%1.0 在 a<b 时会从 0.999 突跳到 0.001，
    高斯值瞬间从 0 跳到 1 → 膝盖每周期弹一下。
    """
    return (a - b + 0.5) % 1.0 - 0.5


def _knee_curve(ph, amp):
    """膝关节角曲线：两个高斯峰
       峰1 loading response（φ≈0.10，微屈，人体吸震）
       峰2 swing（φ≈0.75，深屈，避免脚尖拖地）
    """
    a = np.exp(-(_cyc(ph, 0.75) / 0.18) ** 2) * 0.85
    b = np.exp(-(_cyc(ph, 0.10) / 0.07) ** 2) * 0.28
    return -amp * (a + b)


def gait(ph, preset="natural", scale_h=1.0, stride=None, stance=STANCE_FRAC):
    """步态求解：相位 ph∈[0,1) → 每个关节的 **(u, v, w)**（归一化身高单位）

        u = 身体前向（人朝哪走就往哪）
        v = 离地高度
        w = 身体侧向（左为正）

    三轴分开是"能沿路走远"的前提：2D 时代只有 (u,v)，左右宽度无处安放，
    人只能永远侧站；3D 后同一个解可以投成侧视 / 背视 / 正视 / 任意角度。

    动力学链（业界 walk cycle 标准顺序）：
        髋摆 → 脊柱反向旋转 → 胸 → 肩（反相于髋）→ 头（滞后）→ 臂 → 腿 → 脚
    """
    P = gait_params(preset)
    two = 2.0 * np.pi * ph
    L1, L2 = PROP["thigh"], PROP["shank"]
    span = L1 + L2
    if stride is None:
        stride = P["stride"]

    # ---- 根：重心起伏 = 两腿几何的后果（不再外加 bob，也不会让腿够不到脚）
    # 先定位双脚（脚锁定，不依赖 hip 高度），再由腿长反推 hip 高度：
    #   hip_y = ankle_y + sqrt((span·straight)² − dx²)
    # 双腿最开时(φ=0/0.5) hip 最低，单脚支撑时(φ=0.25/0.75) hip 最高 —— CoM 起伏自然涌现
    straight = 0.975                      # 腿常备微屈，永不锁死
    # 前后轴：重心匀速前进，不叠正弦（业界明确要求脚位移 Linear）
    u_root = 0.0
    # 左右轴：Saunders 第 5 决定因素，每周期 1 次（原错加在 u 上，已修正）
    w_root = P["lateral"] * math.sin(two)
    lift = P["lift"]
    foots = {}
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        phs = (ph + (0.0 if sgn > 0 else 0.5)) % 1.0
        foots[side] = (phs, np.array(foot_local(phs, stride, stance, lift)))
    # 髋能抬多高，取决于「最难够到的那只脚」——取全体上限的最小值，
    # 保证两条腿（支撑腿 + 摆动腿）都在腿长范围内，IK 永不被截断
    # 髋会被骨盆旋转/倾斜推离中线（hip_u/hip_v 各偏 LAT["hip"]·sin(θ)），
    # 反解可达高度时必须把这截余量预留出来，否则摆动腿髋踝距略超 reach，
    # two_bone_ik 的 soft clamp 会把小腿拉长（实测曾达 14cm）。
    _lat_room = (LAT["hip"] * (math.sin(math.radians(PELVIS_ROT_DEG))
                               + math.sin(math.radians(PELVIS_LIST_DEG)))
                 + LIFT_ROOM)
    reach = span * straight - _lat_room
    # 垂直：直接取实测 COM 曲线（业界顺序：COM 是先验，腿去适配，不是几何反推）
    #   y = y0 − A·cos(4πφ)  每周期 2 次；最低 5%/55%(双腿支撑) 最高 30%/80%(单腿支撑)
    #   峰峰 5 cm（Oklahoma HSC / J.Biomech 23人实测）。步长变化不改写曲线——
    #   差值交给膝盖屈曲吸收，这才是"垂直位移对步长不敏感"的物理来源。
    y_stand = PROP["ankle"] + reach
    y_root = y_stand - COM_AMP_N * math.cos(2.0 * two)
    dy = y_root - (PROP["ankle"] + reach)   # 躯干整体随之起伏（腿伸直时 dy=0）

    # ---- 腿：脚世界锁定 + 两骨 IK 反求膝盖（消除打滑）
    # 侧向宽度 LAT 现在走 w 轴（不再塞进 u），u/v 保持纯矢状面
    out = {}
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        phs, ank = foots[side]
        # ---- 骨盆旋转 4° / 倾斜 5°（Saunders 决定因素 1、2）----
        # 旋转：绕竖直轴，髋点 (0, w) → u 分出前后，两侧反相
        # 倾斜：冠状面，摆动侧下降；两侧反相
        two_s = 2.0 * np.pi * phs
        rot_s = math.radians(PELVIS_ROT_DEG) * math.cos(two_s)
        list_s = math.radians(PELVIS_LIST_DEG) * math.cos(two_s)
        hip_u = u_root + (LAT["hip"] * sgn) * math.sin(rot_s)
        hip_w = w_root + (LAT["hip"] * sgn) * math.cos(rot_s)
        hip_v = y_root - LAT["hip"] * math.sin(list_s) * sgn

        hip_uv = np.array([hip_u, hip_v])
        knee_uv = two_bone_ik(hip_uv, ank, L1, L2, bend=(1.0, 0.0))   # 膝朝前
        pit = foot_pitch(phs, stance)                                  # 脚掌滚动
        out["hip_" + side] = np.array([hip_u, hip_v, hip_w])
        out["knee_" + side] = np.array([knee_uv[0], knee_uv[1], LAT["knee"] * sgn + w_root])
        out["ank_" + side] = np.array([ank[0], ank[1], LAT["ank"] * sgn + w_root])
        # 旧写法 `max(0.0, sin(pit))` 把负 pitch 全压成 0 → 蹬地时脚尖永远压不下去，
        # 摆动时脚尖还被钉在踝的高度，配合 pitch 外推就成了「脚翻转」的观感。
        # 脚掌应整体绕踝转：脚尖在前 (cos,sin)，脚跟在后 (-cos,-sin)。
        out["toe_" + side] = np.array([ank[0] + TOE_LEN * np.cos(pit),
                                       ank[1] + TOE_LEN * np.sin(pit),
                                       LAT["ank"] * sgn + w_root])
        out["heel_" + side] = np.array([ank[0] - HEEL_LEN * np.cos(pit),
                                        ank[1] - HEEL_LEN * np.sin(pit),
                                        LAT["ank"] * sgn + w_root])

    # ---- 脊柱：S 曲线 + 反向旋转（髋摆 → 胸反相）
    # 扭转是「角度」，不是位移。躯干中心线在旋转轴上 → 位移≈0；
    # 真正位移的是偏离轴的点（肩，半径=SH_W）。肩前后摆幅由此自然落在文献 3~5 cm。
    twist = -P["thorax_rom"] * np.cos(two)               # 胸-骨盆扭转角（rad），反相于髋
    lean_ang = math.radians(P["lean_deg"]) * np.sin(two)  # 躯干前后倾角（rad）
    # 倾角 × 髋→颈的力臂 = 颈/头的前后位移（SwayStar pitch 6.7°±2.2° 的半幅）
    lean_d = (PROP["neck"] - PROP["hip"]) * math.sin(lean_ang)

    def S(u, v, w=0.0):
        return np.array([u, v, w], dtype=np.float64)

    out["pelvis"] = S(u_root, y_root, w_root)
    out["waist"] = S(u_root + 0.10 * lean_d, y_root + PROP["waist"] - PROP["hip"], w_root * 0.55)
    out["chest"] = S(u_root + 0.55 * lean_d, PROP["chest"] + dy, w_root * 0.30)
    out["neck"] = S(u_root + 0.80 * lean_d, PROP["neck"] + dy, w_root * 0.18)
    # 头滞后一拍（follow through 的雏形）
    out["head"] = S(u_root + 1.00 * lean_d,
                    PROP["neck"] + dy + PROP["head_r"] * 0.95, w_root * 0.14)

    # ---- 臂：肩反相于同侧髋
    # 胸椎扭转是**绕竖直轴的转角**（不是位移）：肩点沿该角在 (u,w) 平面上转，
    # 于是背视时两肩一前一后、侧视时两肩一左一右 —— 朝向自然就对了。
    AU, AF = PROP["upperarm"], PROP["forearm"]
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        phs = (ph + (0.0 if sgn > 0 else 0.5)) % 1.0
        two_s = 2.0 * np.pi * phs
        th_sh = -P["arm_swing"] * np.cos(two_s)          # 反相
        th_elb = -0.25 - 0.22 * max(0.0, np.cos(two_s))  # 前摆时屈肘多
        su = out["chest"][0] + sgn * SH_W * np.sin(twist)
        sw = out["chest"][2] + sgn * SH_W * np.cos(twist)
        sv = PROP["shoulder"]
        elb, wri = _arm_chain(su, sv, th_sh, th_elb, AU, AF)
        out["sh_" + side] = S(su, sv, sw)
        out["elb_" + side] = S(elb[0], elb[1], sw)
        out["wri_" + side] = S(wri[0], wri[1], sw)

    if scale_h != 1.0:
        out = {k: np.asarray(v) * scale_h for k, v in out.items()}
    return out


# ================================================================
# 三、形体场（SDF 装配）
# ================================================================

# 每个部件：胶囊端点取自关节名（或固定偏移）+ 半径
# 半径按归一化身高给；r_scale 可整体调胖瘦
BODY_SPEC = [
    # (a, b, r)   a/b 是关节名，或 ("@", dx, dy) 表示相对某关节偏移
    ("hip_l", "knee_l", 0.052), ("knee_l", "ank_l", 0.042),
    ("hip_r", "knee_r", 0.052), ("knee_r", "ank_r", 0.042),
    ("pelvis", "waist", 0.082), ("waist", "chest", 0.088),
    ("chest", "neck", 0.070),
    ("sh_l", "elb_l", 0.034), ("elb_l", "wri_l", 0.029),
    ("sh_r", "elb_r", 0.034), ("elb_r", "wri_r", 0.029),
]


def project_body(J, cam, Xc=0.0, Zc=10.0, yaw=90.0, body_h=1.70):
    """归一化 (u,v,w) 关节 → 屏幕像素。

    关节先在身体局部绕竖直轴转 yaw，再平移到世界 (Xc,Zc)，最后交给相机投影。
        yaw =   0°  背对镜头（朝画面深处走远）  ← 沿路走远用这个
        yaw =  90°  纯侧视（人物表 / 横向走过）
        yaw = 180°  正对镜头走来
    返回 {name: (sx, sy, s)}，s 是该点的 **像素/米**（半径缩放要用）。
    """
    th = math.radians(yaw)
    st, ct = math.sin(th), math.cos(th)
    out = {}
    for k, j in J.items():
        u, v, w = float(j[0]), float(j[1]), float(j[2] if len(j) > 2 else 0.0)
        U = u * body_h                 # 前向 → 米
        V = (v + SOLE_LIFT) * body_h   # 离地高度 → 米（脚底对齐地面）
        Wd = w * body_h                # 侧向 → 米
        X = Xc + U * st + Wd * ct
        Z = Zc + U * ct - Wd * st
        sx, sy, s = cam.proj(X, Z, V)
        out[k] = (float(sx), float(sy), float(s))
    return out


def body_geometry(Jp, body_h=1.70):
    """屏幕关节 → 胶囊表（像素）。半径按各自深度的 像素/米 缩放。"""
    caps = []
    for a, b, r in BODY_SPEC:
        ax, ay, sa = Jp[a]
        bx, by, sb = Jp[b]
        caps.append((float(ax), float(ay), float(bx), float(by),
                     max(r * body_h * 0.5 * (sa + sb), 0.8)))
    hx, hy, hs = Jp["head"]
    ell = [(float(hx), float(hy),
            max(PROP["head_r"] * 0.86 * body_h * hs, 1.0),
            max(PROP["head_r"] * 1.12 * body_h * hs, 1.0))]
    for side in ("l", "r"):
        ax, ay, as_ = Jp["ank_" + side]
        tx, ty, ts = Jp["toe_" + side]
        caps.append((float(ax), float(ay), float(tx), float(ty),
                     max(0.024 * body_h * 0.5 * (as_ + ts), 0.8)))
    sm = max(0.030 * body_h * max(s for _, _, s in Jp.values()), 0.5)
    return caps, ell, sm


def field_px(caps, ell, smooth, pad=6.0):
    """在**屏幕像素网格**上建 SDF。返回 (d, (x0, y0), d_head)。

    头单独存一份 d_head，用来做肤色蒙版（不再按"上 1/5 切一条线"瞎切）。
    """
    xs, ys, rs = [], [], []
    for ax, ay, bx, by, r in caps:
        xs += [ax, bx]; ys += [ay, by]; rs.append(r)
    for cx, cy, rx, ry in ell:
        xs += [cx - rx, cx + rx]; ys += [cy - ry, cy + ry]; rs.append(max(rx, ry))
    m = 2.0 * max(rs) + pad
    x0 = float(int(min(xs) - m)); y0 = float(int(min(ys) - m))
    W = max(8, int(max(xs) + m - x0)); H = max(8, int(max(ys) + m - y0))
    gx = np.arange(W, dtype=np.float32) + x0
    gy = np.arange(H, dtype=np.float32) + y0
    PX, PY = np.meshgrid(gx, gy)
    d = np.full((H, W), 1e6, np.float32)
    for ax, ay, bx, by, r in caps:
        d = smin(d, sd_capsule(PX, PY, ax, ay, bx, by, r), k=smooth)
    dh = None
    for cx, cy, rx, ry in ell:
        e = sd_ellipse(PX, PY, cx, cy, rx, ry)
        dh = e if dh is None else np.minimum(dh, e)
        d = smin(d, e, k=smooth)
    if dh is None:
        dh = np.full((H, W), 1e6, np.float32)
    return d, (x0, y0), dh


def draw_body(cv, cam, J, Xc=0.0, Zc=10.0, yaw=90.0, body_h=1.70,
              robe=(128, 74, 52), skin=(214, 176, 148),
              chains=None, wind=(0.0, 0.0), dt=1 / 60.0, attach=None,
              hem_scale=None):
    """统一渲染入口：任何相机 / 任何朝向 / 任何深度都用这一条。"""
    if isinstance(J, dict):
        pass
    Jp = project_body(J, cam, Xc=Xc, Zc=Zc, yaw=yaw, body_h=body_h)
    caps, ell, sm = body_geometry(Jp, body_h)
    d, (ox, oy), dh = field_px(caps, ell, sm)

    col = shade_sdf(d, robe)
    hm = dh < 0.0
    if np.any(hm):
        sk = shade_sdf(np.where(hm, dh, 1e6), skin)
        col = np.where(hm[..., None], sk, col)
    a = np.asarray(cv.img, dtype=np.float32)
    hh, ww = d.shape
    px, py = int(round(ox)), int(round(oy))
    x0, y0 = max(0, px), max(0, py)
    x1, y1 = min(cv.w, px + ww), min(cv.h, py + hh)
    if x1 > x0 and y1 > y0:
        sub_a = (d < 0)[y0 - py:y1 - py, x0 - px:x1 - px].astype(np.float32)
        sub_c = col[y0 - py:y1 - py, x0 - px:x1 - px]
        al = sub_a[:, :, None]
        a[y0:y1, x0:x1] = a[y0:y1, x0:x1] * (1 - al) + sub_c * al
        from PIL import Image as _I
        cv.img = _I.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        cv.d = ImageDraw.Draw(cv.img)

    # 锚点（供 Verlet 链）：按投影后的躯干真实位置，不再按"贴图的几分之几"
    _att = attach if attach is not None else {}
    cxm = float(np.mean([Jp[k][0] for k in ("pelvis", "waist", "chest", "neck")]))
    _att["chest"] = (Jp["chest"][0], Jp["chest"][1])
    _att["waist"] = (Jp["waist"][0], Jp["waist"][1])
    _att["head"] = (Jp["head"][0], Jp["head"][1])
    _att["cx"] = cxm
    _att["s"] = float(Jp["pelvis"][2])          # 像素/米，给链子定粗细
    _att["hp"] = body_h * _att["s"]             # 身高像素，布料宽度按它缩放

    if chains:
        for name, key in (("hem", "waist"), ("sash", "chest")):
            if name in chains:
                chains[name].step(dt=dt, wind=wind, anchor=_att[key])
        wpx = max(2, int((hem_scale or 0.020) * body_h * _att["s"]))
        if wpx >= 2:
            _draw_chains(cv, chains, robe, wpx, height_px=_att.get("hp"))
    return Jp


# ================================================================
# 四、着色（inflate 伪 3D 法线）
# ================================================================

def shade_sdf(d, base_rgb, light=(-0.55, -0.62, 0.56), amb=0.42,
              rim_pow=2.6, rim_amt=0.34, d_max=None):
    """由 SDF 直接算伪 3D 法线并着色。

    边缘 nz=0（垂直视线，与 Lumo 的轮廓边界条件一致）
    中心 nz=1（朝向观察者）
    → 一个圆被着色成一个球
    """
    inside = d < 0.0
    if not inside.any():
        return np.zeros((*d.shape, 3), dtype=np.float32)

    if d_max is None:
        d_max = max(-d[inside].min(), 1e-6)
    t = np.clip(-d / d_max, 0.0, 1.0)           # 归一化内距

    # 2D 梯度（中心差分）
    gy, gx = np.gradient(d)
    gl = np.sqrt(gx * gx + gy * gy) + 1e-9
    nx, ny = gx / gl, gy / gl                    # 指向外

    nz = np.sqrt(np.clip(1.0 - (1.0 - t) ** 2, 0.0, 1.0))
    k = np.sqrt(np.clip(1.0 - nz * nz, 0.0, 1.0))
    Nx, Ny, Nz = nx * k, ny * k, nz

    L = np.array(light, dtype=np.float32)
    L = L / (np.linalg.norm(L) + 1e-9)
    lam = np.clip(Nx * L[0] + Ny * L[1] + Nz * L[2], 0.0, 1.0)

    rim = np.clip(1.0 - nz, 0.0, 1.0) ** rim_pow

    base = np.asarray(base_rgb, dtype=np.float32)[None, None, :]
    col = base * (amb + (1.0 - amb) * lam[:, :, None])
    col = col + rim[:, :, None] * rim_amt * 255.0
    col[~inside] = 0.0
    return np.clip(col, 0, 255)


# ================================================================
# 五、次级运动（Verlet 链）—— 衣摆 / 飘带 / 头发
# ================================================================

class VerletChain:
    """Verlet 质点链 + 距离约束松弛

        p_{n+1} = 2 p_n - p_{n-1} + dt^2 * a
        约束松弛: delta *= 0.5 * (L - d) / d

    约束迭代次数决定刚度：1 次=软绳，20 次≈不可拉伸
    """

    def __init__(self, pts, seg_len=None, damp=0.985, iters=6,
                 gravity=(0.0, 260.0)):
        self.p = np.array(pts, dtype=np.float32)
        self.prev = self.p.copy()
        if seg_len is None:
            seg_len = np.linalg.norm(self.p[1:] - self.p[:-1], axis=1)
        self.L = np.asarray(seg_len, dtype=np.float32)
        self.damp = damp
        self.iters = iters
        self.g = np.array(gravity, dtype=np.float32)

    def step(self, dt=1 / 60.0, wind=(0.0, 0.0), anchor=None):
        n = len(self.p)
        v = (self.p - self.prev) * self.damp
        self.prev = self.p.copy()
        acc = self.g + np.asarray(wind, dtype=np.float32)
        self.p = self.p + v + acc * (dt * dt)

        if anchor is not None:
            self.p[0] = np.asarray(anchor, dtype=np.float32)
        for _ in range(self.iters):
            for i in range(n - 1):
                a, b = self.p[i], self.p[i + 1]
                delta = b - a
                dd = np.linalg.norm(delta) + 1e-9
                corr = delta * (0.5 * (self.L[i] - dd) / dd)
                if i != 0:
                    self.p[i] -= corr
                self.p[i + 1] += corr
        return self.p


# ================================================================
# 六、主入口
# ================================================================

def make_robe(attach, height_px):
    """衣摆 / 飘带链：锚点在腰与胸，长度按身高比例，不是拍脑袋的像素数。

    衣摆 damp 高、iters 多 → 厚重少摆；飘带 damp 低、iters 少 → 轻飘。
    """
    cx, cy = attach["chest"]
    wx, wy = attach["waist"]
    L = float(height_px)
    # 衣摆：自腰垂下，长度 ≈ 腰到膝（D&C: 腰0.560 膝0.285 → 0.275H）
    n_hem = 7
    hem = [[wx, wy + L * (0.275 * (i + 1) / n_hem)] for i in range(n_hem)]
    hem = [[wx, wy]] + hem
    # 飘带：自胸斜垂，长度 ≈ 0.22H
    n_s = 6
    sash = [[cx - L * 0.020 * (i + 1), cy + L * (0.22 * (i + 1) / n_s)]
            for i in range(n_s)]
    sash = [[cx, cy]] + sash
    return {
        "hem": VerletChain(hem, damp=0.972, iters=8, gravity=(0.0, 320.0)),
        "sash": VerletChain(sash, damp=0.955, iters=4, gravity=(0.0, 200.0)),
    }


def _draw_chains(cv, chains, color, width, height_px=None):
    """把链画成**有宽度的布料**，不是细线。

    之前只画 width 递减的多段线 → 屏幕上就是两根细长条，看着像尾巴。
    布料必须有横向铺开：沿链求法向，左右各偏半个"半宽"，连成闭合多边形。
    """
    dr = cv.d
    L = float(height_px or width * 40.0)
    for name, ch in chains.items():
        p = np.asarray(ch.p, dtype=np.float64)
        n = len(p)
        # 半宽：衣摆是下摆散开的裙（下宽上窄），飘带是窄带（梢更窄）
        if name == "hem":
            hw = L * np.linspace(0.075, 0.115, n)
        else:
            hw = L * np.linspace(0.016, 0.006, n)
        tan = np.vstack([p[1:] - p[:-1], p[-1] - p[-2]])
        ln = np.linalg.norm(tan, axis=1) + 1e-9
        nrm = np.stack([-tan[:, 1] / ln, tan[:, 0] / ln], axis=1)
        left = p + nrm * hw[:, None]
        right = p - nrm * hw[:, None]
        poly = np.vstack([left, right[::-1]])
        dr.polygon([tuple(v) for v in poly], fill=color)
        # 下摆/带梢压一道暗边，布料才有厚度
        dr.line([tuple(v) for v in right], fill=tuple(int(c * 0.72) for c in color),
                width=max(1, int(L * 0.006)))


def draw_character(cv, ctx, t=0.0, preset="natural", phase0=0.0,
                   x=None, y=None, height_px=None,
                   robe=(128, 74, 52), skin=(214, 176, 148),
                   attach=None, chains=None, wind=(0.0, 0.0), dt=1 / 60.0,
                   yaw=90.0, body_h=1.70):
    """人物表（2D）入口：正交相机 + 侧视。沿路走远请直接用 draw_body + 真相机。

    x,y: 脚底在屏幕的位置；height_px: 身高像素
    attach: dict，把飘带/衣摆的锚点返回给调用方（供 VerletChain 用）
    """
    ctx = ctx if ctx is not None else {"w": cv.w, "h": cv.h}
    P = gait_params(preset)
    ph = (phase0 + t / P["dur"]) % 1.0
    J = gait(ph, preset)

    H = height_px if height_px is not None else int(ctx["h"] * 0.30)
    if x is None:
        x = ctx["w"] * 0.5
    if y is None:
        y = ctx["h"] * 0.86

    # 正交相机：把"身高像素"换算成 像素/米
    vtop = float(J["head"][1]) + PROP["head_r"] * 1.12 + SOLE_LIFT
    s = H / max(vtop * body_h, 1e-6)
    cam = camera.OrthoCam(s=s, cx=float(x), y0=float(y))
    draw_body(cv, cam, J, Xc=0.0, Zc=10.0, yaw=yaw, body_h=body_h,
              robe=robe, skin=skin, chains=chains, wind=wind, dt=dt,
              attach=attach)
    return ph, J


# ================================================================
# 自检
# ================================================================

if __name__ == "__main__":
    from scene import kit

    ok = True

    def chk(name, cond, extra=""):
        global ok
        ok = ok and bool(cond)
        print("  %-28s %s %s" % (name, "OK" if cond else "FAIL", extra))

    print("=" * 62)
    print("  character 自检")
    print("=" * 62)

    # 1 SDF 原语
    d = sd_circle(np.array([0.0, 1.0, 5.0]), np.array([0.0, 0.0, 0.0]),
                  0.0, 0.0, 1.0)
    chk("圆 SDF 内外符号", d[0] < 0 and d[2] > 0, "内%.1f 外%.1f" % (d[0], d[2]))

    a = np.array([1.0, 1.0]); b = np.array([1.0, 1.0])
    k = smin(a, b, 0.5)
    # smin(1,1,k) = 1 - k/4，故 k=0.5 → 0.875（交界处比 min 低 k/4，即圆滑内凹）
    chk("smin 交界平滑", abs(float(k[0]) - 0.875) < 1e-6, "%.4f" % float(k[0]))

    # 2 步态连续性
    P = gait_params("natural")
    worst = 0.0
    for i in range(60):
        p0, p1 = i / 60.0, (i + 1) / 60.0
        A, B = gait(p0), gait(p1)
        for kk in JOINTS:
            worst = max(worst, float(np.linalg.norm(A[kk] - B[kk])))
    chk("步态逐帧连续", worst < 0.05, "最大关节位移 %.4f" % worst)

    # 3 周期闭合
    A, B = gait(0.0), gait(0.9999)
    close = max(float(np.linalg.norm(A[kk] - B[kk])) for kk in JOINTS)
    chk("周期闭合", close < 0.01, "首尾差 %.5f" % close)

    # 4 膝盖真的弯曲（不总是直的）
    kn = [abs(_knee_curve(i / 24.0, math.radians(50.34))) for i in range(24)]
    chk("膝角有屈伸变化", max(kn) > 0.5 and min(kn) < 0.05,
        "max %.2f min %.2f" % (max(kn), min(kn)))

    # 5 三种预设不同
    g1 = gait(0.25, "natural"); g2 = gait(0.25, "march")
    diff = max(float(np.linalg.norm(g1[kk] - g2[kk])) for kk in JOINTS)
    chk("预设产生不同姿态", diff > 0.02, "差异 %.4f" % diff)

    # 6 形体场（3D 关节 → 正交相机 → 屏幕 SDF）
    J = gait(0.25)
    cam_o = camera.OrthoCam(s=100.0, cx=100.0, y0=700.0)
    Jp = project_body(J, cam_o, Xc=0.0, Zc=10.0, yaw=90.0)
    caps, ell, sm = body_geometry(Jp)
    d, _o, dh = field_px(caps, ell, sm)
    neg = float((d < 0).mean())
    chk("形体场有主体", 0.02 < neg < 0.60, "占比 %.3f 尺寸%s" % (neg, d.shape))
    chk("头有独立场(肤色蒙版)", np.any(dh < 0.0),
        "头像素 %d" % int((dh < 0).sum()))

    # 7 着色：中心亮于边缘（球感）
    col = shade_sdf(d, (128, 74, 52))
    ins = d < 0
    lum = col.mean(axis=2)
    cen = lum[ins].max(); edge = lum[ins & (d > -0.02)].mean()
    chk("中心亮于边缘(立体感)", cen > edge + 8,
        "中心%.0f 边缘%.0f" % (cen, edge))

    # 8 Verlet 链收敛
    vc = VerletChain([[0, 0], [0, 20], [0, 40], [0, 60]])
    for _ in range(120):
        vc.step(dt=1 / 60.0, anchor=(0, 0))
    seg = np.linalg.norm(vc.p[1:] - vc.p[:-1], axis=1)
    chk("Verlet 链不发散", np.all(np.isfinite(vc.p)) and seg.max() < 25.0,
        "最大段长 %.2f" % seg.max())

    # 9 脚底不穿地：任意相位下最低点 ≥ 0（SOLE_LIFT 抬起脚胶囊底）
    lo = 1e9
    for i in range(48):
        jj = gait(i / 48.0)
        for kk in JOINTS:
            lo = min(lo, float(jj[kk][1]) + SOLE_LIFT)
    chk("脚底不穿地", lo > -0.004, "最低 v=%.4f" % lo)

    # 9b 脚掌绝不翻转：全周期 |pitch| < 90°，脚尖永远在脚跟前方
    #    旧实现此处在 phs=0.75~0.95 外推到 -96°~-265°，脚翻过去再弹回来。
    _pmax, _flip, _behind = 0.0, 0, 0
    for i in range(64):
        _pit = foot_pitch(i / 64.0)
        _pmax = max(_pmax, abs(math.degrees(_pit)))
        if abs(math.degrees(_pit)) > 90.0:
            _flip += 1
        if math.cos(_pit) <= 0.0:      # 脚尖转到脚跟后方
            _behind += 1
    chk("脚掌不翻转", _flip == 0, "最大|pitch|=%.1f° 翻转帧%d/64" % (_pmax, _flip))
    chk("脚尖永朝前", _behind == 0, "脚尖跑到脚跟后 %d/64" % _behind)
    _pc = abs(foot_pitch(0.0) - foot_pitch(1.0))
    _tb = abs(_FP_DEG[0] - _FP_DEG[-1])
    chk("脚掌角周期闭合", _pc < 1e-9 and _tb < 1e-9,
        "f(0)≡f(1) 差%.1e；表首尾 %.1f°/%.1f°" % (_pc, _FP_DEG[0], _FP_DEG[-1]))

    # 10 侧向宽度：双腿/双臂真的分开了（3D 化生效）
    jm = gait(0.25)
    dw = abs(jm["ank_l"][2] - jm["ank_r"][2])
    chk("双腿有侧向宽度", dw > 0.05, "ank 间距 %.3f" % dw)

    # 11 透视相机：走远 → 身高单调变小、脚底单调升高、身高/路宽比恒定
    cam_p = camera.Cam(540, 960, 270, 499, 518.6, 1.60, 0.488)
    hs, gy, rt = [], [], []
    for Z in (2.0, 4.0, 8.0, 16.0, 32.0):
        Jz = project_body(gait(0.25), cam_p, Xc=0.0, Zc=Z, yaw=0.0)
        top = Jz["head"][1] - PROP["head_r"] * 1.12 * 1.70 * Jz["head"][2]
        bot = max(Jz["ank_l"][1], Jz["ank_r"][1])
        hs.append(bot - top)
        gy.append(cam_p.ground_y(Z))
        rt.append((Jz["hip_l"][1] - top) / cam_p.px_per_m(Z))
    mono_h = all(hs[i] > hs[i + 1] for i in range(len(hs) - 1))
    chk("走远身高单调变小", mono_h,
        " ".join("%.0f" % v for v in hs))
    chk("脚底随走远升高", all(gy[i] > gy[i + 1] for i in range(len(gy) - 1)),
        " ".join("%.0f" % v for v in gy))
    chk("身高随深度等比缩放", (max(rt) - min(rt)) / max(rt) < 0.05,
        "身高/米 %.3f~%.3f（各关节深度略异，非严格等比）" % (min(rt), max(rt)))

    # 12 朝向：yaw=0（背视走远）前向落在 Z 轴 → 屏幕上前后脚 y 拉开、x 几乎重叠
    jb = gait(0.0)      # 脚跟着地相位：前后脚张得最开
    Ja = project_body(jb, cam_p, Xc=0.0, Zc=2.5, yaw=0.0)
    Js = project_body(jb, cam_p, Xc=0.0, Zc=2.5, yaw=90.0)
    # 背视：前后脚差在"深度"上 → 屏幕上主要是 y 差（远的更高）
    dxb = abs(Ja["ank_l"][0] - Ja["ank_r"][0]); dyb = abs(Ja["ank_l"][1] - Ja["ank_r"][1])
    # 侧视：前后脚差在"横向"上 → 屏幕上主要是 x 差
    dxs = abs(Js["ank_l"][0] - Js["ank_r"][0]); dys = abs(Js["ank_l"][1] - Js["ank_r"][1])
    chk("背视:前后脚显为y差", dyb > dxb, "dx%.1f dy%.1f" % (dxb, dyb))
    chk("侧视:前后脚显为x差", dxs > dys, "dx%.1f dy%.1f" % (dxs, dys))

    # 8b 步态物理：IK 骨长守恒 / 不打滑 / 膝朝前 / 周期闭合 / 重心起伏
    L1_, L2_ = PROP["thigh"], PROP["shank"]
    e1_, e2_, cr_, sl_, hs_ = [], [], [], [], []
    for i in range(96):
        ph_ = i / 96.0
        J_ = gait(ph_); hs_.append(J_["hip_l"][1])
        for s_ in ("l", "r"):
            h_, k_, a_ = J_["hip_" + s_], J_["knee_" + s_], J_["ank_" + s_]
            e1_.append(abs(np.linalg.norm(k_ - h_) - L1_))
            e2_.append(abs(np.linalg.norm(a_ - k_) - L2_))
            dv_, kv_ = a_ - h_, k_ - h_
            cr_.append(dv_[0] * kv_[1] - dv_[1] * kv_[0])
            if (ph_ + (0.0 if s_ == "l" else 0.5)) % 1.0 < 0.62:
                sl_.append(abs(gait(ph_ + 1 / 96.0)["ank_" + s_][0] - a_[0]))
    e1_, e2_, cr_, sl_ = map(np.array, (e1_, e2_, cr_, sl_))
    chk("IK 骨长守恒", e1_.max() < 1e-6 and e2_.max() < 1e-6,
        "大腿%.1e 小腿%.1e" % (e1_.max(), e2_.max()))
    chk("膝盖一律朝前", bool((cr_ > 0).all()), "异常%d/%d" % ((cr_ <= 0).sum(), len(cr_)))
    cvsl = sl_.std() / max(sl_.mean(), 1e-9)
    chk("支撑脚不打滑", cvsl < 0.05, "CV %.4f" % cvsl)
    g0_, g1_ = gait(0.0), gait(1.0)
    chk("周期闭合(φ=0≡1)", np.allclose(g0_["hip_l"], g1_["hip_l"], atol=1e-6)
        and np.allclose(g0_["ank_l"], g1_["ank_l"], atol=1e-6), "hip/ank 均闭合")
    com = max(hs_) - min(hs_)
    chk("重心起伏合理", 0.02 < com < 0.06, "%.4f (真实≈0.03)" % com)

    # 9 画出人物（多相位居一格）
    cv = kit.Canvas(540, 960, (28, 34, 48))
    for i, ph in enumerate([0.0, 0.25, 0.5, 0.75]):
        draw_character(cv, {"w": 540, "h": 960}, phase0=ph,
                       x=90 + i * 120, y=880, height_px=300)
    cv.img.save("人物_四相位.png")
    chk("人物绘制成功", True, "→ 人物_四相位.png")

    # 10 走路序列（1 个周期 12 帧小图）
    tiles = []
    for i in range(12):
        c2 = kit.Canvas(180, 320, (28, 34, 48))
        draw_character(c2, {"w": 180, "h": 320}, phase0=i / 12.0,
                       x=90, y=300, height_px=250)
        tiles.append(c2.img)
    sheet = Image.new("RGB", (180 * 6, 320 * 2), (18, 22, 32))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % 6) * 180, (i // 6) * 320))
    sheet.save("人物_走路12帧.png")
    chk("走路序列出图", True, "→ 人物_走路12帧.png")

    print("-" * 62)
    print("  SELF_CHECK:", "PASS" if ok else "FAIL")
