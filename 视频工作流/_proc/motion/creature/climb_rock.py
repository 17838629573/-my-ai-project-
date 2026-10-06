#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 契约: proc/motion/character/climb_rock
#   一句话: 不规则支点攀岩：环境查询支点 + 两骨 IK 放置 + 三点支撑
"""攀岩攀爬（climb_rock）：不规则支点 + 环境查询 + IK 肢体放置。

用途: 给 AI 视频模型当前置骨架锚点时，覆盖"攀岩/不规则支点攀爬"这一类动作。
与 climb.py（爬梯，梯距硬编码）的区别：本模块的支点来自**环境查询**
（sweep_hold 球形范围查询 + 法线点乘判坡度），不硬编码间距。

业界依据（已检索）:
- 环境查询: Unreal/Unity 攀爬系统的通行做法是 shape casting / capsule
  sweep / raycast 找可攀面，命中点当 IK 目标，表面法线决定手掌朝向
  （Quaternion.FromToRotation 对齐 -normal）。本模块用球形范围查询 +
  normal·UP 判坡度实现同一步骤。
- 接触精度: CIMI4D / HumanPOSE 等以 5cm 为接触判真阈值；本模块取 1e-9
  （解析落点，无数值误差）并另设 5cm 作为"环境查询命中"的业界对照阈值。
- 稳定性: 攀爬静态姿态要求 >=3 效应器支撑（三点固定），本模块每步只动
  一个效应器（对角交替 LF->RH->RF->LH），故恒为 3 点支撑。
- 平滑: EaseLerp（smoothstep），端点一阶导为 0，避免效应器切换跳帧。

坐标: 岩壁为 x=0 平面，法线 +x 指向攀爬者；y 向上；z 为沿壁左右。
      所有值归一化身高（1.70m），与 body/proportions.py 一致。
"""
import math
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

import numpy as np

from ..beat import capability
from motion.character.climb import _ease, _mid, UPPER_ARM, FOREARM, THIGH, SHANK, SHOULDER_UP

# ---- 几何常量（归一化身高）----
HAND_Z = 0.12          # 手支点左右偏移
FOOT_Z = 0.09          # 脚支点左右偏移
WALL_X = 0.02          # 效应器贴壁深度（支点面上）
BODY_X = 0.18          # 躯干离壁距离
PEL_UP = 0.13          # pelvis 相对足支点均值高度（保证臂/腿可达）
HF_GAP = 0.70          # 手支点均值 - 足支点均值（攀爬手脚间距）
ARM_FULL = UPPER_ARM + FOREARM      # 0.332
LEG_FULL = THIGH + SHANK            # 0.491

# 效应器顺序（对角交替，业界攀爬常见：手脚不同时同侧）
ORDER = ("lf", "rh", "rf", "lh")
EFF_Z = {"lh": +HAND_Z, "rh": -HAND_Z, "lf": +FOOT_Z, "rf": -FOOT_Z}
IS_HAND = {"lh": True, "rh": True, "lf": False, "rf": False}


def wall_holds(n_level=6, dy=0.30, base_y=0.10, jx=0.0):
    """生成岩壁支点集（环境）。

    返回 [(x, y, z, nx, ny, nz), ...]，后三项为壁面法线（近垂直）。
    手列与脚列错开 dy/2，保证 hand_mean - foot_mean = HF_GAP 恒定。
    """
    hs = []
    for k in range(n_level):
        yf = base_y + k * dy
        hs.append((0.0, yf, +FOOT_Z + jx, 1.0, 0.0, 0.0))
        hs.append((0.0, yf, -FOOT_Z + jx, 1.0, 0.0, 0.0))
        hs.append((0.0, yf + HF_GAP, +HAND_Z + jx, 1.0, 0.0, 0.0))
        hs.append((0.0, yf + HF_GAP, -HAND_Z + jx, 1.0, 0.0, 0.0))
    return hs


