# 契约: proc/motion/character/gait
#   一句话: 步态主函数：臂摆、膝屈曲线、相位推进与 BODY_SPEC
#   完整契约见 motion/character/__init__.py

import math
from typing import NamedTuple
import numpy as np
from .proportions import *
from .joints import *
from .leg import *


# 参数对象：把 >3 个参数收成具名整体（业界：参数>3 用 Parameter Object）
class Step(NamedTuple):
    """步长参数。stride 归一化身高单位，stance 支撑相占比"""
    stride: float
    stance: float


class Root(NamedTuple):
    """根状态（solve_root 的输出）：重心三轴 + 双脚锁定表"""
    u: float      # 身体前向
    w: float      # 身体侧向
    y: float      # 髋高（由实测 COM 曲线定，不由几何反推）
    dy: float     # 躯干随动起伏
    foots: dict   # {"l"/"r": (相位, 脚踝 uv)}，脚世界锁定


class Spine(NamedTuple):
    """脊柱解。twist 是胸-骨盆扭转**角**，供臂摆取肩点"""
    joints: dict
    twist: float


def _S(u, v, w=0.0):
    return np.array([u, v, w], dtype=np.float64)


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


def solve_root(ph, P, step):
    """根：侧向摆 + 重心起伏 + 双脚世界锁定。

    垂直方向直接取实测 COM 曲线（业界顺序：COM 是先验，腿去适配，不是几何反推）：
        y = y0 − A·cos(4πφ)  每周期 2 次；最低 5%/55%(双腿支撑) 最高 30%/80%(单腿支撑)
        峰峰 5 cm（Oklahoma HSC / J.Biomech 23人实测）
    步长变化不改写曲线——差值交给膝盖屈曲吸收，这才是"垂直位移对步长不敏感"的物理来源。
    """
    two = 2.0 * np.pi * ph
    span = PROP["thigh"] + PROP["shank"]
    straight = 0.975                      # 腿常备微屈，永不锁死
    # 前后轴：重心匀速前进，不叠正弦（业界明确要求脚位移 Linear）
    # 左右轴：Saunders 第 5 决定因素，每周期 1 次（原错加在 u 上，已修正）
    w = P["lateral"] * math.sin(two)

    foots = {}
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        phs = (ph + (0.0 if sgn > 0 else 0.5)) % 1.0
        foots[side] = (phs, np.array(foot_local(phs, step.stride, step.stance, P["lift"])))

    # 髋会被骨盆旋转/倾斜推离中线（hip_u/hip_v 各偏 LAT["hip"]·sin(θ)），
    # 反解可达高度时必须把这截余量预留出来，否则摆动腿髋踝距略超 reach，
    # two_bone_ik 的 soft clamp 会把小腿拉长（实测曾达 14cm）。
    _lat_room = (LAT["hip"] * (math.sin(math.radians(PELVIS_ROT_DEG))
                               + math.sin(math.radians(PELVIS_LIST_DEG)))
                 + LIFT_ROOM)
    reach = span * straight - _lat_room
    y_stand = PROP["ankle"] + reach
    y = y_stand - COM_AMP_N * math.cos(2.0 * two)
    dy = y - y_stand                      # 躯干整体随之起伏（腿伸直时 dy=0）
    return Root(u=0.0, w=w, y=y, dy=dy, foots=foots)


def solve_legs(root, stance):
    """腿：脚世界锁定 + 两骨 IK 反求膝盖（消除打滑）。

    侧向宽度 LAT 走 w 轴（不再塞进 u），u/v 保持纯矢状面。
    """
    L1, L2 = PROP["thigh"], PROP["shank"]
    out = {}
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        phs, ank = root.foots[side]
        # ---- 骨盆旋转 4° / 倾斜 5°（Saunders 决定因素 1、2）----
        # 旋转：绕竖直轴，髋点 (0, w) → u 分出前后，两侧反相
        # 倾斜：冠状面，摆动侧下降；两侧反相
        two_s = 2.0 * np.pi * phs
        rot_s = math.radians(PELVIS_ROT_DEG) * math.cos(two_s)
        list_s = math.radians(PELVIS_LIST_DEG) * math.cos(two_s)
        hip_u = root.u + (LAT["hip"] * sgn) * math.sin(rot_s)
        hip_w = root.w + (LAT["hip"] * sgn) * math.cos(rot_s)
        hip_v = root.y - LAT["hip"] * math.sin(list_s) * sgn

        knee_uv = two_bone_ik(np.array([hip_u, hip_v]), ank, L1, L2, bend=(1.0, 0.0))  # 膝朝前
        pit = foot_pitch(phs, stance)                                                  # 脚掌滚动
        aw = LAT["ank"] * sgn + root.w
        out["hip_" + side] = _S(hip_u, hip_v, hip_w)
        out["knee_" + side] = _S(knee_uv[0], knee_uv[1], LAT["knee"] * sgn + root.w)
        out["ank_" + side] = _S(ank[0], ank[1], aw)
        # 旧写法 `max(0.0, sin(pit))` 把负 pitch 全压成 0 → 蹬地时脚尖永远压不下去，
        # 摆动时脚尖还被钉在踝的高度，配合 pitch 外推就成了「脚翻转」的观感。
        # 脚掌应整体绕踝转：脚尖在前 (cos,sin)，脚跟在后 (-cos,-sin)。
        out["toe_" + side] = _S(ank[0] + TOE_LEN * np.cos(pit),
                                ank[1] + TOE_LEN * np.sin(pit), aw)
        out["heel_" + side] = _S(ank[0] - HEEL_LEN * np.cos(pit),
                                 ank[1] - HEEL_LEN * np.sin(pit), aw)
    return out


