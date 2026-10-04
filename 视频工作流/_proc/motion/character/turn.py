# -*- coding: utf-8 -*-
"""原地转身模块（动作层·转身）

契约: proc/motion/character/turn
  一句话: yaw 连续转身 + 原地换步 —— 让人物真的"转过去"而不是镜像翻转
  完整契约见 motion/character/__init__.py

  输入: 起始 yaw、目标转角 delta_deg、进度 u∈[0,1]、基准关节 J
  输出: {'yaw': float, 'J': {关节: (u,v,w)}}
  依赖: numpy, math
  被依赖: motion.beat, motion.cafe
  约束: 转身速率分档（基础 125°/s，|Δ|>100° 线性加速到 300°/s）；
        yaw 由每帧设置驱动，转身动画本身只带腿部动作；
        缓动用 smoothstep u²(3-2u)，首尾速度为 0；
        换步只在抬脚侧，支撑脚锁死不打滑；
        躯干转向滞后于骨盆（分段转向），头部最后跟上
  校验: python -m motion.character.turn
"""
import math

import numpy as np

from ..beat import capability

# --- 转身速率：UE4/UE5 Turning In Place 的分档速率 ---------------------
# 基础转身 125°/s；|Δ|>100° 时按角度线性加速，180° 转身达上限 300°/s
# 于是 180° 转身耗时 180/300 = 0.6s，落在实测区间 0.6~1.44s 下限
TURN_RATE_BASE = 125.0    # °/s，小角度转身
TURN_RATE_FAST = 300.0    # °/s，大角度转身上限
FAST_FROM = 100.0         # °，超过这个角度开始加速
FAST_SPAN = 80.0          # °，再大这么多就到满速（180° 时满速）

# --- 换步与姿态 -------------------------------------------------------
TURN_STEPS = 2            # 一次转身完成的换步次数（左右各抬一次）
TURN_STEP_H = 0.022       # 抬脚高度（归一化身高）
TURN_CROUCH = 0.012       # 转身中屈膝量（重心微降）
TURN_TORSO_LAG = 0.22     # 躯干转向滞后于骨盆的比例
TURN_HEAD_LAG = 0.40      # 头部转向滞后比例（头最后跟上）


def _clamp01(u):
    return 0.0 if u < 0.0 else (1.0 if u > 1.0 else float(u))


def turn_speed(delta_deg):
    """转身角速度 °/s。|Δ|≤100° 用基础速率，越大越快，180° 到上限。"""
    a = abs(float(delta_deg))
    if a <= FAST_FROM:
        return TURN_RATE_BASE
    k = min(1.0, (a - FAST_FROM) / FAST_SPAN)
    return TURN_RATE_BASE + (TURN_RATE_FAST - TURN_RATE_BASE) * k


def turn_duration(delta_deg):
    """转身耗时（秒）。"""
    a = abs(float(delta_deg))
    sp = turn_speed(a)
    return 0.0 if a == 0.0 else a / sp


def turn_yaw(yaw0, delta_deg, u):
    """进度 u∈[0,1] → 当前 yaw。smoothstep 缓动，首尾角速度为 0。"""
    u = _clamp01(u)
    k = u * u * (3.0 - 2.0 * u)
    return float(yaw0) + float(delta_deg) * k


def turn_stance(u):
    """换步状态：左右脚抬起高度 + 屈膝量。

    抬脚只在摆动侧，支撑侧恒为 0 —— 锁死不漂移。
    返回 (lift_l, lift_r, crouch)
    """
    u = _clamp01(u)
    ph = u * TURN_STEPS * 2.0 * math.pi
    # 钟形包络：转身首尾不抬脚，中间才换步
    env = math.sin(math.pi * u)
    lift_l = max(0.0, math.sin(ph)) * TURN_STEP_H * env
    lift_r = max(0.0, math.sin(ph + math.pi)) * TURN_STEP_H * env
    crouch = TURN_CROUCH * env
    return lift_l, lift_r, crouch


def turn_legs(J, u):
    """把换步施加到腿部关节（业界: 转身动画只带腿部动作，朝向由每帧 yaw 定）。

    输入/输出均为身体坐标 {关节: (u,v,w)}，v 为归一化身高。
    """
    u = _clamp01(u)
    lift_l, lift_r, crouch = turn_stance(u)
    out = {k: np.array(v, dtype=float) for k, v in J.items()}
    for side, lift in (("l", lift_l), ("r", lift_r)):
        ank, toe, knee, hip = f"ank_{side}", f"toe_{side}", f"knee_{side}", f"hip_{side}"
        if ank in out:
            out[ank] = out[ank] + np.array([0.0, lift, 0.0])
        if toe in out:
            out[toe] = out[toe] + np.array([0.0, lift * 1.35, 0.0])
        if knee in out:
            # 抬脚时膝盖多屈一点
            out[knee] = out[knee] + np.array([0.0, lift * 0.55 - crouch, 0.0])
        if hip in out:
            out[hip] = out[hip] + np.array([0.0, -crouch, 0.0])
    if "root" in out:
        out["root"] = out["root"] + np.array([0.0, -crouch, 0.0])
    return out


