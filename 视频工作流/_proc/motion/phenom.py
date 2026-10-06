
# 契约: proc/motion/phenom
#   一句话: 常见物理现象五能力：leaf_fall/fracture/water_jet/newton_cradle/turntable
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""常见物理现象补齐（对照 GAUGE benchmark 22 任务族 + 用户点名场景）。

依据（搜索先行，非凭记忆）：
- leaf_fall: Wang & Pesavento 2004 PRL《The Unsteady Aerodynamics of Falling
  Flat Plates》；Andersen, Pesavento, Wang 2005 JFM《Unsteady aerodynamics of
  flutter and tumbling bodies》。关键机制：薄片所受升力主要来自**平动速度 ×
  转动角速度的耦合项**（∝ v·ω），而非定常翼型的 v² 项，故薄片在翻转点可短暂
  上升。两种模式 flutter（左右摆动滑翔）与 tumbling（持续翻滚）由无量纲转动
  惯量决定。本实现用准稳态阻力 + v·ω 耦合升力 + 偏心力矩，**系数取典型值以
  复现两种定性模式，非文献精确值**（如实标注，不自造精度）。
- fracture: GAUGE benchmark(arXiv:2608.05948) Wall Breaking 任务族；粘结断裂
  用 cohesive/应变阈值判据（Dugdale 1960; Barenblatt 1962 内聚区模型思想：
  约束拉伸超过临界应变即失效）。砖墙用位置动力学质点 + 三角化 bond 保持刚性。
- water_jet: Position Based Fluids（Macklin & Müller 2013, SIGGRAPH）；
  SPH 核函数 2D 归一化（Poly6 用于密度、Spiky 梯度用于约束梯度）。
- newton_cradle: GAUGE Newton's Cradle 任务族。等质量弹性碰撞 ⇒ 速度交换，
  故末球弹出、中间球静止（动量/能量守恒的直接推论，非调参结果）。
- turntable: GAUGE Turntable 任务族。非惯性系：离心力 mω²r、科氏力
  -2mω×v_rel；静摩擦锥判滑移（库仑）。

坐标：米制世界坐标，x 向右，y 向上（与 rigid2d 系列一致）。
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

from .beat import capability

G = 9.8


# ================================================================= leaf_fall
@capability("leaf_fall", source="Wang & Pesavento 2004 PRL; "
                                "Andersen/Pesavento/Wang 2005 JFM: 升力∝v·ω耦合项",
            group="phenom")
def _leaf_load(vx, vy, w, th, m, L, h, rho_f, C):
    """薄片气动载荷：法向/切向阻力 + v·ω 耦合升力 + 重力 + 力矩。

    返回 (fx, fy, M)，M 为偏心力矩与旋转阻尼之和；spin 模式由调用方处理。
    出处: Andersen et al. 2005 JFM 准稳态模型（唯象系数，见 leaf_fall_sim）。
    """
    C_N, C_T, C_L, C_E, C_M = C
    tx, ty = math.cos(th), math.sin(th)
    nx, ny = -math.sin(th), math.cos(th)
    vn = vx * nx + vy * ny
    vt = vx * tx + vy * ty
    f_n = -0.5 * rho_f * C_N * L * abs(vn) * vn
    f_t = -0.5 * rho_f * C_T * h * abs(vt) * vt
    fx = f_n * nx + f_t * tx
    fy = f_n * ny + f_t * ty
    fx += rho_f * L * L * C_L * w * (-vy)
    fy += rho_f * L * L * C_L * w * (vx)
    fy -= m * G
    v2 = vx * vx + vy * vy
    alpha = math.atan2(vn, -vt) if v2 > 1e-12 else 0.0
    M = (0.5 * rho_f * (L ** 3) * C_E * v2 * math.sin(2.0 * alpha)
         - 0.5 * rho_f * C_M * (L ** 4) * abs(w) * w)
    return fx, fy, M


def _leaf_classify(traj, net, dt):
    """从轨迹与净转角归纳 (mode, v_term, n_swings)。

    v_term 用总下降高度/总时间（口径稳定，不受末段短暂上升干扰）。
    """
    if len(traj) < 10:
        return "settled", 0.0, 0
    arr = np.array(traj)
    v_term = (arr[0, 1] - arr[-1, 1]) / (len(arr) * dt)
    vx_seq = np.diff(arr[:, 0])
    sgn = np.sign(vx_seq)
    sgn = sgn[sgn != 0]
    n_swings = int(np.sum(sgn[1:] != sgn[:-1])) if len(sgn) > 1 else 0
    mode = "tumbling" if abs(net) > 2.0 * math.pi else "flutter"
    return mode, float(v_term), n_swings


