#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
物理求解：受迫链响应、regime 判定、周期与帧时长。

契约: contracts/solver_split.md
改前必读: IMPROVE_solver_split.md
"""

import math
import physics
import anchor
import framerate
from _solver_base import (CONSTANTS, AMP_BY_LEVEL_DEFAULT, REQUIRED,
                         DRAW_PARAM, WIND_DIR_DEFAULT, CHAIN_REQUIRED,
                         CHAIN_REQUIRED_SPEC, wind_sign)
from _solver_geom import skeleton_points
from _family_map import FAMILY_TO_PHYSICS, PHYSICS, FIVE, to_physics_dyn




def flag_lift_deg(*a, **k):
    from _solver_chain_aux import flag_lift_deg as _f
    return _f(*a, **k)




def amp_over_L(*a, **k):
    from _solver_chain_aux import amp_over_L as _f
    return _f(*a, **k)




def _check_spec(*a, **k):
    from _solver_chain_aux import _check_spec as _f
    return _f(*a, **k)




# ------------------------------------------------------------ 主入口
def solve(spec):
    """AI 填物性 -> 代码算全部 -> 答案包（供 AI 拿去生图）"""
    _check_spec(spec)
    fam = spec["family"]
    # 【铁律88】fam 是对外五类；内部物理求解须转成物理形态（映射层唯一真源）
    phys = to_physics_dyn(fam, spec)
    if phys == "static":
        # rigid（马车等）：刚体无振动，只输出位移 + 轮转，禁走振动求解
        return {
            "family": "static",
            "族": spec.get("族", "rigid"),
            "registration_point": spec["registration_point"],
            "freq_hz": 0.0,
            "period_s": 0.0,
            "frames": 1,
            "regime": "rigid",
            "drive_src": "code:rigid_body",
            "需序列帧": False,
            "note": "刚体：车轮自转与位移由代码算，禁序列帧（driver.must）",
        }
    if fam == "chain":
        # chain 不吃 geometry/material/fluid：几何由 links 累加，驱动由 drive 给
        links = spec["links"]
        L = sum(float(lk["L"]) for lk in links)
        W = float(links[0].get("W", L * 0.33)) if links else L * 0.33
        # 【铁律20】chain 链首若为风驱动，U 必须进来，由代码算驱动，禁 AI 手填
        U = float((spec.get("fluid") or {}).get("U", 0.0) or 0.0)
        g, mat, fl = {"L": L, "W": W}, {}, {"U": U}
        t = 2.0e-4
        sigma = 0.0
    else:
        g = spec["geometry"]
        mat = spec["material"]
        fl = spec["fluid"]
        L = float(g["L"])
        W = float(g.get("W", L))
        t = float(g.get("t", 2.0e-4))
        sigma = float(mat["sigma"])
        U = float(fl["U"])

    # --- 派生物性（代码算，非 AI 填）---
    if fam == "chain":
        mass_kg = sum(float(lk["m"]) for lk in links)
        area_m2 = sum(float(lk["L"]) * float(lk.get("W", W)) for lk in links)
        B = links[0].get("EI", 0.0) if links else 0.0
    else:
        mass_kg = sigma * L * W                      # 面密度 × 面积
        area_m2 = L * W                              # 薄板迎风面积（几何）
    if fam != "chain" and "B" in mat:
        B = float(mat["B"])                      # AI 直接给实测值（优先，ASTM D-1388）
    elif fam != "chain":
        E = float(mat["E"])
        nu = float(mat.get("nu", 0.34))          # 泊松比 Poisson's ratio
        # Izawa 原文: B = E·h³ / 12(1-ν²)  ← ν 是泊松比，不是面密度
        B = E * W * t ** 3 / (12.0 * (1.0 - nu * nu))

    # --- 无量纲数（复用 anchor，逻辑唯一）---
    if fam == "chain":
        # chain 不用旗帜判据：它的 regime 由各级放大因子决定（铁律34）
        dims = {"R1": float("nan"), "R2": float("nan"),
                "Re": float("nan"), "Fr": float("nan"), "Ustar": float("nan")}
        regime = "chain"                          # 由 chain_response 给振幅/相位
    else:
        dims = anchor.dimensionless(L, sigma, B, U, H=g.get("H"))
        # 【铁律32】regime 由 AI 搜证的判据决定，代码不做文献判断
        crit = spec["criteria"]
        by = crit["regime_by"]
        if by == "mu":                            # Connell & Yue 2007 常规旗
            mu = dims["R1"]
            lo = float(crit["mu_stable"])         # < lo : 稳定不动
            hi = float(crit["mu_chaotic"])         # > hi : 混沌拍打
            regime = ("stable" if mu < lo
                      else ("chaotic" if mu > hi else "flapping"))
        elif by == "given":
            regime = crit["regime"]               # AI 已判，直接采用
        else:
            raise ValueError("未知 regime_by=%r（铁律32：判据须 AI 搜证）"
                             % by)
    if fam != "chain":
        dims["mu"] = dims["R1"]
        # Fr 与 U*
        Fr = U / math.sqrt(CONSTANTS["G"] * L)
        dims["Fr"] = Fr
        dims["Ustar"] = (Fr / math.sqrt(dims["R1"])
                         if dims["R1"] > 0 else float("nan"))
    else:
        dims["mu"] = float("nan")

    # --- 风级 -> 振幅比（铁律32：表由 AI 搜证传入，代码只查表）---
    level = physics.beaufort_level(U)[0] if U > 0.0 else 0
    aol = amp_over_L(level, spec.get("criteria"))
    lift = flag_lift_deg(U)
    wdir = float(spec.get("wind_dir", WIND_DIR_DEFAULT))

    # --- 频率/周期/帧数（铁律20 + 铁律29）---
    if fam == "chain":
        drv = spec.get("drive") or {}
        lks = spec.get("links") or []
        L = sum(float(lk["L"]) for lk in lks) or L
        src_kind = spec.get("source")
        # 【铁律42】多驱动叠加：风 与 步频/冲击 可同时作用。
        # 旧实现二选一 -> "2-3 级风里有人走动"时衣摆只随步频、风进不去。
        # 主驱动在前（决定周期与相位），叠加项在后。
        # 【铁律20】主驱动由 source 决定，不是由"谁先写进 spec"决定。
        # 旧实现: f = drives[0] -> 手填 f_hz 恒压过风驱动，
        #   导致 4 级风(U=5.5)下旗仍按手填 1.71Hz(6级风值)播，摆速快 3.1 倍。
        # 现: source=="wind" -> 风为频率主驱动；否则步频/冲击为主，风为叠加。
        given = None
        if "f_hz" in drv:
            # 非风驱动（步频/冲击）：频率由 AI 给（驱动源属性，不是算术）
            given = (float(drv["f_hz"]), float(drv.get("amp_m", 0.02)),
                     src_kind or "given")
        wind_drive = None
        if U > 0.0:
            # 【铁律20】风驱动：频率由 St、振幅由风级查表，均由代码算，禁 AI 手填
            f_w, _ = anchor.strouhal_freq(U, L, a_over_l=max(aol, 1e-6))
            wind_drive = (f_w, aol * L / 2.0, "wind")
        if src_kind == "wind":
            drives = ([wind_drive] if wind_drive else []) + ([given] if given else [])
        else:
            drives = ([given] if given else []) + ([wind_drive] if wind_drive else [])
        if not drives:
            raise ValueError("chain 族缺 fluid.U 或 drive.f_hz（铁律20："
                             "风驱动须给 U，由代码算频率与振幅）")
        f, T = drives[0][0], 1.0 / drives[0][0]
        drive_src = "+".join("%s:%s@%.3fHz" % (d[2], "code" if d[2] == "wind"
                                               else "ai", d[0]) for d in drives)
        resp = chain_response_multi(lks, drives)
        tip_pp = resp[-1]["amp_m"] * 2.0
        L = sum(float(lk["L"]) for lk in (spec.get("links") or [])) or L
    elif fam == "cantilever":
        f, T = anchor.strouhal_freq(U, L, a_over_l=max(aol, 1e-6))
        tip_pp = aol * L
    else:
        # 二级摆/铰链/液面：Izawa 判据不适用，由 AI 给周期或退化为固有频率
        f, T = anchor.strouhal_freq(U, L, a_over_l=max(aol, 1e-6))
        tip_pp = aol * L
    N = framerate.frames_for_period(T)           # N = round(T*FPS)

    # --- 物理点（复用 anchor，逻辑唯一）---
    if fam == "chain":
        # 由 chain_response 的逐级振幅/相位滞后合成物理点
        tot = sum(float(lk["L"]) for lk in (spec.get("links") or [])) or 1.0
        amax = max(r["amp_m"] for r in resp) or 1.0
        pts, acc_s, acc_lag = [], 0.0, 0.0
        pts.append((0.0, 0.0, 0.0))              # 链首固定端，位移恒 0
        for lk, r in zip(spec.get("links") or [], resp):
            acc_s += float(lk["L"]) / tot
            acc_lag += r["phase_lag_deg"]
            pts.append((min(acc_s, 1.0), r["amp_m"] / amax, acc_lag % 360.0))
    else:
        pts = anchor.build_anchor(spec.get("name", "actor"), L=L, H=L,
                                  sigma=sigma, B=B, U=U, family=phys,
                                  n=8, a_over_l=aol)["points"]

    # --- N 个相位的骨架几何 ---
    # 【铁律32】伸出度与跨度由 lift（Rule of 4，代码算）决定，
    # 不再是按 regime 查表的常数——否则小风也画成大风形态
    dp = DRAW_PARAM.get(regime, DRAW_PARAM["n/a"])
    mean = math.sin(math.radians(lift))
    vfac = max(math.cos(math.radians(lift)), 0.35)   # 绘制缩放，防退化
    phases = skeleton_points(pts, N, L, W,
                             mean=mean, vfactor=vfac,
                             tip_pp=tip_pp,
                             lift_deg=lift, dir_deg=wdir)

    return {
        "family": fam,
        "族": spec.get("族", fam),   # 对外五类（driver 分派用）
        "derived": {"mass_kg": mass_kg, "area_m2": area_m2, "B_nm2": B},
        "dimensionless": dims,
        "regime": regime,
        "freq_hz": f, "period_s": T, "drive_src": drive_src if fam=="chain" else "code:strouhal",
        "frames": N,
        # 【铁律43】逐帧时长：末帧停留补偿循环闭合（业界定式，非 cross-fade）
        "frame_durations": frame_durations(N, T),
        # 【铁律54】素材张数 = round(T·FPS)，视频不做 16 帧封顶（那是游戏值）
        "mat_frames": N,
        "playrate": 1.0,
        "tip_pp_amp_m": tip_pp,
        "amp_over_L": aol,
        "lift_deg": lift,
        "wind_dir_deg": wdir,
        "points": pts,
        "phase_geometry": phases,
        "draw": {"mean": mean, "vfactor": vfac, "lift_deg": lift,
                 "dir_sign": wind_sign(wdir),
                 "W_over_L": W / L, "frames": N},
        "wind": {"U": U, "level": level, "dir_deg": wdir},
    }




def chain_response(*a, **k):
    from _solver_chain_aux import chain_response as _f
    return _f(*a, **k)




def chain_response_multi(*a, **k):
    from _solver_chain_aux import chain_response_multi as _f
    return _f(*a, **k)




def frame_durations(*a, **k):
    from _solver_chain_aux import frame_durations as _f
    return _f(*a, **k)




def loop_seam_ratio(*a, **k):
    from _solver_chain_aux import loop_seam_ratio as _f
    return _f(*a, **k)




# ------------------------------------------------------------ transient（瞬态衰减）
# 冲击波 = 突然的大风。解的形式从稳态换成瞬态。
# 包络来源 NASA NTRS: h(t) = (1/m·ω_d)·e^(-ζ·ω_n·t)·sin(ω_d·t)
def transient_envelope(*a, **k):
    from _solver_chain_aux import transient_envelope as _f
    return _f(*a, **k)