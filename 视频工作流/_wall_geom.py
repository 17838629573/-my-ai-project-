#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wall geometry —— 墙体落点的透视几何（从 _surface.py 拆出）。

拆出原因（禁提阈值，故必须拆）：_surface.py 加 _horizon_of / _path_center_x 后
达 373 行 / 13153 字符，超体积阈值，gate_post 强制拆分。
此处按职责划出「墙体几何」一组（wall_* 两个函数）。

透视基本式（本文件全部推导的地基）：
    y(z)   = v_h + f * h_cam / z          地面深度 z 对应的屏幕行
    px_h(h_m, z) = f * h_m / z            深度 z 处 h_m 米对应的像素高
两式联立消去 z，得本项目反复使用的自洽式：
    px_per_m(y) = (y - v_h) / h_cam
  自检（城墙场景 v_h=482, h_cam=3.383）：
    y=880 -> 117.65  == spec near_px_per_m 117.647 ✓
    y=600 ->  34.88  ~= spec far_px_per_m   35.056 ✓
"""
import numpy as _np

from _perspective import y_at_depth, object_px_height, depth_at


def wall_top_y(h_wall_m, z_wall_m, v_h, f_px, h_cam, image_h=None):
    """墙顶屏幕行 y = 墙基底 y − 墙的像素高。透视算，非手填坐标。

    h_wall_m: 墙的真实高(m)，物理量，须由 AI 搜证后落盘。
    z_wall_m: 墙所在深度(m)。
    image_h: 画面高；给了就校验墙顶在画面内，跑出边界即报错（禁静默负值）。
    """
    if h_wall_m is None or h_wall_m <= 0:
        raise ValueError("墙高 h_wall_m 必须 > 0 且已声明（缺则走 param_decl 反问）")
    y_base = y_at_depth(z_wall_m, v_h, f_px, h_cam)
    y_top = y_base - object_px_height(h_wall_m, y_base, v_h, h_cam)
    if image_h is not None and not (0.0 <= y_top <= image_h):
        raise ValueError(
            "墙顶 y=%.1f 跑出画面[0,%d]：墙高 %.1fm 在深 %.1fm 处装不下。"
            "应增大墙的深度 z_m 或降低墙高 —— 禁给负值、禁裁到边界了事"
            % (y_top, image_h, h_wall_m, z_wall_m))
    return y_top



def wall_depth_for_top(h_wall_m, y_top_target, v_h, f_px, h_cam):
    """反解：要让墙顶落在屏幕行 y_top_target，墙须在多深的 Z(m)。

    用于"墙在画面里"取代"手填 z"。依据[3]透视双曲线反解。
    """
    if not (y_top_target < v_h):
        raise ValueError("墙顶须在地平线 v_h 之上（y < v_h），否则不是墙顶")
    y_base = y_top_target
    # y_top = y_base - h_wall * (y_base - v_h)/h_cam
    #      = y_base*(1 - h/h_cam) + v_h*h/h_cam
    k = h_wall_m / h_cam
    # y_top = y_base*(1-k) + v_h*k  →  y_base = (y_top - v_h*k)/(1-k)
    if abs(1.0 - k) < 1e-9:
        raise ValueError("墙高恰等于相机高，透视退化，无法反解")
    y_base = (y_top_target - v_h * k) / (1.0 - k)
    return depth_at(y_base, v_h, f_px, h_cam)


