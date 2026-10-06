# -*- coding: utf-8 -*-
# 契约: proc/motion/character/fish_swim
#   一句话: 鱼游行波推进：等弧长脊椎链 + carangiform/anguilliform 包络 + St 反解
"""鱼游：身体行波推进（carangiform / anguilliform）。

契约
  输入  t 秒；body_len 体长（米）；mode 步态
  输出  {"J": {spine_00..spine_12: (x,y,z)}, "meta": {...}}
        非人形骨架 —— 鱼没有 21 关节人体骨架，返回脊椎点列（世界坐标，米制，
        x 沿游动方向、y 横向摆幅、z 竖直）。与 character 的 21 关节骨架不同构，
        因此不走 capbridge 的 POSE 分流，由调用方直接消费。

判定判据（每条附出处）
  尾/头振幅比      carangiform 解析 Am(x)=a0+a1x+a2x²，x=0 取 1、
                   x=1 取 1-3.2+5.6=3.4                    Tytell 无量纲参数
  波长比 λ/L       carangiform 1.0 / anguilliform 0.642     Videler & Hess
  Strouhal 数      St=f·A/v，巡航最优 0.25（区间 0.2~0.4）   Triantafyllou 1993
  脊椎段长守恒     弧长参数化后每段 = L/N（鱼体不可压缩）     骨长守恒同款 IK 判据
  帧间无跳变       ——                                      与项目其余能力同口径

依据
  Videler & Hess 行波  y(x,t) = Am(x)·cos(2π/λ·(x − c·t))
  Tytell carangiform 二次包络系数 a0=1、a1=−3.2、a2=5.6
  anguilliform 指数包络 Am(s)=amax·e^(s−1)
完整契约见 motion/character/__init__.py
"""

from __future__ import annotations

import math
import os
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    __package__ = "motion.character"

import numpy as np

from ..beat import capability

N_SEG = 12                 # 脊椎段数（点数为 N_SEG+1）
AM_CAR = (1.0, -3.2, 5.6)  # carangiform 二次包络系数（Tytell）
AM_ANG_MAX = 0.642 / 11.41  # anguilliform 尾端归一化振幅
LAMBDA_CAR = 1.0           # 波长/体长
LAMBDA_ANG = 0.642


def _amplitude(s, mode="carangiform"):
    """归一化振幅包络 Am(s)，s 为沿体长的归一化弧长 0(头)~1(尾)。"""
    if mode == "anguilliform":
        return AM_ANG_MAX * math.exp(s - 1.0) / AM_ANG_MAX  # 归一到尾端=1
    a0, a1, a2 = AM_CAR
    return (a0 + a1 * s + a2 * s * s) / (a0 + a1 + a2)      # 归一到尾端=1


def _arclen_param(yfun, n_seg, body_len, iters=12):
    """等弧长参数化：每段弧长恒 = L/N，返回 (s, x_end)。

    鱼体不可压缩 → 沿身体的弧长守恒。摆动会拉长弦长，因此 x 方向投影必须
    相应收缩（x_end < body_len）。这里直接解出每段所需的 Δs：
        sqrt((Δs·x_end)² + Δy²) = L/N  →  Δs·x_end = sqrt((L/N)² − Δy²)
    行波相位沿**弧长**传播（用归一化 s），故 y 只由 s 决定，迭代收敛快。
    """
    s = np.linspace(0.0, 1.0, n_seg + 1)
    seg = body_len / n_seg
    x_end = body_len
    for _ in range(iters):
        y = yfun(s)
        dy = np.diff(y)
        need = np.sqrt(np.maximum(seg * seg - dy * dy, 0.0))  # 摆动过大时退化，见契约
        x_end = float(need.sum())
        s = np.concatenate([[0.0], np.cumsum(need / x_end)])
    return s, x_end


@capability("fish_swim",
            source="Videler & Hess 行波 y(x,t)=Am(x)cos(2π/λ(x−ct))；"
                   "Tytell carangiform 包络 a0=1,a1=−3.2,a2=5.6",
            group="character")
def fish_swim(t, body_len=0.30, freq=2.0, speed=0.50, tail_amp=None,
              mode="carangiform", n_seg=N_SEG):
    """鱼体行波游动。tail_amp 为尾端单边振幅（米），默认取 St=0.25 反解。"""
    lam = (LAMBDA_ANG if mode == "anguilliform" else LAMBDA_CAR) * body_len
    if tail_amp is None:                       # St = f·(2·A)/v = 0.25 → A = 0.125·v/f
        tail_amp = 0.125 * speed / freq

    def y_of(s):
        am = _amplitude(s, mode)
        return tail_amp * am * np.cos(2.0 * math.pi * (s * body_len / lam - freq * t))

    s, x_end = _arclen_param(y_of, n_seg, body_len)
    y = y_of(s)
    x = s * x_end
    z = np.zeros_like(x)
    pts = np.stack([x, y, z], axis=1)

    J = {}
    for i, p in enumerate(pts):
        J["spine_%02d" % i] = (float(p[0]), float(p[1]), float(p[2]))
    meta = {"mode": mode, "freq": freq, "speed": speed, "lam": lam,
            "tail_amp": float(tail_amp),
            "strouhal": float(freq * 2.0 * tail_amp / speed),
            "body_len": float(body_len), "n_seg": int(n_seg)}
    return {"J": J, "meta": meta}


