# -*- coding: utf-8 -*-
# 契约: proc/motion/creature/bird_fly
#   一句话: 鸟飞扑翼：三位置角 + 下扑/上举不对称 + 准定常叶素法气动（升力/推力由积分真算）
"""鸟飞：扑翼飞行（flapping flight）。

契约
  输入  t 秒；b 翼展（米）；m 体重（kg）；S 翼面积（m^2）；U 巡航速度（m/s）
  输出  {"J": {body, head, tail, shoulder_l/r, wrist_l/r, mid_l/r, tip_l/r}, "meta": {...}}
        非人形骨架 —— 鸟不是 21 关节人体骨架，返回翼与躯干点列（世界坐标米制，
        x 沿飞行方向、y 竖直、z 翼展侧向）。与 character 骨架不同构，不走
        capbridge 的 POSE 分流，由调用方直接消费。

设计要点（与项目其余能力的分界）
  这是本项目第一个**流体推进**能力。此前所有能力都是接触式推进（地面反作用力
  / 刚体接触冲量），鸟飞的升力与推力来自连续介质气动力，范式不同：
    - 力不是接触约束解出的，而是叶素法（BEM）沿翼展积分出来的
    - 机体竖直起伏不是写死的动画曲线，而是 m·ÿ = ΣF_y − m·g 积分出来的
  因此"下扑机身上升、上举机身下降"是**算出来的因果**，不是调出来的姿态。

判定判据（每条附出处）
  下扑时长 > 上举时长      down_frac=0.55 > 0.5            扑翼上下冲程不对称
  上举有效展长 < 下扑       fold=0.62（屈曲回收降阻）        上举气动不活跃
  下扑净推力 > 上举净推力   由 BEM 积分得出，非写死         下扑为 power phase
  下扑机身上升/上举下降     m·ÿ=ΣF_y−mg 积分，非写死        Ramakrishnananda & Wong 1999
  Strouhal 数 0.2~0.4      巡航最优 0.21（direct fliers）   Nudds/Taylor/Thomas 2004
  巡航配平 平均升力=mg      反解配平攻角                    定常水平飞行
  翼骨段长守恒             三段各恒 = semi/3                骨长守恒同款 IK 判据
  帧间无跳变               ——                               与项目其余能力同口径

依据
  Wu & Popović 2003, SIGGRAPH/TOG   翼拍参数优化 + 前向动力学 + PD 控制
  MDPI 扑翼运动学（ornithopter 实测）三位置角：扑动角 φ / 仰角 θ / 攻角 α
  RoboFalcon2.0 (PMC)              下扑=动力相产生升力推力；上举屈曲、气动不活跃
  BEM 叶素法                        f_L(r)=(ρ/2)c(r)u_r^2 C_L(α_r)
  Sane & Dickinson 翼型拟合          C_L=0.225+1.58sin(2.13α−7.2°)、
                                    C_D=1.92−1.55cos(2.04α−9.82°)
  Pennycuick 1996/2001              f=m^(3/8) g^(1/2) b^(−23/24) S^(−1/3) ρ^(−3/8)
  Nudds et al. 2004                 St=fA/U∈[0.2,0.4]，θ≈67b^(−0.24)，St=0.21
  Ramakrishnananda & Wong 1999      气动模型预测下扑上升、上举下降

模型边界（如实声明）
  准定常假设：忽略附加质量、尾迹捕获、旋转升力等非定常效应；忽略机身寄生阻力
  与尾翼配平。BEM 是扑翼气动的一阶估计，不是 CFD。
完整契约见 motion/character/__init__.py
"""

from __future__ import annotations

import math
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    __package__ = "motion.creature"

import numpy as np

from ..beat import capability

# 气动与翼骨几何的唯一真源在 .bird_aero（自本模块拆出，避免两处各写一份）。
from .bird_aero import (RHO_AIR, G, DOWN_FRAC, FOLD, N_ELEM, N_WING_SEG,
                        CD0_PROFILE, E_OSWALD, CL_MAX, stroke_angle_deg,
                        flapping_angle, is_downstroke, flapping_rate,
                        fold_factor, sweep_angle, wing_aero, trim_alpha,
                        _wing_points, _cl_coeff, _cd_coeff)