def turn_torso(J, u, delta_deg):
    """分段转向：躯干滞后于骨盆、头部最后跟上。

    转身不是整块刚体一起转 —— 先脚和髋，再躯干，最后头。
    这里用"额外的扭转偏移"表达，实际朝向仍由 yaw 统一控制。
    返回扭转量 (torso_twist, head_twist)，单位 °，随进度回零。
    """
    u = _clamp01(u)
    env = math.sin(math.pi * u)      # 中途最大，首尾为 0（转完必须回正）
    torso = delta_deg * TURN_TORSO_LAG * env
    head = delta_deg * TURN_HEAD_LAG * env
    return torso, head


def self_check():
    ok = True
    # 速率分档
    assert abs(turn_speed(90) - TURN_RATE_BASE) < 1e-9, "90° 应用基础速率"
    assert abs(turn_speed(180) - TURN_RATE_FAST) < 1e-9, "180° 应达上限速率"
    assert TURN_RATE_BASE < turn_speed(140) < TURN_RATE_FAST, "140° 应介于两者之间"
    # 时长落在实测区间
    d180 = turn_duration(180)
    assert 0.6 - 1e-9 <= d180 <= 1.44, f"180°转身 {d180:.3f}s 应落在 0.6~1.44s"
    assert turn_duration(0) == 0.0, "0° 转身耗时 0"
    # yaw 连续且端点准确
    assert abs(turn_yaw(180.0, 180.0, 0.0) - 180.0) < 1e-9, "起点应等于 yaw0"
    assert abs(turn_yaw(180.0, 180.0, 1.0) - 360.0) < 1e-9, "终点应等于 yaw0+delta"
    ys = [turn_yaw(180.0, 180.0, i / 200.0) for i in range(201)]
    dif = [abs(ys[i + 1] - ys[i]) for i in range(200)]
    assert max(dif) < 180.0 * 3.0 / 200.0, f"单帧 yaw 跳变过大 {max(dif):.3f}"
    # 首尾角速度为 0（smoothstep）
    assert abs(ys[1] - ys[0]) < abs(ys[100] - ys[99]), "起步应慢于中段"
    assert abs(ys[-1] - ys[-2]) < abs(ys[100] - ys[99]), "收尾应慢于中段"
    # 换步：支撑侧不抬起
    for i in range(101):
        ll, lr, _c = turn_stance(i / 100.0)
        assert ll >= -1e-12 and lr >= -1e-12, "抬脚高度不得为负"
        assert not (ll > 1e-9 and lr > 1e-9), "不得双脚同时抬起（会跳）"
    assert turn_stance(0.0)[0] < 1e-12 and turn_stance(1.0)[0] < 1e-12, "首尾不抬脚"
    # 换步施加：抬起侧确实抬高，支撑侧不动
    J = {"ank_l": np.array([0.0, 0.05, 0.1]), "ank_r": np.array([0.0, 0.05, -0.1]),
         "toe_l": np.array([0.09, 0.02, 0.1]), "toe_r": np.array([0.09, 0.02, -0.1]),
         "knee_l": np.array([0.0, 0.29, 0.1]), "knee_r": np.array([0.0, 0.29, -0.1]),
         "hip_l": np.array([0.0, 0.53, 0.09]), "hip_r": np.array([0.0, 0.53, -0.09])}
    # u=0.125 左脚摆动 / u=0.375 右脚摆动 / u=0.25 恰是双脚同时着地的换步瞬间
    m1 = [k for k in ("ank_l", "ank_r")
          if abs(turn_legs(J, 0.125)[k][1] - J[k][1]) > 1e-9]
    m2 = [k for k in ("ank_l", "ank_r")
          if abs(turn_legs(J, 0.375)[k][1] - J[k][1]) > 1e-9]
    assert len(m1) == 1 and len(m2) == 1, f"摆动期应只有一只脚在动 {m1} {m2}"
    assert m1 != m2, f"两次摆动必须换脚，实际都是 {m1}"
    assert turn_stance(0.25)[0] < 1e-9 and turn_stance(0.25)[1] < 1e-9, \
        "换步瞬间应双脚同时着地（真人 double support）"
    # 分段转向首尾回正
    t0, h0 = turn_torso(J, 0.0, 180.0)
    assert abs(t0) < 1e-9 and abs(h0) < 1e-9, "转身结束扭转必须回正"
    tm, hm = turn_torso(J, 0.5, 180.0)
    assert hm > tm > 0, "头部滞后应大于躯干滞后"
    print(f"  turn: 180°={d180:.3f}s  90°={turn_duration(90):.3f}s  "
          f"换步{TURN_STEPS}次  单帧最大{ max(dif):.3f}°")
    print("SELF_CHECK: PASS (turn)")
    return ok


if __name__ == "__main__":
    self_check()


@capability("turn", "转身: 骨盆优先, 脊柱延迟, 头最后 (NIH PMC)")
def _turn_cap(dur, t, yaw0=0.0, yaw1=180.0, **_kw):
    """转身能力（供能力表登记；门检只认名字，实现见 turn_yaw / turn_torso）"""
    u = 0.0 if dur <= 0 else max(0.0, min(1.0, t / dur))
    torso, head = turn_torso(None, u, yaw1 - yaw0)
    return {"yaw": turn_yaw(yaw0, yaw1, u), "torso": torso, "head": head}
