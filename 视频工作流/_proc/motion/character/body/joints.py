# 契约: proc/motion/character/joints
#   一句话: 关节表、躯干摆动常量、步态预设与 gait_params
#   完整契约见 motion/character/__init__.py

import math
import numpy as np
from .proportions import *

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

__all__ = [n for n in dir() if not n.startswith("__")]

# ---- 手臂段长与休息位（供 prop.py 道具交接使用）----
# 出处 Drillis & Contini 1966（转引 Winter 1990 表 4.1），归一化身高
ARM_SEG = {"upperarm": 0.186, "forearm": 0.146, "hand": 0.108}
# 自然站立腕位：肩高 0.82 减去上臂+前臂，略前伸
REST_ARM = (0.10, 0.82 - ARM_SEG["upperarm"] - ARM_SEG["forearm"], 0.115)