ST_DIRECT = 0.21         # 连续扑翼飞行者巡航 Strouhal 数（Nudds 2004）



def beat_freq_pennycuick(m, b, S, rho=RHO_AIR):
    """Pennycuick 扑翼频率律 f = m^(3/8) g^(1/2) b^(−23/24) S^(−1/3) ρ^(−3/8)。

    出处：Pennycuick 1996（32 种）修订版，J Exp Biol 2001 再拟合 47 种。
    """
    return (m ** (3.0 / 8.0)) * math.sqrt(G) * (b ** (-23.0 / 24.0)) \
        * (S ** (-1.0 / 3.0)) * (rho ** (-3.0 / 8.0))


def stroke_amplitude(b):
    """扑动振幅 A（米，翼尖峰峰值的半幅）A = b·sin(θ/2)，θ=67b^(−0.24)。"""
    return b * math.sin(math.radians(stroke_angle_deg(b)) / 2.0)


def strouhal(f, b, U):
    """St = f·A/U，A=b·sin(θ/2)。巡航高推进效率区间 0.2~0.4。"""
    return f * stroke_amplitude(b) / U


def cruise_speed(f, b, St=ST_DIRECT):
    """由 St 反解巡航速度 U = f·A/St。与鱼游同款 Strouhal 反解。"""
    return f * stroke_amplitude(b) / St


# ---- 三位置角（fold_factor / sweep_angle 唯一真源见 .bird_aero）----


def bird_flight_sim(m=1.0, b=1.2, S=0.2, U=None, alpha0_deg=None, alt0=8.0,
                    t_end=2.0, dt=1.0 / 240.0, rho=RHO_AIR, down_frac=DOWN_FRAC,
                    fold=FOLD):
    """前向动力学积分：m·ÿ = ΣF_y − m·g，机体竖直起伏由此**算出**。

    返回 dict：t 序列、y 高度序列、各时刻 (Fx,Fy)、下扑/上举相位标记。
    """
    f = beat_freq_pennycuick(m, b, S, rho)
    if U is None:
        U = cruise_speed(f, b, ST_DIRECT)
    if alpha0_deg is None:
        alpha0_deg = trim_alpha(f, U, b, S, m, rho)
    # 采样窗必须**精确**等于整数个翼拍周期。若用固定 dt 再 round，总时长与
    # n_cyc/f 会差约 0.7% 周期（实测），周期平均升力因此偏离 mg，机体高度
    # 出现 2m/2s 的虚假漂移。故反解 dt_eff = 1/(f·n_per) 使窗长精确闭合。
    n_cyc = max(1, int(math.ceil(t_end * f)))
    n_per = max(8, int(round(1.0 / f / dt)))
    dt_eff = 1.0 / (f * n_per)
    n = n_cyc * n_per
    ts, fxs, fys, downs, acc = [], [], [], [], []
    for i in range(n + 1):
        t = i * dt_eff
        fx, fy = wing_aero(t, f, U, b, S, alpha0_deg, rho, down_frac, fold)
        ts.append(t); fxs.append(fx); fys.append(fy)
        downs.append(is_downstroke(t, f, down_frac))
        acc.append((fy - m * G) / m)

    # 气动合力只依赖 t（不含机体寄生阻力，与 y/v 无关），故速度可解析：
    #   vy_i = vy0 + S_i，S_i = Σ_{j<i} a_j·dt（半隐式欧拉的速度增量）
    # 配平巡航的定义是"高度周期性波动、无净爬升"，即 vy 的周期均值为 0
    # ——据此**反解** vy0。若像普通积分那样取 vy0=0，vy 会带一个常数偏移，
    # 高度便线性漂移（实测 2m/2s 的假爬升），那不是物理而是初值没配平。
    acc = np.array(acc, dtype=float)
    S = np.concatenate(([0.0], np.cumsum(acc[:-1]) * dt_eff))
    k = max(1, min(n_per, len(S) - 1))
    vy0 = -float(np.mean(S[-k:]))
    vy_series = vy0 + S
    ys = list(alt0 + np.concatenate(
        ([0.0], np.cumsum(vy_series[1:] * dt_eff))))
    return {"t": np.array(ts), "y": np.array(ys), "fx": np.array(fxs),
            "fy": np.array(fys), "down": np.array(downs, dtype=bool),
            "f": f, "U": U, "alpha0_deg": alpha0_deg}