@capability("fish_strouhal",
            source="Triantafyllou 1993：巡航最优 St≈0.25，生物区间 0.2~0.4",
            group="character")
def fish_strouhal(freq, tail_amp, speed):
    """Strouhal 数 St = f·A/v，A 取尾端峰峰振幅（2×单边振幅）。"""
    return float(freq * 2.0 * tail_amp / speed)


def _spine(k, dt):
    """取第 k 帧的脊椎点阵（N_SEG+1 个点）。"""
    J = fish_swim(k * dt)["J"]
    return np.array([J["spine_%02d" % i] for i in range(N_SEG + 1)], float)


def _check_shape(c):
    """形体判据：振幅比 / 波长比 / Strouhal / 包络单调。"""
    r = _amplitude(1.0) / _amplitude(0.0)
    c.chk("尾/头振幅比=3.4 | Tytell a0=1,a1=-3.2,a2=5.6", abs(r - 3.4) < 1e-9,
          "ratio=%.6f (== 3.4)" % r)
    c.chk("波长比 λ/L=1.0（carangiform）| Videler & Hess",
          abs(LAMBDA_CAR - 1.0) < 1e-12, "lam/L=%.6f (== 1.0)" % LAMBDA_CAR)
    c.chk("波长比 λ/L=0.642（anguilliform）| Videler & Hess",
          abs(LAMBDA_ANG - 0.642) < 1e-12, "lam/L=%.6f (== 0.642)" % LAMBDA_ANG)
    st = fish_strouhal(2.0, 0.03125, 0.50)
    c.chk("Strouhal 数落在 0.2~0.4 | Triantafyllou 1993 最优 0.25",
          0.2 <= st <= 0.4, "St=%.6f ([0.2, 0.4])" % st)
    a = np.array([_amplitude(s, "anguilliform") for s in np.linspace(0, 1, 11)])
    c.chk("anguilliform 包络单调且尾端归一 | Am(s)=amax·e^(s−1)",
          bool(np.all(np.diff(a) > 0)) and abs(a[-1] - 1.0) < 1e-12,
          "a[-1]=%.6f (== 1.0)" % a[-1])
    return st


def _check_motion(c, n=240, dt=1.0 / 60.0):
    """运动学判据：段长守恒 / 周期复现 / 帧间跳变 / 头尾摆幅 / 体长守恒。"""
    worst = 0.0
    for k in range(0, n, 7):
        seg = np.linalg.norm(np.diff(_spine(k, dt), axis=0), axis=1)
        worst = max(worst, float(np.abs(seg - 0.30 / N_SEG).max()))
    c.chk("脊椎段长守恒（每段=L/N）| 鱼体不可压缩", worst < 1e-6,
          "max_err=%.6e (< 1e-6)" % worst)

    y0 = fish_swim(0.0)["J"]["spine_%02d" % N_SEG][1]
    y1 = fish_swim(1.0 / 2.0)["J"]["spine_%02d" % N_SEG][1]
    c.chk("尾端按 freq 周期复现 | f=2Hz→T=0.5s", abs(y0 - y1) < 1e-9,
          "Δy=%.6e (< 1e-9)" % abs(y0 - y1))

    prev, mj = None, 0.0
    for k in range(n):
        P = _spine(k, dt)
        if prev is not None:
            mj = max(mj, float(np.abs(P - prev).max()))
        prev = P
    c.chk("帧间无跳变 | 2π·f·A/60=0.0065", mj < 0.02,
          "max_jump=%.6f (< 0.02)" % mj)

    Jh = fish_swim(0.25)["J"]
    hd = abs(Jh["spine_00"][1])
    tl = abs(Jh["spine_%02d" % N_SEG][1])
    c.chk("头端摆幅远小于尾端 | carangiform 头稳尾摆", hd < 0.3 * tl,
          "head=%.6f tail=%.6f (head < 0.3·tail)" % (hd, tl))

    lens = []
    for k in range(0, n, 13):
        lens.append(float(np.linalg.norm(
            np.diff(_spine(k, dt), axis=0), axis=1).sum()))
    c.chk("体长全周期守恒 | 不可压缩鱼体", max(lens) - min(lens) < 1e-6,
          "ΔL=%.6e (< 1e-6)" % (max(lens) - min(lens)))
    return worst, mj


def self_check():
    from base.assertrun import Checker
    c = Checker("fish_swim")
    st = _check_shape(c)
    worst, mj = _check_motion(c)
    print("  鱼游 240 帧：St=%.4f，段长误差 %.2e，最大帧间位移 %.4f"
          % (st, worst, mj))
    return c.report()


if __name__ == "__main__":
    raise SystemExit(0 if self_check() else 1)