def solve_spine(ph, P, root):
    """脊柱：S 曲线 + 反向旋转（髋摆 → 胸反相）。

    扭转是「角度」，不是位移。躯干中心线在旋转轴上 → 位移≈0；
    真正位移的是偏离轴的点（肩，半径=SH_W）。肩前后摆幅由此自然落在文献 3~5 cm。
    """
    two = 2.0 * np.pi * ph
    twist = -P["thorax_rom"] * np.cos(two)               # 胸-骨盆扭转角（rad），反相于髋
    lean_ang = math.radians(P["lean_deg"]) * np.sin(two)  # 躯干前后倾角（rad）
    # 倾角 × 髋→颈的力臂 = 颈/头的前后位移（SwayStar pitch 6.7°±2.2° 的半幅）
    lean_d = (PROP["neck"] - PROP["hip"]) * math.sin(lean_ang)
    j = {
        "pelvis": _S(root.u, root.y, root.w),
        "waist": _S(root.u + 0.10 * lean_d, root.y + PROP["waist"] - PROP["hip"], root.w * 0.55),
        "chest": _S(root.u + 0.55 * lean_d, PROP["chest"] + root.dy, root.w * 0.30),
        "neck": _S(root.u + 0.80 * lean_d, PROP["neck"] + root.dy, root.w * 0.18),
        # 头滞后一拍（follow through 的雏形）
        "head": _S(root.u + 1.00 * lean_d,
                   PROP["neck"] + root.dy + PROP["head_r"] * 0.95, root.w * 0.14),
    }
    return Spine(joints=j, twist=twist)


def solve_arms(ph, P, spine):
    """臂：肩反相于同侧髋。

    胸椎扭转是**绕竖直轴的转角**（不是位移）：肩点沿该角在 (u,w) 平面上转，
    于是背视时两肩一前一后、侧视时两肩一左一右 —— 朝向自然就对了。
    """
    AU, AF = PROP["upperarm"], PROP["forearm"]
    chest = spine.joints["chest"]
    out = {}
    for side, sgn in (("l", 1.0), ("r", -1.0)):
        phs = (ph + (0.0 if sgn > 0 else 0.5)) % 1.0
        two_s = 2.0 * np.pi * phs
        th_sh = -P["arm_swing"] * np.cos(two_s)          # 反相
        th_elb = -0.25 - 0.22 * max(0.0, np.cos(two_s))  # 前摆时屈肘多
        su = chest[0] + sgn * SH_W * np.sin(spine.twist)
        sw = chest[2] + sgn * SH_W * np.cos(spine.twist)
        sv = PROP["shoulder"]
        elb, wri = _arm_chain(su, sv, th_sh, th_elb, AU, AF)
        out["sh_" + side] = _S(su, sv, sw)
        out["elb_" + side] = _S(elb[0], elb[1], sw)
        out["wri_" + side] = _S(wri[0], wri[1], sw)
    return out


def gait(ph, preset="natural", scale_h=1.0, stride=None, stance=STANCE_FRAC):
    """步态求解：相位 ph∈[0,1) → 每个关节的 **(u, v, w)**（归一化身高单位）

        u = 身体前向（人朝哪走就往哪）
        v = 离地高度
        w = 身体侧向（左为正）

    三轴分开是"能沿路走远"的前提：2D 时代只有 (u,v)，左右宽度无处安放，
    人只能永远侧站；3D 后同一个解可以投成侧视 / 背视 / 正视 / 任意角度。

    动力学链（业界 walk cycle 标准顺序）：
        髋摆 → 脊柱反向旋转 → 胸 → 肩（反相于髋）→ 头（滞后）→ 臂 → 腿 → 脚

    本函数只讲故事（Composed Method），每段细节藏在同名子函数里。
    """
    P = gait_params(preset)
    step = Step(stride=(P["stride"] if stride is None else stride), stance=stance)

    root = solve_root(ph, P, step)
    out = solve_legs(root, stance)
    spine = solve_spine(ph, P, root)
    out.update(spine.joints)
    out.update(solve_arms(ph, P, spine))

    if scale_h != 1.0:
        out = {k: np.asarray(v) * scale_h for k, v in out.items()}
    return out


__all__ = [n for n in dir() if not n.startswith("__")]
