"""systems 的自检/检查逻辑（由 _extract_tool.py 从 systems.py 抽出）

改前必读: IMPROVE_systems.md
"""
import math
import os
import sys
import cv2
import numpy as np
from skeleton_runtime import Skeleton, apply_animation, mat_apply
import physics as ph
import physics_rules as pr
import framerate
from framerate import FPS
import re as _re

def init_physics(ctx):
    from systems import REAL_HEIGHT_M
    """Verlet 粒子 + 空气动力。惰性初始化。

    每个质点必须带上 area_m2 / mass_kg，否则 update_physics 无法由压力
    换算加速度（铁律14：禁 *1e-3 之类量纲补丁）。

    物性来源（铁律23：真实尺寸由 AI 经 scene_spec 传入，代码不含常量）：
      ctx.cloth_mass_kg / ctx.cloth_area_m2 —— 由调用方按 actor 物性给出。
      未给出时按 kind 从 physics 取默认并【报错提示】，不静默填 0。
    """
    mass_kg = getattr(ctx, "cloth_mass_kg", None)
    area_m2 = getattr(ctx, "cloth_area_m2", None)
    if mass_kg is None or area_m2 is None:
        raise ValueError(
            "init_physics 缺少 cloth_mass_kg / cloth_area_m2（铁律23："
            "物性由调用方按 scene_spec 传入，代码不含真实尺寸常量）。"
            "请先经 scale_map / actors 取得该可动件的质量与迎风面积。")
    n = CLOTH_ROWS * CLOTH_COLS
    ctx.particles = []
    for r in range(CLOTH_ROWS):
        for c in range(CLOTH_COLS):
            ctx.particles.append({
                "x": ctx.W * 0.3 + c * 12.0,
                "y": ctx.H * 0.2 + r * 12.0,
                "px": ctx.W * 0.3 + c * 12.0,
                "py": ctx.H * 0.2 + r * 12.0,
                "locked": (r == 0),
                # 均分：总质量/总面积 -> 每质点
                "mass_kg": float(mass_kg) / n,
                "area_m2": float(area_m2) / n,
            })

def update_physics(ctx, i, t):
    from systems import REAL_HEIGHT_M
    """
    Verlet 积分 + 空气动力（Wilson+14 / UCSD CSE169）
      p_new = 2p - p_prev + a·dt²
      F = -½·ρ·|v|²·c_d·a·n
    """
    if not getattr(ctx, "particles", None):
        return
    # 【已修】原写死 wind=30.0 m/s（蒲福11级暴风，树木拔起级别），
    # 而沙漠镜头只是"有风"。现由镜头声明的风级经蒲福换算得到。
    wind_v = getattr(ctx, "wind_speed", 8.0)   # 默认5级：小树摇摆
    wind = (wind_v, 0.0)
    rho = ph.RHO_AIR
    cd = getattr(ctx, "wind_cd", 1.0)
    # 像素/米换算：REAL_HEIGHT_M 对应角色身高的像素数
    px_per_m = getattr(ctx, "px_per_m", None)
    if px_per_m is None:
        h_px = float(getattr(ctx, "char_px", 691) or 691)
        px_per_m = ph.px_per_m(h_px, REAL_HEIGHT_M)
    gravity = -ph.G * px_per_m      # 9.81 m/s² 换算成 px/s²
    damping = 0.98
    # 铁律28：dt 必须跟随输出帧率，禁止写死 1/60。
    #   写死会让 24fps/30fps 输出时物理按错误时间步积分（实测错位 2.5 倍 / 2.0 倍）。
    dt = 1.0 / float(getattr(ctx, "fps", None) or FPS)

    for p in ctx.particles:
        if p["locked"]:
            continue
        vx = (p["x"] - p["px"]) * damping
        vy = (p["y"] - p["py"]) * damping
        # 空气动力
        # 【量纲】vx/vy 是 px/frame，wind 是 m/s —— 必须先换算到同一单位。
        #   漏换算会让气动力大 px_per_m^2 倍（实测 16.5 万倍）-> Verlet 立刻 nan。
        rvx = (vx / dt) / px_per_m - wind[0]
        rvy = (vy / dt) / px_per_m - wind[1]
        v2 = rvx * rvx + rvy * rvy
        mag = math.sqrt(v2)
        if mag > 1e-6:
            # 【逻辑唯一】气动力只由 physics 算，禁止本文件再写 0.5*rho*Cd*v^2
            # 【铁律14】压力(Pa) -> 加速度 必须经 (面积/质量)，禁止 *1e-3 之类凑数。
            #   原代码写 f * (rvx/mag) * 1e-3 —— 1e-3 是凭空凑的量纲补丁，已删除。
            press = -ph.force_per_area(mag, cd, b=getattr(ctx, "wind_b", 0.0))
            area_m2 = float(p.get("area_m2", 0.0) or 0.0)
            mass_kg = float(p.get("mass_kg", 0.0) or 0.0)
            if area_m2 <= 0.0 or mass_kg <= 0.0:
                # 质点缺物性 -> 硬报错（禁静默降级为 0）
                raise ValueError(
                    "质点缺少 area_m2/mass_kg，无法由压力换算加速度（铁律14）。"
                    "请在 init_physics 里按 actor 物性填入，或改用 ph.force()+ph.accel()。")
            # a = (F/A) * (A/m) ; 单位 m/s^2 -> 再换算 px/s^2
            a_mag = ph.accel(press * area_m2, mass_kg) * px_per_m
            ax_aero = a_mag * (rvx / mag)
            ay_aero = a_mag * (rvy / mag)
        else:
            ax_aero = ay_aero = 0.0
        p["px"], p["py"] = p["x"], p["y"]
        p["x"] += vx + (ax_aero + 0) * dt * dt
        p["y"] += vy + (gravity + ay_aero) * dt * dt