_CACHE = {}


def _trimmed(m, b, S, U, alt0, t_end, down_frac, fold):
    key = (m, b, S, U, alt0, t_end, down_frac, fold)
    if key not in _CACHE:
        _CACHE[key] = bird_flight_sim(m, b, S, U, alt0=alt0, t_end=t_end,
                                      down_frac=down_frac, fold=fold)
    return _CACHE[key]


def bird_fly(t, m=1.0, b=1.2, S=0.2, U=None, alt0=8.0, t_end=2.0,
             body_len=None, down_frac=DOWN_FRAC, fold=FOLD, sweep_deg=12.0):
    """单帧鸟骨架（世界坐标米制）。高度取自配平仿真的周期稳态解。"""
    sim = _trimmed(m, b, S, U, alt0, t_end, down_frac, fold)
    f, Uc = sim["f"], sim["U"]
    semi = b / 2.0
    if body_len is None:
        body_len = 0.35 * b

    x = Uc * t
    # 高度：取仿真中同相位的最近样本（周期稳态），避免纯函数无法积分
    T = 1.0 / f
    ys = sim["y"]
    n = len(ys)
    idx = int(round(((t / T) % 1.0) * (n - 1)))
    y = float(ys[min(idx, n - 1)])

    phi = flapping_angle(t, f, None, b, down_frac)
    th = sweep_angle(t, f, sweep_deg, down_frac)
    eff = fold_factor(t, f, fold, down_frac)

    cp, sp = math.cos(phi), math.sin(phi)
    ct, st = math.cos(th), math.sin(th)
    body = np.array([x, y, 0.0])
    head = body + np.array([0.42 * body_len, 0.10 * body_len, 0.0])
    tail = body + np.array([-0.45 * body_len, -0.02 * body_len, 0.0])

    J = {"body": tuple(body), "head": tuple(head), "tail": tuple(tail)}
    for side, sgn in (("l", -1.0), ("r", 1.0)):
        sh = body + np.array([0.06 * body_len, 0.05 * body_len, sgn * 0.11 * body_len])
        # 展向：先扑动（绕 x 轴 −φ）再扫掠（绕 y 轴 θ）
        e = np.array([cp * st, sp, cp * ct]) * sgn
        up = np.array([0.0, 1.0, 0.0])
        n_hat = up - float(np.dot(up, e)) * e
        nl = float(np.linalg.norm(n_hat))
        n_hat = n_hat / nl if nl > 1e-9 else np.array([0.0, 1.0, 0.0])
        wrist, mid, tip = _wing_points(sh, e, n_hat, semi, eff)
        J["shoulder_" + side] = tuple(sh)
        J["wrist_" + side] = tuple(wrist)
        J["mid_" + side] = tuple(mid)
        J["tip_" + side] = tuple(tip)
    return {"J": J, "meta": {"f": f, "U": Uc, "alpha0_deg": sim["alpha0_deg"],
                             "phi_deg": math.degrees(phi), "eff": eff,
                             "down": bool(is_downstroke(t, f, down_frac)),
                             "St": strouhal(f, b, Uc)}}


@capability("bird_fly", source="Wu & Popović 2003; Nudds et al. 2004; "
                               "Pennycuick 1996; Sane & Dickinson")
def _cap_bird_fly(t, params):
    p = params or {}
    return bird_fly(t, **{k: v for k, v in p.items()
                          if k in ("m", "b", "S", "U", "alt0", "t_end",
                                   "body_len", "down_frac", "fold", "sweep_deg")})