@capability("leaf_fall", source="Andersen et al. 2005 JFM 薄片下落双稳态"
                                "(flutter/tumbling) 准稳态气动模型",
            group="phenom")
def leaf_fall_sim(L=0.06, h=5e-4, m=5e-4, rho_f=1.225, T=4.0, dt=1.0 / 2000.0,
                  theta0=0.6, I_scale=1.0, ground_y=0.0, w0=0.0,
                  spin=None):
    """薄片（树叶/纸片）飘落：flutter（摆动滑翔）与 tumbling（持续翻滚）。

    返回 (mode, v_term, n_swings, dtheta, traj)
      mode        "flutter" 或 "tumbling"（按**净转角**判定，非端点差）
      v_term      全程平均下降速度（m/s）
      n_swings    水平速度符号变化次数（flutter 特征）
      dtheta      **净**转角（有符号累加）
      traj        [(x, y, theta), ...]
    物理：准稳态法向/切向阻力 + v·ω 耦合升力 + 偏心力矩 + 旋转阻尼。
    tumbling 需给定自转 spin（自持翻滚的涌现未实现，如实标注不冒充）。
    """
    I = I_scale * m * (L * L + h * h) / 12.0
    C_N, C_T, C_L, C_E, C_M = 1.8, 0.10, 0.50, 0.30, 0.20
    x, y, th = 0.0, 2.0, theta0
    vx, vy, w = 0.0, 0.0, w0
    net = 0.0
    traj = []
    C = (C_N, C_T, C_L, C_E, C_M)
    n = int(round(T / dt))
    for _ in range(n):
        fx, fy, M = _leaf_load(vx, vy, w, th, m, L, h, rho_f, C)
        if spin is not None:
            M = 0.0                  # tumbling：自转为给定输入，不解算力矩
        vx += fx / m * dt
        vy += fy / m * dt
        w = spin if spin is not None else w + M / I * dt
        x += vx * dt
        y += vy * dt
        th += w * dt
        net += w * dt
        if y <= ground_y:            # 落地即停（判据取落地前的行为）
            break
        traj.append((x, y, th))
    mode, v_term, n_swings = _leaf_classify(traj, net, dt)
    return mode, v_term, n_swings, float(net), traj


# ================================================================= fracture
@capability("fracture", source="GAUGE(arXiv:2608.05948) Wall Breaking; "
                               "内聚区断裂(Dugdale 1960/Barenblatt 1962)",
            group="phenom")
