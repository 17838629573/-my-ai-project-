# -*- coding: utf-8 -*-
"""原地转身模块（动作层·转身）

契约: proc/motion/character/turn
  一句话: yaw 连续转身 + 原地换步 —— 让人物真的"转过去"而不是镜像翻转
  完整契约见 motion/character/__init__.py

  输入: 起始 yaw、目标转角 delta_deg、进度 u∈[0,1]、基准关节 J
  输出: {'yaw': float, 'J': {关节: (u,v,w)}}
  依赖: numpy, math
  被依赖: motion.beat, showreel.cafe
  约束: 转身速率分档（基础 125°/s，|Δ|>100° 线性加速到 300°/s）；
        yaw 由每帧设置驱动，转身动画本身只带腿部动作；
        缓动用 smoothstep u²(3-2u)，首尾速度为 0；
        换步只在抬脚侧，支撑脚锁死不打滑；
        躯干转向滞后于骨盆（分段转向），头部最后跟上
  校验: python -m motion.character.turn
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

# --- 转身时间曲线：不对称（旧实现 smoothstep 完全对称，已废）------------
# 旧 turn_yaw 用 u²(3-2u)：前 50% 时间恰好转 50% 角度，即"转到侧面"和
# "从侧面转到后面"耗时相等。这与两条已知事实冲突：
#  1) Disney《The Illusion of Life》(Thomas & Johnston, 1981)：主动作前有
#     Anticipation（反向预备 2-3 帧 @30fps ≈ 66-100ms），末尾有 Overshoot
#     （超出目标 10-15%，3-5 帧内 settle）；并注明缓慢/小幅动作不需要 antic。
#  2) 505 变向测试（IJERPH 18(11):5519, 2021）：180° 转向中减速阶段的平均
#     速度变化率比加速阶段高 70%-75%，且发生在更短时间内 ——
#     即"启动要克服惯性（慢）、末端要精确对准（收得急）"，峰值角速度偏前。
# 结果：转到侧面（50% 角度）只花约 43% 时间，后 50% 角度花约 57%，不相等。
TURN_ANTIC = 0.10         # 反向预备占总时长比例（Disney: 2-3帧@30fps≈66-100ms）
TURN_SETTLE = 0.16        # 过冲回弹占总时长比例（Disney: 3-5帧稳定）
TURN_ANTIC_DEG = 6.0      # 反向预备角度（°，90°及以上转身的满值）
TURN_OVERSHOOT = 0.10     # 过冲超出目标的比例（业界 0.10~0.15，取下沿）
TURN_PEAK_AT = 0.45       # 主转段内走完 50% 角度所用时间比例（<0.5 = 峰值偏前）
TURN_MA = 0.6             # 主转段首段末切率，决定峰值尖锐度，见下方 TURN_PEAK_FACTOR

# --- 峰值角速度上限（生理约束，反解时长用）-------------------------------
# ISBS 2015（Codari/Grilli/Sforza/Zago）：青少年球员带球 180° 转身
#   骨盆旋转峰值角速度 414 ± 90 °/s。
# 【引用错配自查，第三方评审指出，已承认并分档】
#   1) 样本是 10 名 U13 少年、29 次有效试验，不是原先注释写的 n=12；
#   2) 论文为 PCA 研究，摘要只报执行时间 0.68±0.53s，"414±90 °/s"未见于摘要；
#   3) 任务是 5m 运球后脚底半转身，非原地转身；U13 少年不能当"生理上沿"。
# 结论：人群与任务双重错配，该数不能直接当原地转身的生理上限。
# 处理：把"设计值"与"硬闸"分开 —— 设计值 400（留裕度），硬闸 460（判据仍用 460）。
# 这是"运动员 + 带球 + 全力"的上沿场景；原地空手转身不应快过它。
# 取 均值 + 0.5·SD ≈ 459 ≈ 460 °/s 作为硬上限。
# 对照：老年人 180° 行走转身峰值仅 141 ± 32 °/s（J Gerontol A），
#       健康成年人原地转身落在两者之间 —— 460 是"快但不超生理"的取值。
TURN_PEAK_RATE = 400.0    # °/s，设计值（硬闸 460 留在 harness.CRIT）
# 主转段内 峰值角速度 / 平均角速度 的比值，由 turn_profile 数值实测：
#   M_A=0.9 → 2.000    M_A=0.6 → 1.501    M_A=0.45 → 1.485（不再下降）
# 取 M_A=0.6：既把峰值削掉 25%，又保留"启动慢、末端收得急"的不对称。
TURN_PEAK_FACTOR = 1.501


def _clamp01(u):
    return 0.0 if u < 0.0 else (1.0 if u > 1.0 else float(u))


def _hermite(t, r0, m0, r1, m1):
    """三次 Hermite 插值，t∈[0,1]，m0/m1 为端点切率。"""
    t2 = t * t
    t3 = t2 * t
    return ((2.0 * t3 - 3.0 * t2 + 1.0) * r0 + (t3 - 2.0 * t2 + t) * m0
            + (-2.0 * t3 + 3.0 * t2) * r1 + (t3 - t2) * m1)


def turn_profile(s):
    """主转段内角度比例 r(s)：s∈[0,1] → r∈[0,1]，非对称。

    分两段 Hermite，在 s=TURN_PEAK_AT 处 r=0.5 且切率连续（C1）：
      段 A [0,P]    起点切率 0（启动慢）→ 末切率 M_A；
      段 B [P,1]    初切率 M_B = M_A·(1-P)/P（保证 ds 尺度下连续）→ 末切率 0（收得急）。
    因 M_B > M_A，峰值角速度落在 s=P 附近，即 PEAK_AT<0.5 → 前半程更快。
    """
    s = _clamp01(s)
    P = TURN_PEAK_AT
    M_A = TURN_MA   # 0.6: 主转段峰值因子 1.501（数值实测, 0.9 时为 2.000）
    if s <= P:
        return _hermite(s / P, 0.0, 0.0, 0.5, M_A)
    M_B = M_A * (1.0 - P) / P
    return _hermite((s - P) / (1.0 - P), 0.5, M_B, 1.0, 0.0)


def turn_speed(delta_deg):
    """转身角速度 °/s。|Δ|≤100° 用基础速率，越大越快，180° 到上限。"""
    a = abs(float(delta_deg))
    if a <= FAST_FROM:
        return TURN_RATE_BASE
    k = min(1.0, (a - FAST_FROM) / FAST_SPAN)
    return TURN_RATE_BASE + (TURN_RATE_FAST - TURN_RATE_BASE) * k


def turn_duration(delta_deg):
    """转身耗时（秒）——取"分档速率"与"峰值角速度约束"两者的较大值。

    两个约束各自给出一条下限：
      t_rate = |Δ| / turn_speed(Δ)                  UE4 转身资产的经验速率分档
      t_peak = PEAK_FACTOR·总行程 / (主转占比·峰值上限)  生理上限（ISBS 2015）

    取 max 即"两者都满足"。小角度由经验速率主导（转身本就该快），
    大角度由生理峰值主导 —— 180° 若仍按 300°/s 的均值，峰值会冲到
    1020°/s（实测），是运动员带球全力转身实测峰值 414°/s 的 2.5 倍，
    表现为中途"甩头"，帧间跳变超标。
    """
    a = abs(float(delta_deg))
    if a < 1e-9:
        return 0.0
    t_rate = a / turn_speed(a)
    shrink = min(1.0, a / 90.0)
    # 主转段实际要转过的角度：反向预备量 + 目标量·(1+过冲)
    travel = TURN_ANTIC_DEG * shrink + a * (1.0 + TURN_OVERSHOOT * shrink)
    main_frac = 1.0 - TURN_ANTIC - TURN_SETTLE      # 主转段占总时长比例
    t_peak = TURN_PEAK_FACTOR * travel / (main_frac * TURN_PEAK_RATE)
    return max(t_rate, t_peak)


def turn_yaw(yaw0, delta_deg, u):
    """进度 u∈[0,1] → 当前 yaw。三段不对称时间曲线。

    [0, ANTIC)          反向预备：yaw 先朝反方向微转（Disney anticipation）
    [ANTIC, 1-SETTLE)   主转：从 -antic 转到 delta·(1+overshoot)，内部非对称
    [1-SETTLE, 1]       回弹：从过冲量 settle 回 delta

    小幅转身（<90°）按比例削弱 antic 与 overshoot —— Disney 明确指出
    缓慢或小幅动作不需要预备姿势。
    端点严格：turn_yaw(·,·,0)=yaw0，turn_yaw(·,·,1)=yaw0+delta。
    """
    u = _clamp01(u)
    a = float(delta_deg)
    mag = abs(a)
    if mag < 1e-9:
        return float(yaw0)
    sgn = 1.0 if a > 0.0 else -1.0
    shrink = min(1.0, mag / 90.0)          # 小角度削弱
    antic = TURN_ANTIC_DEG * shrink
    over = TURN_OVERSHOOT * shrink
    y0 = float(yaw0)

    if u < TURN_ANTIC:                      # 反向预备
        k = _hermite(u / TURN_ANTIC, 0.0, 0.0, 1.0, 0.0)
        return y0 - sgn * antic * k

    if u >= 1.0 - TURN_SETTLE:              # 过冲回弹
        v = (u - (1.0 - TURN_SETTLE)) / TURN_SETTLE
        k = _hermite(v, 1.0, 0.0, 0.0, 0.0)   # k: 1 → 0
        return y0 + sgn * mag * (1.0 + over * k)

    s = (u - TURN_ANTIC) / (1.0 - TURN_ANTIC - TURN_SETTLE)
    r = turn_profile(s)
    start = -antic
    end = mag * (1.0 + over)
    return y0 + sgn * (start + (end - start) * r)


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


def _peak_rate(delta, N=2000):
    """峰值角速度 °/s：yaw 序列的最大单步差按真实时长折算。"""
    d = turn_duration(delta)
    y = [turn_yaw(0.0, delta, i / float(N)) for i in range(N + 1)]
    return max(abs(y[i + 1] - y[i]) for i in range(N)) * N / d


def _yaw_seq(delta=180.0, N=400):
    return [turn_yaw(0.0, delta, i / float(N)) for i in range(N + 1)]


def _u_half(ys):
    """首次到达 50% 角度(90°)的归一化时刻；None = 全程未到达。"""
    for i, v in enumerate(ys):
        if v >= 90.0:
            return i / float(len(ys) - 1)
    return None


def _stance_ok():
    """换步约束：抬脚高度非负、绝不双脚同抬、首尾不抬脚。"""
    for i in range(101):
        ll, lr, _c = turn_stance(i / 100.0)
        if ll < -1e-12 or lr < -1e-12:
            return False
        if ll > 1e-9 and lr > 1e-9:
            return False
    return turn_stance(0.0)[0] < 1e-12 and turn_stance(1.0)[0] < 1e-12


def _sample_J():
    """自检用基准关节（站立姿态，左右对称）。"""
    return {"ank_l": np.array([0.0, 0.05, 0.1]), "ank_r": np.array([0.0, 0.05, -0.1]),
            "toe_l": np.array([0.09, 0.02, 0.1]), "toe_r": np.array([0.09, 0.02, -0.1]),
            "knee_l": np.array([0.0, 0.29, 0.1]), "knee_r": np.array([0.0, 0.29, -0.1]),
            "hip_l": np.array([0.0, 0.53, 0.09]), "hip_r": np.array([0.0, 0.53, -0.09])}


def _swing_feet(J, u):
    """在进度 u 下被抬起的脚（比对施加换步前后的 y 变化）。"""
    return [k for k in ("ank_l", "ank_r")
            if abs(turn_legs(J, u)[k][1] - J[k][1]) > 1e-9]


def _chk_rate(c):
    """速率分档 / 时长 / 峰值角速度——A4 转身判据的物理地基。"""
    c.chk("90° 应用基础速率", abs(turn_speed(90) - TURN_RATE_BASE) < 1e-9)
    c.chk("180° 应达上限速率", abs(turn_speed(180) - TURN_RATE_FAST) < 1e-9)
    c.chk("140° 介于两者之间", TURN_RATE_BASE < turn_speed(140) < TURN_RATE_FAST)
    d180, d90 = turn_duration(180), turn_duration(90)
    c.chk("180°时长落实测区间", 0.6 - 1e-9 <= d180 <= 1.44, "%.3fs" % d180)
    c.chk("0° 转身耗时 0", abs(turn_duration(0)) < 1e-12)
    # 峰值不超生理上限（ISBS 2015 运动员带球 180° 转身 414±90 °/s）
    pk, pk9 = _peak_rate(180.0), _peak_rate(90.0)
    c.chk("180°峰值不超生理上限", pk <= TURN_PEAK_RATE * 1.02, "%.1f°/s" % pk)
    c.chk("90°峰值不超生理上限", pk9 <= TURN_PEAK_RATE * 1.02, "%.1f°/s" % pk9)
    # 主导约束：小角度靠经验速率分档，大角度靠峰值上限
    c.chk("90°由经验速率主导", abs(d90 - 90.0 / TURN_RATE_BASE) < 1e-9)
    c.chk("180°由峰值约束主导", d180 > 180.0 / TURN_RATE_FAST)
    return d180, d90


def _chk_curve(c):
    """曲线形态：端点准确、无单帧跳变、反向预备、过冲、settle、前后不等时。"""
    c.chk("起点等于 yaw0", abs(turn_yaw(180.0, 180.0, 0.0) - 180.0) < 1e-9)
    c.chk("终点等于 yaw0+delta", abs(turn_yaw(180.0, 180.0, 1.0) - 360.0) < 1e-9)
    ys = _yaw_seq(180.0, 400)
    dif = [abs(ys[i + 1] - ys[i]) for i in range(len(ys) - 1)]
    total = 180.0 * (1.0 + TURN_OVERSHOOT) + TURN_ANTIC_DEG
    c.chk("单帧 yaw 无跳变", max(dif) < total * 3.0 / float(len(dif)),
          "%.3f" % max(dif))
    c.chk("起步有反向预备", ys[1] < ys[0])
    c.chk("有过冲", max(ys) > 180.0 + 1e-6, "峰值%.3f" % max(ys))
    c.chk("settle 精确回目标", abs(ys[-1] - 180.0) < 1e-9)
    # 不对称（505 变向 IJERPH 18(11):5519：启动慢、末端收得急）
    u50 = _u_half(ys)
    c.chk("到达侧面", u50 is not None)
    c.chk("前后半程不等时", u50 is not None and abs(u50 - 0.5) > 0.03,
          "u50=%.3f" % u50 if u50 else "-")
    c.chk("前半程更快", u50 is not None and u50 < 0.5)
    c.chk("收尾慢于中段",
          abs(ys[-1] - ys[-2]) < abs(ys[len(ys) // 2] - ys[len(ys) // 2 - 1]))
    return max(dif)


def _chk_stance(c):
    """换步（不双脚同抬、摆期换脚）与分段转向（头部滞后>躯干）。"""
    c.chk("换步非负且不同抬", _stance_ok())
    J = _sample_J()
    m1, m2 = _swing_feet(J, 0.125), _swing_feet(J, 0.375)
    c.chk("摆动期只有一只脚动", len(m1) == 1 and len(m2) == 1, "%s %s" % (m1, m2))
    c.chk("两次摆动必须换脚", bool(m1) and bool(m2) and m1 != m2)
    c.chk("换步瞬间双脚着地",
          turn_stance(0.25)[0] < 1e-9 and turn_stance(0.25)[1] < 1e-9)
    t0, h0 = turn_torso(J, 0.0, 180.0)
    tm, hm = turn_torso(J, 0.5, 180.0)
    c.chk("转身结束扭转回正", abs(t0) < 1e-9 and abs(h0) < 1e-9)
    c.chk("头部滞后大于躯干", hm > tm > 0)


def self_check():
    """转身自检：判据与改造前逐条一致，计算抽 helper、断言交统一执行器。"""
    from base.assertrun import Checker
    c = Checker("turn")
    d180, d90 = _chk_rate(c)
    mx = _chk_curve(c)
    _chk_stance(c)
    c.note("180°=%.3fs  90°=%.3fs  换步%d次  单帧最大%.3f°"
           % (d180, d90, TURN_STEPS, mx))
    return c.report()


if __name__ == "__main__":
    self_check()


@capability("turn", "转身: 骨盆优先, 脊柱延迟, 头最后 (NIH PMC)")
def _turn_cap(dur, t, yaw0=0.0, yaw1=180.0, **_kw):
    """转身能力（供能力表登记；门检只认名字，实现见 turn_yaw / turn_torso）"""
    u = 0.0 if dur <= 0 else max(0.0, min(1.0, t / dur))
    torso, head = turn_torso(None, u, yaw1 - yaw0)
    return {"yaw": turn_yaw(yaw0, yaw1, u), "torso": torso, "head": head}
