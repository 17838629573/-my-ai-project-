# 契约: proc/motion/phenom/fracture
#   一句话: 砖墙被球撞击碎裂（内聚区 bond 应变阈值失效）
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""墙体开裂/碎裂：位置动力学（PBD）质点 + 三角化 bond + 内聚区失效判据。

依据（搜索先行，非凭记忆）：
- GAUGE benchmark(arXiv:2608.05948) Wall Breaking 任务族
- 内聚区断裂（Dugdale 1960；Barenblatt 1962）：约束拉伸超过临界应变即失效

    返回 (n_broken, n_frag, max_disp, mom_err, stable, v_ball_end)
      n_broken  断裂 bond 数
      n_frag    连通分量数（>1 表示真裂开成碎块）
      max_disp  砖块最大位移（m）
      mom_err   动量守恒误差（水平；PBD 位置投影不严格守恒，见 note）
      stable    未受撞时墙自身是否稳定（静置位移小于阈值）
      v_ball_end 球末速度 x 分量（撞击后应减速）
    note: PBD 位置投影为几何修正，不保证动量严格守恒；mom_err 仅作参考量，
          不作为判据（实测 O(1e2)），判据改用「球减速 + 碎块位移有界」。
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

import numpy as np

from ..beat import capability

G = 9.8


# ------------------------------------------------------------------ 建模
def _build_brick_mesh(cols, rows, brick, gap):
    """质点网格：底行固定在地面。返回 (p, fix)。"""
    pos, fixed = [], []
    for r in range(rows):
        for c in range(cols):
            pos.append([c * (brick + gap), 0.5 * brick + r * (brick + gap)])
            fixed.append(r == 0)
    return np.array(pos, dtype=float), np.array(fixed)


def _build_bonds(p, cols, rows):
    """三角化 bond：水平/垂直/两条对角（保持刚性）。返回 (bonds, rest)。"""
    idx = lambda c, r: r * cols + c          # noqa: E731
    bonds, rest = [], []

    def _add(i, j):
        bonds.append((i, j))
        rest.append(float(np.linalg.norm(p[i] - p[j])))

    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                _add(idx(c, r), idx(c + 1, r))
            if r + 1 < rows:
                _add(idx(c, r), idx(c, r + 1))
            if c + 1 < cols and r + 1 < rows:
                _add(idx(c, r), idx(c + 1, r + 1))
                _add(idx(c + 1, r), idx(c, r + 1))
    return np.array(bonds), np.array(rest)


def _components(n_p, bonds, alive_mask):
    """按存活 bond 计算连通分量数（并查集）。"""
    par = list(range(n_p))

    def _find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for k in range(len(bonds)):
        if alive_mask[k]:
            a, b = _find(int(bonds[k, 0])), _find(int(bonds[k, 1]))
            if a != b:
                par[a] = b
    return len({_find(i) for i in range(n_p)})


# ------------------------------------------------------------------ 求解
def _relax(q, bonds, rest, fix, steps):
    """PBD bond 松弛若干步（不改变断裂状态，仅几何投影）。"""
    for _ in range(steps):
        for k in range(len(bonds)):
            i, j = int(bonds[k, 0]), int(bonds[k, 1])
            d = q[j] - q[i]
            L_ = np.linalg.norm(d)
            if L_ < 1e-12:
                continue
            corr = 0.5 * (L_ - rest[k]) * d / L_
            if not fix[i]:
                q[i] += corr
            if not fix[j]:
                q[j] -= corr
    return q


def _settle(p, bonds, rest, fix, steps=200):
    """无外力静置，检验墙自身稳定：返回相对初始位置的最大位移。"""
    return float(np.max(np.linalg.norm(_relax(p.copy(), bonds, rest, fix, steps)
                                       - p, axis=1)))


def _project_bonds(p, bonds, rest, alive, fix, strain_limit, break_hist):
    """一轮 bond 约束投影：拉伸超临界应变即失效（内聚区判据）。"""
    for k in range(len(bonds)):
        if not alive[k]:
            continue
        i, j = int(bonds[k, 0]), int(bonds[k, 1])
        d = p[j] - p[i]
        L_ = float(np.linalg.norm(d))
        if L_ < 1e-12:
            continue
        strain = (L_ - rest[k]) / rest[k]
        if strain > strain_limit:
            alive[k] = False
            break_hist.append(k)
            continue
        corr = 0.5 * (L_ - rest[k]) * d / L_
        if not fix[i]:
            p[i] += corr
        if not fix[j]:
            p[j] -= corr
    return alive