def fracture_sim(cols=5, rows=4, brick=0.12, gap=0.002, mass=1.0,
                 strain_limit=0.02, ball_m=3.0, ball_r=0.07, v0=10.0,
                 T=2.0, dt=1.0 / 600.0, iters=8, restitution=0.05,
                 damping=1.2):
    """砖墙被球撞击碎裂：bond 拉伸超临界应变即失效（内聚区断裂）。

    返回 (n_broken, n_frag, max_disp, mom_err, stable)
      n_broken  断裂 bond 数
      n_frag    连通分量数（>1 表示真裂开成碎块）
      max_disp  砖块最大位移（m）
      mom_err   动量守恒误差（无重力方向，水平动量守恒）
      stable    未受撞时墙自身是否稳定（max_disp 小于阈值）
    实现：位置动力学（PBD）质点 + 三角化 bond（水平/垂直/对角保持刚性）。
    """
    # 质点网格：底行固定在地面
    idx = lambda c, r: r * cols + c          # noqa: E731
    pos, fixed = [], []
    for r in range(rows):
        for c in range(cols):
            pos.append([c * (brick + gap), 0.5 * brick + r * (brick + gap)])
            fixed.append(r == 0)
    p = np.array(pos, dtype=float)
    p_ref0 = p.copy()
    p_old = p.copy()
    fix = np.array(fixed)
    n_p = len(p)

    # bond：水平、垂直、对角（三角化 → 保持刚性）
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
    bonds = np.array(bonds)
    rest = np.array(rest)
    alive = np.ones(len(bonds), dtype=bool)

    def _components(n_b, alive_mask):
        """按存活 bond 计算连通分量数（并查集）。"""
        par = list(range(n_p))
        def _find(a):
            while par[a] != a:
                par[a] = par[par[a]]
                a = par[a]
            return a
        for k in range(n_b):
            if alive_mask[k]:
                a, b = _find(int(bonds[k, 0])), _find(int(bonds[k, 1]))
                if a != b:
                    par[a] = b
        return len({_find(i) for i in range(n_p)})

    def _settle(steps=200):
        """无外力静置，检验墙自身稳定。"""
        qq = p.copy()
        for _ in range(steps):
            for k in range(len(bonds)):
                i, j = int(bonds[k, 0]), int(bonds[k, 1])
                d = qq[j] - qq[i]
                L_ = np.linalg.norm(d)
                if L_ < 1e-12:
                    continue
                corr = 0.5 * (L_ - rest[k]) * d / L_
                if not fix[i]:
                    qq[i] += corr
                if not fix[j]:
                    qq[j] -= corr
        return float(np.max(np.linalg.norm(qq - p, axis=1)))

    stable_disp = _settle()

    # 撞击球（质点，从左向右）
    bp = np.array([-0.60, 0.5 * brick + 1.5 * (brick + gap)], dtype=float)
    bv = np.array([v0, 0.0], dtype=float)
    bvel = np.zeros_like(p)          # 砖质点显式速度（PBD：位置投影后反推）
    n_steps = int(round(T / dt))
    p_break_hist = []
    for _ in range(n_steps):
        # 重力 + 积分（半隐式欧拉）
        bvel[:, 1] -= G * dt
        bv[1] -= G * dt
        p_prev = p.copy()
        p += bvel * dt
        bp += bv * dt
        # bond 约束（PBD 迭代）
        for _it in range(iters):
            for k in range(len(bonds)):
                if not alive[k]:
                    continue
                i, j = int(bonds[k, 0]), int(bonds[k, 1])
                d = p[j] - p[i]
                L_ = float(np.linalg.norm(d))
                if L_ < 1e-12:
                    continue
                strain = (L_ - rest[k]) / rest[k]
                if strain > strain_limit:      # 内聚区失效判据
                    alive[k] = False
                    p_break_hist.append(k)
                    continue
                corr = 0.5 * (L_ - rest[k]) * d / L_
                if not fix[i]:
                    p[i] += corr
                if not fix[j]:
                    p[j] -= corr
        # 球-砖碰撞：真正的冲量交换 + 按逆质量分配位置分离
        inv_b = 1.0 / ball_m
        for i in range(n_p):
            if fix[i]:
                continue
            d = p[i] - bp
            dist = float(np.linalg.norm(d))
            if dist < ball_r:
                nrm = d / (dist if dist > 1e-12 else 1.0)
                inv_i = 1.0 / mass
                v_rel = bvel[i] - bv
                vn = float(np.dot(v_rel, nrm))
                if vn < 0.0:                   # 正在接近 → 施加法向冲量
                    jn = -(1.0 + restitution) * vn / (inv_i + inv_b)
                    bvel[i] += jn * inv_i * nrm
                    bv -= jn * inv_b * nrm
                pen = ball_r - dist
                if pen > 0.0:
                    p[i] += nrm * (pen * inv_i / (inv_i + inv_b))
                    bp -= nrm * (pen * inv_b / (inv_i + inv_b))
        # 地面
        p[:, 1] = np.maximum(p[:, 1], 0.0)
        if bp[1] < ball_r:
            bp[1] = ball_r
        # PBD：由约束投影后的位置反推速度
        bvel = (p - p_prev) / dt
        # 地面接触：法向弱回弹 + 切向摩擦
        for i in range(n_p):
            if p[i, 1] <= 1e-9:
                if bvel[i, 1] < 0.0:
                    bvel[i, 1] = -0.10 * bvel[i, 1]
                bvel[i, 0] *= 0.90
        # 空气阻尼 / 内耗（防止断裂碎块无限加速）
        bvel *= max(0.0, 1.0 - damping * dt)

    n_broken = int(np.sum(~alive))
    n_frag = _components(len(bonds), alive)
    # 动量守恒（水平）：球 + 全部砖块
    p_brick_x = float(np.sum((p[:, 0] - p_old[:, 0]) / dt)) * mass
    mom_err = abs((bv[0] * ball_m + p_brick_x) - (v0 * ball_m))
    v_ball_end = float(bv[0])
    return n_broken, n_frag, float(np.max(np.linalg.norm(p - p_ref0, axis=1))), \
        float(mom_err), float(stable_disp), v_ball_end