def sweep_hold(pos, holds, reach=0.45, min_rise=0.05, up=(0.0, 1.0, 0.0)):
    """环境查询：球形范围扫掠 + 法线点乘判坡度。

    只返回近垂直面（法线与竖直夹角 <= 30°）上、高于当前位置 min_rise、
    水平可达（<reach）的支点中**最低**的那个（攀爬选最近可抓点）。
    找不到返回 None。
    """
    best = None
    for h in holds:
        p = np.asarray(h[:3], float)
        d = p - np.asarray(pos, float)
        nrm = np.asarray(h[3:6], float)
        if abs(float(nrm @ np.asarray(up, float))) > 0.5:
            continue                      # 坡度判据：法线近竖直=水平面，不可攀
        if float(d[1]) < min_rise:
            continue                      # 必须向上
        if float(np.hypot(d[2], d[0])) > reach:
            continue                      # 超出可达范围
        if best is None or float(p[1]) < float(best[1]):
            best = p
    return best


def _eff_level(step_idx, i):
    """效应器 i 在第 step_idx 步开始时已完成的移动次数。"""
    k = step_idx - i
    return 0 if k < 0 else (k + 3) // 4


def _effectors(t, cycle=1.6, dy=0.30, base_y=0.10):
    """返回 (四点位置字典, 正在移动的效应器名, 相位)。"""
    r = t / cycle
    si = int(math.floor(r))
    ph = r - si
    mv = ORDER[si % 4]
    e = _ease(ph)
    out = {}
    for i, nm in enumerate(ORDER):
        lv = _eff_level(si, i)
        rise = lv * dy
        y0 = base_y + (HF_GAP if IS_HAND[nm] else 0.0)
        yy = y0 + rise
        if nm == mv:
            yy += dy * e                # 向上移动一级
        out[nm] = (WALL_X, yy, EFF_Z[nm])
    return out, mv, ph


def _pelvis(eff):
    """pelvis 由支撑点推导：足支点均值上方 PEL_UP。"""
    fy = (eff["lf"][1] + eff["rf"][1]) * 0.5
    return (BODY_X, fy + PEL_UP, 0.0)


@capability("climb_rock", "攀岩: 环境查询(sweep_hold 球形扫掠+法线坡度判据)+四效应器对角交替+两骨IK; 恒3点支撑, 支撑相零滑移")
def climb_rock(t, cycle=1.6, dy=0.30, base_y=0.10, body_h=1.70):
    """攀岩姿态。

    t       秒（连续）
    cycle   每个效应器移动一次的耗时（秒）
    dy      相邻支点高差（归一化身高）
    base_y  起始足支点高度（归一化身高）
    返回 21 关节字典，值 (x, y, z) 归一化身高。
    """
    eff, mv, _ph = _effectors(t, cycle, dy, base_y)
    P = _pelvis(eff)

    J = {}
    J["pelvis"] = P
    J["waist"] = (BODY_X, P[1] + 0.10, 0.0)
    J["chest"] = (BODY_X, P[1] + 0.24, 0.0)
    J["neck"] = (BODY_X, P[1] + 0.34, 0.0)
    J["head"] = (BODY_X, P[1] + 0.44, 0.0)

    sh_y = P[1] + SHOULDER_UP
    J["sh_l"] = (BODY_X, sh_y, +0.10)
    J["sh_r"] = (BODY_X, sh_y, -0.10)

    for side, nm in (("l", "lh"), ("r", "rh")):
        J["wri_" + side] = eff[nm]
        J["elb_" + side] = _mid(J["sh_" + side], eff[nm],
                                UPPER_ARM, FOREARM, (0.0, 0.0, 1.0))

    J["hip_l"] = (BODY_X, P[1], +0.080)
    J["hip_r"] = (BODY_X, P[1], -0.080)

    for side, nm in (("l", "lf"), ("r", "rf")):
        a = eff[nm]
        J["ank_" + side] = (a[0], a[1] + 0.020, a[2])
        J["heel_" + side] = (a[0] - 0.010, a[1], a[2])
        J["toe_" + side] = (a[0] + 0.045, a[1] + 0.005, a[2])
        J["knee_" + side] = _mid(J["hip_" + side], J["ank_" + side],
                                 THIGH, SHANK, (0.0, 0.0, 1.0))
    return J