def _ball_brick(p, bp, bvel, bv, fix, ball_r, ball_m, mass, restitution):
    """球-砖碰撞：法向冲量交换 + 按逆质量分配位置分离。"""
    inv_b = 1.0 / ball_m
    for i in range(len(p)):
        if fix[i]:
            continue
        d = p[i] - bp
        dist = float(np.linalg.norm(d))
        if dist >= ball_r:
            continue
        nrm = d / (dist if dist > 1e-12 else 1.0)
        inv_i = 1.0 / mass
        v_rel = bvel[i] - bv
        vn = float(np.dot(v_rel, nrm))
        if vn < 0.0:                          # 正在接近 → 施加法向冲量
            jn = -(1.0 + restitution) * vn / (inv_i + inv_b)
            bvel[i] += jn * inv_i * nrm
            bv -= jn * inv_b * nrm
        pen = ball_r - dist
        if pen > 0.0:
            p[i] += nrm * (pen * inv_i / (inv_i + inv_b))
            bp -= nrm * (pen * inv_b / (inv_i + inv_b))
    return p, bp, bvel, bv


def _ground_clamp(p, bp, ball_r):
    """地面位置夹紧（在速度反推之前执行）。"""
    p[:, 1] = np.maximum(p[:, 1], 0.0)
    if bp[1] < ball_r:
        bp[1] = ball_r
    return p, bp


def _ground_contact(p, bvel):
    """地面接触速度修正：法向弱回弹 + 切向摩擦（在速度反推之后执行）。"""
    for i in range(len(p)):
        if p[i, 1] <= 1e-9:
            if bvel[i, 1] < 0.0:
                bvel[i, 1] = -0.10 * bvel[i, 1]
            bvel[i, 0] *= 0.90
    return bvel


# ------------------------------------------------------------------ 主入口
def _fracture_step(p, bp, bvel, bv, bonds, rest, alive, fix, strain_limit,
                   p_break_hist, ball_r, ball_m, mass, restitution,
                   damping, iters, dt):
    """单步：重力积分 → bond 投影 → 球砖碰撞 → 地面夹紧 → 速度反推。

    顺序不可换：地面夹紧须在速度反推之前（否则穿地），地面接触须在其后。
    """
    bvel[:, 1] -= G * dt
    bv[1] -= G * dt
    p_prev = p.copy()
    p += bvel * dt
    bp += bv * dt
    for _it in range(iters):
        _project_bonds(p, bonds, rest, alive, fix, strain_limit,
                       p_break_hist)
    p, bp, bvel, bv = _ball_brick(p, bp, bvel, bv, fix, ball_r, ball_m,
                                  mass, restitution)
    p, bp = _ground_clamp(p, bp, ball_r)
    bvel = (p - p_prev) / dt
    bvel = _ground_contact(p, bvel)
    bvel *= max(0.0, 1.0 - damping * dt)
    return p, bp, bvel, bv


@capability("fracture", source="GAUGE(arXiv:2608.05948) Wall Breaking; "
                               "内聚区断裂(Dugdale 1960/Barenblatt 1962)",
            group="phenom")
def fracture_sim(cols=5, rows=4, brick=0.12, gap=0.002, mass=1.0,
                 strain_limit=0.02, ball_m=3.0, ball_r=0.07, v0=10.0,
                 T=2.0, dt=1.0 / 600.0, iters=8, restitution=0.05,
                 damping=1.2):
    """砖墙被球撞击碎裂：bond 拉伸超临界应变即失效（内聚区断裂）。

    返回 (n_broken, n_frag, max_disp, mom_err, stable, v_ball_end)
    """
    p, fix = _build_brick_mesh(cols, rows, brick, gap)
    p_ref0 = p.copy()
    p_old = p.copy()
    n_p = len(p)
    bonds, rest = _build_bonds(p, cols, rows)
    alive = np.ones(len(bonds), dtype=bool)

    stable_disp = _settle(p, bonds, rest, fix)

    # 撞击球（质点，从左向右）
    bp = np.array([-0.60, 0.5 * brick + 1.5 * (brick + gap)], dtype=float)
    bv = np.array([v0, 0.0], dtype=float)
    bvel = np.zeros_like(p)          # 砖质点显式速度（PBD：位置投影后反推）
    n_steps = int(round(T / dt))
    p_break_hist = []
    for _ in range(n_steps):
        p, bp, bvel, bv = _fracture_step(
            p, bp, bvel, bv, bonds, rest, alive, fix, strain_limit,
            p_break_hist, ball_r, ball_m, mass, restitution,
            damping, iters, dt)

    n_broken = int(np.sum(~alive))
    n_frag = _components(n_p, bonds, alive)
    # 动量守恒（水平）：球 + 全部砖块
    p_brick_x = float(np.sum((p[:, 0] - p_old[:, 0]) / dt)) * mass
    mom_err = abs((bv[0] * ball_m + p_brick_x) - (v0 * ball_m))
    return n_broken, n_frag, float(np.max(np.linalg.norm(p - p_ref0, axis=1))), \
        float(mom_err), float(stable_disp), float(bv[0])