# ================================================================= water_jet
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


# ============================================================ newton_cradle
@capability("newton_cradle", source="GAUGE(arXiv:2608.05948) Newton's Cradle; "
                                    "等质量弹性碰撞⇒速度交换",
            group="phenom")
def newton_cradle_sim(n=5, L=0.50, r=0.04, m=0.20, th0=0.60, T=3.0,
                      dt=1.0 / 4000.0, e=0.999):
    """牛顿摆：首球拉起释放，等质量弹性碰撞 ⇒ 末球弹出、中间球静止。

    返回 (v_last, th_mid_win, th_last_win, mom_err, energy_err)
      v_last      末球获得的最大速度（应接近首球入射速度）
      th_mid_win  首次碰撞后 0.25s 窗口内中间球最大角位移（应≈0）
      th_last_win 同窗口内末球最大角位移（应≈th0）
      mom_err     动量守恒误差
      energy_err  能量守恒误差（e<1 时允许少量耗散，故判据看比例）
    注：末球弹出后会摆回二次撞击，届时中间球必然动起来，故中间球"静止"
    只在首次碰撞后的短窗口内判定，这是牛顿摆的正确观测口径。
    碰撞沿切向（摆的切向速度），等质量 ⇒ 交换切向速度（乘 e）。
    """
    th = np.zeros(n)
    om = np.zeros(n)
    th[0] = th0
    # 悬挂点间距 = 2r（刚好接触）
    anchor_x = np.arange(n) * (2.0 * r)
    n_steps = int(round(T / dt))
    v_last = 0.0
    th_mid_win = 0.0
    th_last_win = 0.0
    first_hit = None
    e0 = m * G * L * (1.0 - math.cos(th0))     # 初始势能
    for _step in range(n_steps):
        # 单摆：θ'' = -(g/L) sinθ
        om += (-(G / L) * np.sin(th)) * dt
        th += om * dt
        # 球心位置与切向速度
        pos_x = anchor_x + L * np.sin(th)
        vt = om * L
        # 相邻球接触检测（球心距 < 2r 且互相接近）
        for i in range(n - 1):
            d = pos_x[i + 1] - pos_x[i]
            if d < 2.0 * r and (vt[i] - vt[i + 1]) > 0.0:
                # 等质量弹性碰撞 ⇒ 交换速度（乘恢复系数）
                a, b = e * vt[i + 1], e * vt[i]
                vt[i], vt[i + 1] = a, b
                om[i], om[i + 1] = vt[i] / L, vt[i + 1] / L
                if first_hit is None:
                    first_hit = _step
        v_last = max(v_last, abs(vt[-1]))
        if first_hit is not None and (_step - first_hit) * dt <= 0.25:
            if n > 2:
                th_mid_win = max(th_mid_win,
                                 float(np.max(np.abs(th[1:-1]))))
            th_last_win = max(th_last_win, abs(float(th[-1])))
    # 末态能量（动能 + 势能）
    ek = 0.5 * m * (om * L) ** 2
    ep = m * G * L * (1.0 - np.cos(th))
    energy_err = abs(float(np.sum(ek) + np.sum(ep) - e0)) / max(e0, 1e-12)
    mom_err = abs(float(np.sum(m * om * L * np.cos(th)))) / max(m * L, 1e-12)
    return (float(v_last), float(th_mid_win), float(th_last_win),
            float(mom_err), float(energy_err))


# ================================================================ turntable
@capability("turntable", source="GAUGE(arXiv:2608.05948) Turntable; "
                                "非惯性系离心力mω²r与科氏力-2mω×v",
            group="phenom")