def update_movables(ctx, i, t):
    from systems import REAL_HEIGHT_M
    """
    可动件（dynamic actor）渲染：播放预生成序列帧（flipbook）。

    【已改·序列帧】业界定式：布料/火/水/烟"模拟后烘焙成 flipbook 导入引擎"，
    而非运行时几何变形。原做法对单张图做仿射剪切，既非物理也无真实布料形态。

    序列：assets_tang/char/<name>_f01..fNN.png（由合图切分，见 notes/banner.md）
    摆幅不由本文件算：姿态差异已烘焙在序列帧里，这里只做取帧 + cross-fade 循环。
    """
    lst = getattr(ctx, "movables", None)
    if not lst:
        return
    fps = float(getattr(ctx, "fps", 60) or 60)
    seqs = getattr(ctx, "movable_seqs", None) or {}
    for name in lst:
        seq = seqs.get(name)
        if not seq:
            continue
        n = len(seq)
        # 每帧时长：由 actor 声明的循环周期决定（默认 1.0s 一圈）
        period = float(getattr(ctx, "movable_period", {}).get(name, 1.0)) if isinstance(
            getattr(ctx, "movable_period", None), dict) else 1.0
        # 【铁律46】消费 solver 的 frame_durations，禁自己线性取帧（断链）
        durs = (getattr(ctx, "movable_durations", None) or {}).get(name)
        if not durs or len(durs) != n:
            durs = [period / n] * n            # 未提供则退化均匀
        i0, i1, f = framerate.frame_index(i / fps, durs)
        a0 = seq[i0].astype(np.float32)
        a1 = seq[i1].astype(np.float32)
        # 布局差异：不同帧抠像后尺寸不同，统一贴到最大画布（左上对齐=杆顶对齐）
        hs = max(x.shape[0] for x in seq)
        ws = max(x.shape[1] for x in seq)
        if getattr(ctx, "_mv_canvas", None) != (name, hs, ws):
            ctx._mv_canvas = (name, hs, ws)
        c0 = np.zeros((hs, ws, 4), np.float32); c0[:a0.shape[0], :a0.shape[1]] = a0
        c1 = np.zeros((hs, ws, 4), np.float32); c1[:a1.shape[0], :a1.shape[1]] = a1
        out = (c0 * (1 - f) + c1 * f).astype(np.uint8)
        ctx.parts[name] = out