def self_check():
    """飞行自检：分四组（频率巡航 / 骨长守恒 / 气动因果 / 帧间采样）。"""
    from base.assertrun import Checker
    c = Checker("motion.creature.bird_fly")
    _sc_freq(c)
    _sc_bones(c)
    _sc_aero(c)
    _sc_frames(c)
    return not c.failed


def _sc_freq(c):
    m, b, S = 1.0, 1.2, 0.2
    f = beat_freq_pennycuick(m, b, S)
    T = 1.0 / f
    U = cruise_speed(f, b, ST_DIRECT)
    # --- 频率与巡航速度（银鸥 herring gull 量级）---
    m, b, S = 1.0, 1.2, 0.2
    f = beat_freq_pennycuick(m, b, S)
    c.chk("Pennycuick 频率落在银鸥量级 3~6Hz | f=%.4f" % f, 3.0 < f < 6.0,
          "Pennycuick 1996/2001：m=1.0,b=1.2,S=0.2 应约 4.2Hz")
    U = cruise_speed(f, b, ST_DIRECT)
    c.chk("St 反解巡航速度 8~16m/s | U=%.4f" % U, 8.0 < U < 16.0,
          "Nudds 2004：St=0.21，银鸥巡航约 10~13m/s")
    st = strouhal(f, b, U)
    c.chk("Strouhal 数=0.21（direct fliers）| St=%.6f" % st, abs(st - ST_DIRECT) < 1e-9,
          "Nudds/Taylor/Thomas 2004 Proc R Soc B：巡航 St 收敛于 0.21")
    c.chk("扑动幅角 θ=67b^(−0.24) | θ=%.4f°" % stroke_angle_deg(b),
          abs(stroke_angle_deg(b) - 67.0 * b ** (-0.24)) < 1e-12,
          "Nudds 2004：θ≈67b^(−0.24)")

    # --- 下扑/上举不对称 ---
    c.chk("下扑时长 > 上举时长 | down_frac=%.2f" % DOWN_FRAC, DOWN_FRAC > 0.5,
          "上下冲程不对称：下扑为动力相，占时更长")
    # 上举段从 down_frac·T 起到 T，其中点是 (down_frac + (1−down_frac)/2)·T
    fold_mid = fold_factor((DOWN_FRAC + (1.0 - DOWN_FRAC) * 0.5) / f, f)
    c.chk("上举中段有效展长收缩到 FOLD | eff=%.4f" % fold_mid,
          abs(fold_mid - FOLD) < 1e-9,
          "RoboFalcon2.0 (PMC)：上举屈曲回收、气动不活跃")
    c.chk("下扑段完全伸展 eff=1", abs(fold_factor(0.1 / f, f) - 1.0) < 1e-12,
          "下扑翼全展以产生升力与推力")

    # --- 扑动角 C1 连续（周期衔接无速度突跳）---
    T = 1.0 / f
    eps = 1e-6
    r0 = flapping_rate(0.0, f)
    r1 = flapping_rate(T - eps, f)
    c.chk("扑动角速率在周期衔接处连续 | Δ=%.3e" % abs(r0 - r1), abs(r0 - r1) < 1e-3,
          "两段余弦端点导数均为 0 → C1 连续")


def _sc_bones(c):
    m, b, S = 1.0, 1.2, 0.2
    f = beat_freq_pennycuick(m, b, S)
    T = 1.0 / f
    U = cruise_speed(f, b, ST_DIRECT)
    # --- 翼骨段长守恒 ---
    semi = b / 2.0
    worst = 0.0
    for tt in [i * T / 24 for i in range(24)]:
        J = bird_fly(tt, m=m, b=b, S=S)["J"]
        for side in ("l", "r"):
            segs = [("shoulder_" + side, "wrist_" + side),
                    ("wrist_" + side, "mid_" + side),
                    ("mid_" + side, "tip_" + side)]
            for a0, a1 in segs:
                d = np.linalg.norm(np.array(J[a1]) - np.array(J[a0]))
                worst = max(worst, abs(d - semi / N_WING_SEG))
    c.chk("翼骨三段等长守恒 | 最大偏差 %.3e" % worst, worst < 1e-9,
          "骨长守恒同款 IK 判据：段长恒 = semi/3")