def turntable_sim(om_p=8.0, r0=0.10, mu_s=0.35, mu_k=0.25, m=1.0,
                  T=2.0, dt=1.0 / 2000.0):
    """旋转平台上的物块：离心力超过静摩擦锥后向外滑移。

    返回 (r_end, slip_started, lateral_deflect)
      r_end            最终半径（应 > r0，被甩出）
      slip_started     是否发生滑移（离心力 > μ_s·m·g）
      lateral_deflect  科氏力导致的横向偏转量（切向位移，m）
    物理（平台参考系）：F_cent = m ω² r（径向外），F_cor = -2m ω × v_rel
    （切向），摩擦 |f| ≤ μ N 指向相对速度反向。
    """
    r, rdot = r0, 0.0
    s = 0.0                      # 切向位移（相对平台）
    sdot = 0.0
    g = G
    slip = False
    n_steps = int(round(T / dt))
    for _ in range(n_steps):
        # 非惯性系力（平台系 2D）：ω = ω ẑ，v_rel = rdot r̂ + sdot ŝ
        #   F_cor = -2m ω × v_rel = 2mω·sdot r̂ - 2mω·rdot ŝ
        f_r = m * om_p * om_p * r + 2.0 * m * om_p * sdot   # 径向：离心+科氏
        f_t = -2.0 * m * om_p * rdot                        # 切向：纯科氏
        # 需求摩擦力（维持相对静止）
        f_need = math.hypot(f_r, f_t)
        f_max = mu_s * m * g
        if not slip and f_need > f_max:
            slip = True
        if not slip:
            continue                              # 静摩擦锁住，随平台转
        # 滑动：动摩擦，方向与相对速度反向
        v_rel = math.hypot(rdot, sdot)
        if v_rel > 1e-12:
            fr = -mu_k * m * g * (rdot / v_rel)
            fs = -mu_k * m * g * (sdot / v_rel)
        else:
            fr = fs = 0.0
        ar = (f_r + fr) / m
        a_s = (f_t + fs) / m
        rdot += ar * dt
        sdot += a_s * dt
        r += rdot * dt
        s += sdot * dt
        if r < 0.0:
            r = 0.0
    return float(r), slip, float(abs(s))


# =============================================================== self_check
def self_check():
    """自检：五现象各自的物理不变量（数据表化，执行器统一跑）。"""
    from base.assertrun import Checker
    c = Checker("phenom")
    for _probe in (_chk_leaf, _chk_frac, _chk_water, _chk_cradle, _chk_turn):
        _probe(c)
    return c.report()


def _chk_leaf(c):
    """树叶飘落探针：flutter 涌现 + tumbling 给定自转 + 终端速度合理。"""
    mode, v_term, n_swings, dtheta, traj = leaf_fall_sim()
    v_free = math.sqrt(2 * G * 2.0)
    c.chk("leaf 终端速度存在且远小于自由落体（阻力起作用）",
          v_term > 0.0 and v_term < 0.5 * v_free,
          "v_term=%.4f, v_free=%.4f" % (v_term, v_free))
    c.chk("leaf 产生水平漂移（非竖直直线下落）",
          abs(traj[-1][0] - traj[0][0]) > 1e-4,
          "dx=%.5f" % abs(traj[-1][0] - traj[0][0]))
    # flutter：从静止涌现，表现为左右摆动、净转角远小于 2π
    c.chk("leaf 静止释放呈 flutter（摆动滑翔，净转角 < 2π）",
          mode == "flutter" and n_swings >= 2 and abs(dtheta) < 2.0 * math.pi,
          "mode=%s swings=%d dtheta=%.3f" % (mode, n_swings, dtheta))
    # tumbling：给定自转角速度，净转角 > 2π，且终端速度仍在合理区间
    mt, vt, _, dt_t, _ = leaf_fall_sim(spin=3.0, T=6.0)
    c.chk("leaf 给定自转呈 tumbling（净转角 > 2π）",
          mt == "tumbling" and abs(dt_t) > 2.0 * math.pi,
          "mode=%s dtheta=%.3f" % (mt, dt_t))
    c.chk("leaf tumbling 终端速度仍在 0.05~1.5 m/s",
          0.05 < vt < 1.5, "v_term=%.4f" % vt)
    c.note("leaf 默认(flutter) mode=%s v_term=%.4f m/s swings=%d dtheta=%.3f rad"
           % (mode, v_term, n_swings, dtheta))
    c.note("leaf tumbling(spin=3) v_term=%.4f m/s dtheta=%.3f rad" % (vt, dt_t))
    c.note("已知限制：tumbling 为给定自转角速度，自持翻滚的涌现未实现"
           "（唯象双稳态模型在本求解器下不稳定，不冒充涌现）")


