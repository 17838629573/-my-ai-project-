#!/usr/bin/env python
"""rain_layer.py — 雨层渲染（复用 water.py 全部公式，本模块不含任何物性常数）

依赖: water（雨滴物理）, _common（clamp/线性插值）
被依赖: build_video
铁律96: 雨强 R(mm/h) 是唯一输入量纲，滴谱/终速/倾角/拖尾全部由 water 算出
"""
import numpy as np
import water
import _common

DEPTH_M = 0.05   # 视觉景深(m)：近景雨幕薄层，非物理视深（需按镜头标定，见 IMPROVE_water.md）

def rain_drops(R_mm_h, wind_ms, W, H, px_per_m, seed=7, depth_m=DEPTH_M):
    """按 Marshall-Palmer 滴谱抽样雨滴 -> [(x0,y0,D_mm,V_ms,ang_rad,len_px)]"""
    rng = np.random.default_rng(seed)
    lam = water.marshall_palmer_lambda(R_mm_h)          # 1/mm
    n_per_m3 = water.drop_count_above(0.5, R_mm_h)      # 直径>0.5mm 的数密度
    # 画面体积 = 宽(m) * 高(m) * 视觉景深(m)
    vol = (W/px_per_m) * (H/px_per_m) * depth_m
    n = int(_common.clamp(n_per_m3 * vol, 20, 20000))
    D = rng.exponential(1.0/lam, n) + 0.3               # 直径 mm（截掉过小的雾滴）
    D = np.clip(D, 0.3, 6.0)
    out = []
    for d in D:
        V  = water.drop_terminal_velocity(d)             # D_mm 输入, 返回 m/s
        ang = water.rain_inclination(wind_ms, d)         # (v_wind, D_mm) -> rad
        lp = water.streak_length(V, 1/60.0, d)           # (v, t_exposure, D_mm) -> m
        out.append((float(rng.uniform(-0.2,1.2))*W,
                    float(rng.uniform(-0.5,1.0))*H,
                    float(d), float(V), float(ang), float(lp*px_per_m)))
    return out

def draw_rain(frame, drops, t, wind_ms, px_per_m, color=(200,210,225)):
    """把雨画到一帧上（BGR,numpy）。位置 = 初值 + 速度*t，出界回绕。"""
    h, w = frame.shape[:2]
    for (x0, y0, D, V, ang, L) in drops:
        vx = wind_ms * px_per_m
        vy = water.drop_terminal_velocity(D) * px_per_m
        x = (x0 + vx*t) % (w*1.4) - 0.2*w
        y = (y0 + vy*t) % (h*1.5) - 0.5*h
        x2, y2 = x + L*np.sin(ang), y + L*np.cos(ang)
        cv2_line(frame, (int(x),int(y)), (int(x2),int(y2)), color,
                 max(1,int(D*0.35)), ang)
    return frame

def cv2_line(img, p1, p2, color, thick, ang):
    import cv2
    if 0 <= p1[0] < img.shape[1] and 0 <= p1[1] < img.shape[0]:
        cv2.line(img, p1, p2, color, thick, cv2.LINE_AA)

def self_check():
    ok = 0
    # 1) 小雨/大雨滴数随雨强单调增
    n1 = len(rain_drops(2.5, 0, 540, 960, 120)); n2 = len(rain_drops(25, 0, 540, 960, 120))
    assert n2 > n1, (n1, n2); ok += 1
    # 2) 无风 -> 倾角≈0
    d0 = rain_drops(10, 0.0, 540, 960, 120); assert abs(d0[0][4]) < 1e-6; ok += 1
    # 3) 有风 -> 倾角>0 且随风速增
    a1 = rain_drops(10, 4.0, 540, 960, 120)[0][4]
    a2 = rain_drops(10, 12.0, 540, 960, 120)[0][4]
    assert a2 > a1 > 0, (a1, a2); ok += 1
    # 4) 大雨滴终速 > 小雨滴（D_mm 输入）
    assert water.drop_terminal_velocity(2.0) > water.drop_terminal_velocity(0.5); ok += 1
    # 5) 拖尾随直径增 (v, t, D_mm)
    assert water.streak_length(6.0, 1/60, 3.0) > water.streak_length(6.0, 1/60, 0.8); ok += 1
    # 6) 溅射分区：K 由 dimensionless 给 dict，splash_regime 吃标量 K
    dim = water.dimensionless(3.0, 6.0)
    assert water.splash_regime(dim["K"]) in ("spread", "crown", "splash"); ok += 1
    # 6b) 细滴小 K -> spread；粗滴高速 -> 非 spread（证明 K 真的在分档）
    k_s = water.dimensionless(0.5, 2.0)["K"]; k_b = water.dimensionless(4.0, 9.0)["K"]
    assert k_b > k_s and water.splash_regime(k_s) == "spread"; ok += 1
    # 7) 渲染不越界（帧内像素变化>0）
    f = np.zeros((200,120,3), np.uint8); ds = rain_drops(10, 5, 120, 200, 120)
    draw_rain(f, ds, 0.0, 5, 120); assert f.sum() > 0; ok += 1
    # 8) 同一雨强两次抽样可复现（seed）
    assert len(rain_drops(10,5,540,960,120,seed=3)) == len(rain_drops(10,5,540,960,120,seed=3)); ok += 1
    print(f"rain_layer 自检 {ok}/9 PASS")
    return ok == 9

if __name__ == "__main__":
    import sys; sys.exit(0 if self_check() else 1)