def _sc_aero(c):
    m, b, S = 1.0, 1.2, 0.2
    sim = bird_flight_sim(m=m, b=b, S=S, t_end=2.0)
    # --- 气动因果：下扑推力/升力主导（由 BEM 积分得出，非写死）---
    sim = bird_flight_sim(m=m, b=b, S=S, t_end=2.0)
    dn, up = sim["down"], ~sim["down"]
    fx_d = float(np.mean(sim["fx"][dn]))
    fx_u = float(np.mean(sim["fx"][up]))
    fy_d = float(np.mean(sim["fy"][dn]))
    fy_u = float(np.mean(sim["fy"][up]))
    c.chk("下扑净推力 > 上举净推力 | %.4f vs %.4f" % (fx_d, fx_u), fx_d > fx_u,
          "BEM 积分：下扑 v_f<0 使升力水平分量成推力（power phase）")
    c.chk("下扑净升力 > 上举净升力 | %.4f vs %.4f" % (fy_d, fy_u), fy_d > fy_u,
          "上举屈曲+负迎角增量 → 气动弱")

    # --- 气动因果：下扑机身上升、上举机身下降（积分得出）---
    # 取仿真中段（避开起转瞬态），按相位分组比较竖直速度
    n = len(sim["t"])
    i0 = int(n * 0.4)
    sl = slice(i0, n)
    yy = sim["y"][sl]
    dd = sim["down"][sl]
    dy = np.diff(yy)
    dd_mid = dd[:-1]
    rise_down = float(np.mean(dy[dd_mid])) if dd_mid.any() else 0.0
    rise_up = float(np.mean(dy[~dd_mid])) if (~dd_mid).any() else 0.0
    c.chk("下扑机身上升、上举机身下降 | Δy_down=%.3e Δy_up=%.3e"
          % (rise_down, rise_up), rise_down > rise_up,
          "Ramakrishnananda & Wong 1999：气动模型预测下扑升、上举降")

    # --- 巡航配平：平均升力 = mg ---
    mean_fy = float(np.mean(sim["fy"]))
    c.chk("周期平均升力 = mg | %.4f vs %.4f" % (mean_fy, m * G),
          abs(mean_fy - m * G) < 0.05 * m * G,
          "定常水平飞行配平（trim_alpha 反解攻角，5% 容差）")


def _sc_frames(c):
    m, b, S = 1.0, 1.2, 0.2
    f = beat_freq_pennycuick(m, b, S)
    T = 1.0 / f
    U = cruise_speed(f, b, ST_DIRECT)
    # --- 帧间无跳变 ---
    mj = 0.0
    prev = None
    for i in range(120):
        J = bird_fly(i / 60.0, m=m, b=b, S=S)["J"]
        cur = np.array([J["tip_r"], J["tip_l"], J["body"]])
        if prev is not None:
            mj = max(mj, float(np.max(np.abs(cur - prev))))
        prev = cur
    # 巡航 12.6m/s 的机体每帧本就前进 U/fps≈0.21m，人形骨架那个 0.05m/帧
    # 口径在这里不适用（那是 1.4m/s 步行的尺度）。改为与**解析峰速**自洽：
    # 翼尖对机体的相对峰速 = semi·φ̇_max，帧间位移不应超过 (U + v_tip)/fps。
    phi_max = max(abs(flapping_rate(i * T / 2000.0, f)) for i in range(2000))
    v_tip = (b / 2.0) * phi_max
    lim = (U + v_tip) / 60.0 * 1.10
    c.chk("翼尖帧间位移与解析峰速自洽 | %.5f ≤ %.5f m/帧" % (mj, lim), mj <= lim,
          "帧间位移上界 (U + semi·φ̇_max)/fps·110%，超出即为积分/相位突跳")
    n_spc = 60.0 / f
    c.chk("扑动采样密度 %.2f 样本/周期 ≥ 10" % n_spc, n_spc >= 10.0,
          "Nyquist–Shannon：周期运动每周期采样不足会产生走样（车轮/频闪效应）")

    return not c.failed