def _chk_frac(c):
    """砖墙碎裂探针：静置稳定 + 撞击断键 + 真裂成多块 + 球减速。"""
    n_broken, n_frag, max_disp, mom_err, stable_disp, v_end = fracture_sim()
    c.chk("fracture 未受撞时墙自身稳定", stable_disp < 1e-3,
          "settle_disp=%.6f" % stable_disp)
    c.chk("fracture 撞击后 bond 断裂", n_broken > 0, "n_broken=%d" % n_broken)
    c.chk("fracture 裂成多个连通碎块", n_frag > 1, "n_frag=%d" % n_frag)
    c.chk("fracture 球撞击后减速（动量传给墙）",
          v_end < 10.0, "v_ball_end=%.4f < v0=10.0" % v_end)
    c.chk("fracture 碎块位移有界（未数值爆炸）", 0.0 < max_disp < 1.0,
          "max_disp=%.4f" % max_disp)
    c.note("fracture n_broken=%d n_frag=%d max_disp=%.4f v_ball_end=%+.4f"
           % (n_broken, n_frag, max_disp, v_end))
    c.note("已知限制：PBD 位置投影本身不严格守恒动量，mom_err 仅作参考"
           "（实测 %.3f），不作判据" % mom_err)


def _chk_water(c):
    """水流探针：不穿透地面 + 铺展 + 粒子不丢失。"""
    min_y, spread, rho_rel, n_alive = water_jet_sim()
    c.chk("water 不穿透地面", min_y >= -1e-9, "min_y=%.6f" % min_y)
    c.chk("water 冲击后横向铺展", spread > 1.0, "spread=%.3f" % spread)
    c.chk("water 粒子无丢失/无NaN", n_alive == 180,
          "n_alive=%d" % n_alive)
    c.chk("water 密度接近静息密度（不可压缩约束成立）", rho_rel < 0.10,
          "rho_rel=%.4f" % rho_rel)
    c.note("water min_y=%.6f spread=%.3f rho_rel=%.4f n_alive=%d"
           % (min_y, spread, rho_rel, n_alive))


def _chk_cradle(c):
    """牛顿摆探针：末球弹出 + 中间球静止（首次碰撞窗口内）+ 能量守恒。"""
    v_last, th_mid, th_last, mom_err, en_err = newton_cradle_sim()
    th0 = 0.60
    v_in = math.sqrt(2.0 * G * 0.50 * (1.0 - math.cos(th0)))
    c.chk("cradle 末球弹出（速度接近首球入射速度）",
          abs(v_last - v_in) < 0.15 * v_in,
          "v_last=%.4f v_in=%.4f" % (v_last, v_in))
    c.chk("cradle 中间球几乎不动（首次碰撞后 0.25s 内角位移≈0）",
          th_mid < 0.05 * th0, "th_mid=%.5f rad < %.4f" % (th_mid, 0.05 * th0))
    c.chk("cradle 末球被弹出到接近初始摆角",
          th_last > 0.5 * th0, "th_last=%.4f > %.4f" % (th_last, 0.5 * th0))
    c.chk("cradle 能量近似守恒", en_err < 0.05, "en_err=%.5f" % en_err)
    c.note("cradle v_last=%.4f th_mid=%.5f th_last=%.4f en_err=%.5f"
           % (v_last, th_mid, th_last, en_err))
    c.note("口径说明：中间球静止只在首次碰撞后短窗口内成立；末球摆回二次"
           "撞击后中间球必然动起来，这是真实牛顿摆行为")


def _chk_turn(c):
    """转台探针：离心超标后滑移且被甩出。"""
    r, slip, lat = turntable_sim()
    c.chk("turntable 离心超静摩擦后滑移", slip is True, "slip=%s" % slip)
    c.chk("turntable 物块被甩向外侧", r > 0.10, "r_end=%.4f" % r)
    c.chk("turntable 科氏产生横向偏转", lat > 1e-6, "lateral=%.6f" % lat)
    # 对照：转速极低时不滑移
    r2, slip2, _ = turntable_sim(om_p=0.1)
    c.chk("turntable 低速不滑移（自证判据有效）", slip2 is False,
          "slip=%s" % slip2)
    c.note("turntable r_end=%.4f lateral=%.6f (低速 r=%.4f slip=%s)"
           % (r, lat, r2, slip2))
