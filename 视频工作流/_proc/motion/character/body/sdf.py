# 契约: proc/motion/character/sdf
#   一句话: SDF 场原语（胶囊/圆/椭圆/平滑并集）+ BODY_SPEC 胶囊装配清单
#   备注: BODY_SPEC 由 gait.py 迁来——形体装配与形体场同属一处，消除 Feature Envy
#   完整契约见 motion/character/__init__.py

import math
import numpy as np

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
# 二、形体场（SDF 装配）
# ================================================================

# 每个部件：胶囊端点取自关节名 + 半径（归一化身高单位）
# 原来住在 gait.py，但唯一使用者是 render.py（Feature Envy）→ 归位到形体层
BODY_SPEC = [
    ("hip_l", "knee_l", 0.052), ("knee_l", "ank_l", 0.042),
    ("hip_r", "knee_r", 0.052), ("knee_r", "ank_r", 0.042),
    ("pelvis", "waist", 0.082), ("waist", "chest", 0.088),
    ("chest", "neck", 0.070),
    ("sh_l", "elb_l", 0.034), ("elb_l", "wri_l", 0.029),
    ("sh_r", "elb_r", 0.034), ("elb_r", "wri_r", 0.029),
]

__all__ = [n for n in dir() if not n.startswith("__")]