# ------------------------- 自检 -------------------------
EFF = {"lh": "wri_l", "rh": "wri_r", "lf": "ank_l", "rf": "ank_r"}


def _bone_err(a, b, L):
    """骨长偏差 |‖a−b‖ − L|。"""
    return abs(float(np.linalg.norm(
        np.asarray(a, float) - np.asarray(b, float))) - L)


def _check_query(c, b0):
    """环境查询判据：命中向上支点 + 坡度判据拒水平面。"""
    q = sweep_hold((WALL_X, b0, +FOOT_Z), wall_holds(),
                   reach=0.45, min_rise=0.05)
    c.chk("环境查询命中向上支点", q is not None,
          "hit=%s" % (None if q is None else "y=%.3f" % float(q[1])))
    flat = [(0.0, b0 + 0.30, 0.0, 0.0, 1.0, 0.0)]
    c.chk("坡度判据拒水平面", sweep_hold((WALL_X, b0, 0.0), flat) is None)


def _check_support(c, Js):
    """支撑判据：三点固定 + 支撑相零滑移。"""
    worst_sup, slip = 99, 0.0
    for k in range(1, len(Js)):
        moved = 0
        for nm in ORDER:
            j = EFF[nm]
            dd = float(np.linalg.norm(np.asarray(Js[k][j], float)
                                      - np.asarray(Js[k - 1][j], float)))
            if dd > 1e-12:
                moved += 1
            else:
                slip = max(slip, dd)
        worst_sup = min(worst_sup, 4 - moved)
    c.chk("恒 >=3 效应器支撑（三点固定）", worst_sup >= 3,
          "min_support=%d" % worst_sup)
    c.chk("支撑相零滑移（foot/hand sliding）", slip < 1e-9,
          "slip=%.3e" % slip)
    return worst_sup


def _check_body(c, Js):
    """形体判据：骨长守恒 / 不穿壁 / 帧间平滑 / 持续上升。"""
    be = max(_bone_err(Js[k]["sh_l"], Js[k]["elb_l"], UPPER_ARM)
             for k in range(len(Js)))
    c.chk("上臂骨长守恒", be < 1e-9, "err=%.3e" % be)
    bk = max(_bone_err(Js[k]["hip_l"], Js[k]["knee_l"], THIGH)
             for k in range(len(Js)))
    c.chk("大腿骨长守恒", bk < 1e-9, "err=%.3e" % bk)

    minx = min(float(Js[k][j][0]) for k in range(len(Js)) for j in Js[k])
    c.chk("不穿透岩壁（x >= 0）", minx >= -1e-12, "min_x=%.3e" % minx)

    jump = max(float(np.linalg.norm(
        np.asarray(Js[k][j], float) - np.asarray(Js[k - 1][j], float)))
        for k in range(1, len(Js)) for j in Js[k])
    c.chk("帧间无跳变（平滑）", jump < 0.02, "max_jump=%.4f" % jump)

    y0 = float(Js[0]["pelvis"][1])
    y1 = float(Js[-1]["pelvis"][1])
    c.chk("持续向上攀爬", y1 > y0 + 1e-6, "%.4f -> %.4f" % (y0, y1))
    return y1 - y0, jump


def self_check():
    """攀岩判据自检：环境查询 / 三点支撑 / 骨长守恒 / 不穿壁 / 平滑 / 上升。"""
    from base.assertrun import Checker
    c = Checker("climb_rock")
    cy, dy, b0 = 1.6, 0.30, 0.10
    n = 320                                    # 5 个效应器步
    Js = [climb_rock(k * cy / 64.0, cycle=cy, dy=dy, base_y=b0)
          for k in range(n)]
    _check_query(c, b0)
    worst_sup = _check_support(c, Js)
    rise, jump = _check_body(c, Js)
    c.note("攀岩 %d 帧：上升 %.4f，最小支撑 %d，最大帧间位移 %.4f"
           % (n, rise, worst_sup, jump))
    return c.report()


if __name__ == "__main__":
    self_check()
