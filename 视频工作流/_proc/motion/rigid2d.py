# 契约: proc/motion/rigid2d
#   一句话: 2D 旋转刚体（SAT 碰撞 + 顺序冲量 + 距离约束）——本文件仅转发
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""2D 刚体动力学（C15~C19 依赖）。

原 917 行单体已按层切为五块，依赖单向无环：

    rigid2d_core     常量(Box2D 原文值) + 几何基元 Body2/rot/cross
        ↑
    rigid2d_collide  SAT 盒-盒 / 地面 / 圆-线段
    rigid2d_solve    Contact 预处理、冲量施加、顺序冲量迭代、距离约束
        ↑
    rigid2d_world    World 主循环（接触生成/休眠/积分/位置松弛）
        ↑
    rigid2d_sim      stack / ramp / pendulum 三能力 + self_check

本文件只做 re-export，外部 `from motion.rigid2d import xxx` 写法不变。
三个 @capability(stack/ramp/pendulum) 随 sim 模块导入时注册。

出处（先搜证再实现，不自造）：
[1] Erin Catto《Fast and Simple Physics using Sequential Impulses》
    GDC2006 / Box2D Lite：顺序冲量、warm starting、累积冲量裁剪 Pn>=0、
    库仑摩擦锥 |Pt| <= mu*Pn
[2] 同文 §Baumgarte 位置修正：bias = (beta/dt)*max(0, pen - slop)
    beta = 0.2，slop = 0.005（Box2D b2_linearSlop）
[3] SAT 分离轴定理（2D 凸多边形）：只测两物体面法线，取穿透最小轴
[4] 距离约束（摆锤）：C = |p - anchor| - L，等效 Box2D b2DistanceJoint
"""
import os as _os, sys as _sys, math as _math
if __package__ in (None, ""):
    _d = _os.path.dirname(_os.path.abspath(__file__))
    while _d != _os.path.dirname(_d) and _os.path.basename(_d) != "_proc":
        _d = _os.path.dirname(_d)
    for _p in (_os.path.dirname(_d), _d):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    __package__ = _os.path.relpath(
        _os.path.dirname(_os.path.abspath(__file__)), _d).replace(_os.sep, ".")

from .rigid2d_core import (  # noqa: F401
    SLOP, BETA, SLEEP_LIN, SLEEP_ANG, SLEEP_TIME, WAKE_VN,
    POS_PERCENT, _ZERO, MAX_LIN_CORR, ITER,
    rot, cross, cross_w, Body2,
)
from .rigid2d_collide import (  # noqa: F401
    collide_box_box, collide_box_box_np, collide_ground, collide_seg,
    _clip_face, _inside_obb, _round_pair, Segment2,
)
from .rigid2d_solve import (  # noqa: F401
    Contact, solve, _prepare, _apply, DistanceConstraint,
)
from .rigid2d_world import World  # noqa: F401
from .rigid2d_sim import (  # noqa: F401
    stack_sim, ramp_sim, pendulum_sim, self_check,
)

__all__ = [
    "SLOP", "BETA", "SLEEP_LIN", "SLEEP_ANG", "SLEEP_TIME", "WAKE_VN",
    "POS_PERCENT", "MAX_LIN_CORR", "ITER",
    "rot", "cross", "cross_w", "Body2",
    "collide_box_box", "collide_box_box_np", "collide_ground", "collide_seg",
    "Segment2", "Contact", "solve", "DistanceConstraint",
    "World", "stack_sim", "ramp_sim", "pendulum_sim", "self_check",
]


def _forward_check():
    """转发完整性自检：原单体对外暴露的名字一个都不能少"""
    need = __all__ + ["_ZERO", "_clip_face", "_inside_obb", "_round_pair",
                      "_prepare", "_apply"]
    miss = [n for n in need if n not in globals()]
    return not miss, ("缺失: " + ", ".join(miss)) if miss else ""
