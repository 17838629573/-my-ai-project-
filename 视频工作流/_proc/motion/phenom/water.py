# 契约: proc/motion/phenom
#   一句话: 常见物理现象能力族（leaf_fall/fracture/water_jet/newton_cradle/turntable）
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""水流冲击地面（PBF/SPH）"""
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

G = 9.8


@capability("water_jet", source="Position Based Fluids(Macklin & Müller 2013); "
                                "SPH 2D 核归一化",
            group="phenom")
def water_jet_sim(nx=12, ny=15, d=0.03, rho0=1000.0, T=1.5,
                  dt=1.0 / 240.0, iters=6, jet_v=(1.2, -1.5), seed=71,
                  eps=1e-6, mass_k=0.75, max_step_k=0.07, gf=0.985):
    """水流冲击地面：PBF 密度约束求解，落地后横向铺展。

    返回 (min_y, spread_ratio, rho_rel, n_alive)
      min_y        全程最小 y（≥0 表示未穿透地面）
      spread_ratio 最终横向范围 / 初始横向范围（>1 表示铺展）
      rho_rel      静息后平均 |ρ/ρ0 - 1|（不可压缩程度）
      n_alive      有效粒子数（无 NaN/逃逸 ⇒ 质量守恒）
    实现要点（PBF, Macklin & Müller 2013）：
      - 粒子按规整方阵排布，间距 d，光滑核半径 h=2.5d（约 20 个邻居）
      - mass = mass_k · ρ0 · d²（mass_k 由静息密度定标，见 self_check 注释）
      - Σ_k|∇_k C_i|² 含 i 自身项（PBF 原文 eq.11，漏项会过冲发散）
      - 单步位移 clamp 到 max_step_k·h，避免 λ 峰值把粒子甩飞
      - dt=1/240、iters=6（dt=1/60 时约束求解跟不上，会炸开）
    """
    rng = np.random.default_rng(seed)
    n_p = nx * ny
    xs = (np.arange(nx) - (nx - 1) / 2.0) * d
    ys = 0.25 + np.arange(ny) * d
    X, Y = np.meshgrid(xs, ys)
    p = np.stack([X.ravel(), Y.ravel()], axis=1).astype(float)
    p += rng.uniform(-0.002, 0.002, p.shape)      # 破对称，避免退化
    v = np.tile(np.array(jet_v, dtype=float), (n_p, 1))
    h = 2.5 * d
    mass = mass_k * rho0 * (d * d)

    # 2D 核函数（归一化）
    def _poly6(r2):
        m = r2 < h * h
        out = np.zeros_like(r2)
        out[m] = (4.0 / (math.pi * h ** 8)) * (h * h - r2[m]) ** 3
        return out
    def _spiky_grad(r2):
        """返回 ∇W 的径向系数 g，使 ∇W_ij = g(r2) * (p_i - p_j)。"""
        m = (r2 < h * h) & (r2 > 1e-12)
        out = np.zeros_like(r2)
        r = np.sqrt(r2[m])
        out[m] = -(30.0 / (math.pi * h ** 5)) * (h - r) ** 2 / r
        return out

    traj_max_x0 = float(p[:, 0].max() - p[:, 0].min())
    min_y = float("inf")
    n_steps = int(round(T / dt))
    for _ in range(n_steps):
        v[:, 1] -= G * dt
        q = p + v * dt
        for _it in range(iters):
            dvec = q[:, None, :] - q[None, :, :]
            r2 = np.sum(dvec * dvec, axis=-1)
            dens = np.sum(mass * _poly6(r2), axis=1)
            C = dens / rho0 - 1.0
            g = _spiky_grad(r2)
            grad = (g[:, :, None] * dvec) / rho0       # ∇_j C_i (j≠i)
            gsum = np.sum(grad, axis=1)                # ∇_i C_i = -Σ_j
            sum_sq = (np.sum(np.sum(grad * grad, axis=-1), axis=1)
                      + np.sum(gsum * gsum, axis=-1))
            lam = -C / (sum_sq + eps)
            # Δp_i = 1/ρ0 Σ_j (λ_i + λ_j) ∇W_ij
            coef = (lam[:, None] + lam[None, :]) * g
            dp = np.sum(coef[:, :, None] * dvec, axis=1) / rho0
            nrm = np.linalg.norm(dp, axis=1, keepdims=True)
            lim = max_step_k * h
            dp = dp * np.minimum(1.0, lim / np.maximum(nrm, 1e-12))
            q = q + dp
            # 地面（只推位置，速度在步末由位移反推 ⇒ 自然产生减速/停滞）
            q[:, 1] = np.maximum(q[:, 1], 0.0)
        v = (q - p) / dt
        p = q
        # 地面切向摩擦（贴地粒子切向速度逐步衰减；无摩擦则水会无限滑行，
        # 180 个粒子摊成单层 ⇒ spread 失真到 30 倍）
        on_g = p[:, 1] < 0.5 * d
        v[on_g, 0] *= gf
        min_y = min(min_y, float(p[:, 1].min()))

    ok = np.all(np.isfinite(p), axis=1)      # 逐粒子判有限（漏 axis 会退化成标量）
    n_alive = int(np.sum(ok))
    spread = float(p[ok, 0].max() - p[ok, 0].min()) / max(traj_max_x0, 1e-9)
    dvec = p[:, None, :] - p[None, :, :]
    r2 = np.sum(dvec * dvec, axis=-1)
    dens = np.sum(mass * _poly6(r2), axis=1)
    rho_rel = float(np.mean(np.abs(dens / rho0 - 1.0)))
    return float(min_y), spread, rho_rel, n_alive
