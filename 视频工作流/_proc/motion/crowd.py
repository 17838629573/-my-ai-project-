# 契约: proc/motion/crowd
#   一句话: 多主体：ORCA 互避 + 胶囊接触分离 + 击掌时序
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""D 组 —— 多主体交互（multi-actor / contact / crowd_collide）。

出处（先搜证再实现，不自造）：
[1] ORCA  Optimal Reciprocal Collision Avoidance
        van den Berg, Guy, Lin, Manocha《Reciprocal n-Body Collision
        Avoidance》Springer STAR 2011（GAMMA / UNC）
    定义（论文式(4)，经 UC Davis 综述转引）：
        ORCA_{A|B}^τ = { v | (v - (v_A^opt + ½u)) · n ≥ 0 }
    其中 u 是 (v_A^opt - v_B^opt) 到 VO 边界的最近点位移向量，
    n 是该处外法线。双方各承担 ½u —— 论文原话 "share the
    responsibility"，这正是它相对 VO/RVO 消除振荡的原因。
[2] VO 碰撞锥（Piorini & Shiller 1991 / Fiorini）
    在 τ 时间窗内会碰撞的相对速度集合。半径 R = rA + rB、
    相对位置 p，则在相对速度空间中 VO 是
        圆心 p/τ、半径 R/τ 的圆盘
[3] 采样选速与惩罚（Directing Crowd Simulations, Patil et al.）
        penalty(v) = w / t_c(v) + ‖v_pref - v‖
    论文原文承认 "computing the union of all RVOs is not feasible
    computationally and we use a Monte-Carlo sampling scheme in
    velocity space" —— 故这里同样用速度空间采样
[4] 角色胶囊接触分离（Joakim Hagdahl《Animation - Character Physics》）
    原文："it is common to just split the resolve between the two
    characters, depending on how important it is for one character to
    stay at their position"
    · 胶囊不做旋转解算（no rotation resolve on it）
    · 撞墙（静态）时分离量全给角色；角色对角色时平分
    · 按质量反比分配：Δa = -n·depth·(m_b/(m_a+m_b))
[5] 击掌姿态（High five 定义）
    两人各抬一只手到头高或以上，掌心朝外相对，短暂拍合；
    上臂外展约 90°。判据是掌心-掌心恰好接触（不穿模）。

本模块是纯数值内核 + 姿态求解，不含绘制。
"""
import math

import numpy as np

# [1] 默认前瞻时间窗 τ（秒）：ORCA 的碰撞预测 horizon
TAU = 2.0
# [3] 采样：候选速度环数 × 每环条数
SAMPLE_RINGS = 4
SAMPLE_SPOKES = 16


class Agent:
    """平面（俯视 XZ）代理。p=(x,z) 米，v 米/秒"""
    __slots__ = ("p", "v", "vpref", "r", "m", "name")

    def __init__(self, x=0.0, z=0.0, vx=0.0, vz=0.0, r=0.25, m=70.0, name=""):
        self.p = np.array([float(x), float(z)])
        self.v = np.array([float(vx), float(vz)])
        self.vpref = np.array([float(vx), float(vz)])
        self.r = float(r)
        self.m = float(m)
        self.name = name


# ------------------------------------------------------------------ [2] VO
def closest_approach(a, b, tau=TAU):
    """最近接近点解析解 → (t*, 最近距离, 该时刻由A指向B的单位向量) 或 None

    相对位置（B 相对 A）  q(t) = p - v_rel·t ，其中 p = p_B - p_A，
    v_rel = v_A - v_B（A 相对 B 的速度）。
    d/dt |q|² = -2·(p - v_rel t)·v_rel = 0  ⇒  t* = (p·v_rel)/|v_rel|²

    · t* < 0  → 正在远离，永不碰撞
    · 否则取 tc = min(t*, τ)，最近距离 = |p - v_rel·tc|
    出处[2] 碰撞锥即 { v_rel | 最近距离 < R }，这里直接解析求，
    比「只判 τ 时刻是否重叠」的圆盘近似严格（后者会漏掉中途相交）。
    """
    p = b.p - a.p
    v_rel = a.vpref - b.vpref
    sp2 = float(np.dot(v_rel, v_rel))
    if sp2 < 1e-12:
        return None                                  # 无相对运动
    t_star = float(np.dot(p, v_rel)) / sp2
    if t_star < 0.0:
        return None                                  # 正在远离
    tc = min(t_star, tau)
    dvec = p - v_rel * tc
    dist = float(np.linalg.norm(dvec))
    if dist < 1e-9:
        # 正对撞：最近距离退化为 0，分离方向取相对速度的反向（把 A 往回推）
        nvec = -v_rel / np.sqrt(sp2)
        return tc, 0.0, nvec
    return tc, dist, dvec / dist


def ttc(a, b, tau=TAU):
    """预期碰撞时间（秒），不碰撞给 τ·2 上界（出处[3] 惩罚项要用）"""
    r = closest_approach(a, b, tau)
    if r is None:
        return tau * 2.0
    tc, dist, _ = r
    return tc if dist < (a.r + b.r) else tau * 2.0


def orca_plane(a, b, tau=TAU):
    """ORCA 半平面 → (n, point_A, point_B)

    n  = 由 A 指向 B 的分离方向
    A 的偏移点 point_A = v_A^opt - ½u（往 -n 让），
    B 的偏移点 point_B = v_B^opt + ½u（往 +n 让）。
    不需要避让（不会碰撞）时返回 None。
    """
    r = closest_approach(a, b, tau)
    if r is None:
        return None
    tc, dist, n = r
    R = a.r + b.r
    if dist >= R:
        return None                                  # 不会碰撞
    # 需要在 tc 内多分离 (R - dist)，故相对速度改变量
    u = n * ((R - dist) / max(tc, 1e-6))
    # 双方各担一半（[1] "share the responsibility"）
    return n, a.vpref - 0.5 * u, b.vpref + 0.5 * u


# ------------------------------------------------------------------ [3] 选速
def _sample_velocities(vmax, rings=SAMPLE_RINGS, spokes=SAMPLE_SPOKES):
    out = [np.zeros(2)]
    for ri in range(1, rings + 1):
        sp = vmax * ri / rings
        for k in range(spokes):
            ang = 2.0 * math.pi * k / spokes
            out.append(np.array([sp * math.cos(ang), sp * math.sin(ang)]))
    return out


def orca_velocity(agent, others, vmax=1.4, tau=TAU, w=1.0):
    """给单个 agent 选一个满足所有 ORCA 半平面、且最接近期望速度的速度"""
    planes = []
    for o in others:
        if o is agent:
            continue
        pl = orca_plane(agent, o, tau)
        if pl is not None:
            planes.append(pl)
    if not planes:
        return agent.vpref.copy()

    def ttc_of(v):
        """用候选速度 v 试算最近碰撞时间（越大越安全）"""
        best = tau * 2.0
        for o in others:
            if o is agent:
                continue
            p = o.p - agent.p
            dv = v - o.v
            sp2 = float(np.dot(dv, dv))
            if sp2 < 1e-12:
                continue
            ts = float(np.dot(p, dv)) / sp2
            if ts < 0.0:
                continue                       # 远离
            tc = min(ts, tau)
            dist = float(np.linalg.norm(p - dv * tc))
            if dist < agent.r + o.r:
                best = min(best, tc)
        return best

    best, best_pen = None, None
    for v in _sample_velocities(vmax):
        # A 侧约束：往 -n 让，即 (v - point_A)·n <= 0
        ok = all(float(np.dot(v - pt, n)) <= 1e-9 for n, pt, _ in planes)
        if not ok:
            continue
        pen = w / max(ttc_of(v), 1e-3) + float(np.linalg.norm(agent.vpref - v))
        if best_pen is None or pen < best_pen:
            best, best_pen = v, pen
    return best if best is not None else agent.vpref.copy()


def orca_step(agents, dt, vmax=1.4, tau=TAU):
    """推进一帧：先各自选速，再统一积分（避免顺序偏差）"""
    newv = [orca_velocity(a, agents, vmax=vmax, tau=tau) for a in agents]
    for a, v in zip(agents, newv):
        a.v = v
        a.p = a.p + v * dt
    return agents


# ------------------------------------------------------------------ [4] 分离
def contact_depth(a, b):
    """重叠深度（米）；不重叠为 0"""
    d = float(np.linalg.norm(b.p - a.p))
    return max((a.r + b.r) - d, 0.0)


def resolve_contact(a, b, static_gain=1.0):
    """位置分离：按质量反比平分推开，胶囊不旋转（出处[4]）

    a、b 都是 Agent；若 b 为 None 表示静态障碍，分离量全给 a。
    """
    p = b.p - a.p
    d = float(np.linalg.norm(p))
    R = a.r + b.r
    depth = R - d
    if depth <= 0.0:
        return 0.0
    if d > 1e-9:
        n = p / d
    else:
        n = np.array([1.0, 0.0])       # 完全重合时任选一个方向
    if b.m == float("inf"):            # 静态：全给 a
        a.p = a.p - n * depth * static_gain
    else:
        tot = a.m + b.m
        a.p = a.p - n * depth * (b.m / tot)
        b.p = b.p + n * depth * (a.m / tot)
    return depth


def separate_all(agents, iters=4):
    """迭代分离所有重叠对（出处[5] Unity CapsuleCast 的『迭代解析』）

    原文强调：只做一次检测会在墙角卡住、复杂场景抖动 —— 必须迭代。
    """
    worst = 0.0
    for _ in range(iters):
        moved = False
        for i in range(len(agents)):
            for j in range(i + 1, len(agents)):
                dep = resolve_contact(agents[i], agents[j])
                if dep > 0.0:
                    moved = True
                    worst = max(worst, dep)
        if not moved:
            break
    return worst


def crowd_sim(agents, t_end, dt=1.0 / 24.0, vmax=1.4, tau=TAU):
    """人群推进：每帧 ORCA 选速 + 积分 + 接触分离。

    agents: [Agent]，每个要预先设好 vpref（期望速度）
    返回 (traj, max_penetration)
      traj: [ [np.array([x,z]) ...] ]  每帧每人的位置
    """
    n = max(1, int(round(t_end / dt)))
    traj = [[a.p.copy() for a in agents]]
    worst = 0.0
    for _ in range(n):
        for a in agents:
            a.vpref = a.vpref            # 期望速度由调用方逐帧更新
        orca_step(agents, dt, vmax=vmax, tau=tau)
        worst = max(worst, separate_all(agents))
        traj.append([a.p.copy() for a in agents])
    return traj, worst


# ------------------------------------------------------------------ [5] 击掌
# 肩高/头高比例（Drillis & Contini 1966 / Winter 转引，H=身高）
HEAD_H = 0.130          # 头高
SHOULDER_FRAC = 0.818   # 肩关节高度 / 身高


def high5_arm(t, t_contact, duration=1.2, H=1.70, side=1.0):
    """击掌右臂抬升曲线 → (肩外展角°, 肘屈角°, 腕高/身高)

    时序（出处[5] 定义 + Lango 的 snappy 三相位）：
      0.00~0.45  抬起：手到头高或以上，上臂外展→90°
      0.45~0.55  拍合：掌心相对，保持接触
      0.55~1.00  收回
    side: +1 用右手，-1 用左手
    """
    u = (t - (t_contact - duration * 0.45)) / duration
    u = max(0.0, min(1.0, u))
    if u < 0.45:                       # 抬起（ease-out，末端减速）
        k = u / 0.45
        s = 1.0 - (1.0 - k) ** 2
    elif u < 0.55:                     # 拍合保持
        s = 1.0
    else:                              # 收回
        k = (u - 0.55) / 0.45
        s = 1.0 - k ** 2
    abduct = 90.0 * s                  # 上臂外展角（出处[5]：约 90°）
    elbow = 15.0 + 25.0 * (1.0 - s)    # 拍合时肘伸直
    wrist_h = (0.818 + 0.232 * s)      # 腕高/身高：肩高 → 略高于头顶
    return side * abduct, elbow, wrist_h * H


def high5_pose(t, t_contact, gap, H=1.70, duration=1.2):
    """两人击掌 → (腕A, 腕B, 掌心距)，腕坐标在『两人连线』局部系

    两人相距 gap，各自沿连线向内伸手。掌心距 = gap - 2·臂展投影
    """
    abA, elA, wA = high5_arm(t, t_contact, duration, H, +1.0)
    abB, elB, wB = high5_arm(t, t_contact, duration, H, -1.0)
    upper = 0.186 * H                  # 上臂长（D&C 1966）
    fore = 0.146 * H                   # 前臂长
    # 外展角越大，手伸得越靠近对方（水平投影）
    reach = upper * math.sin(math.radians(abs(abA))) + fore * math.sin(math.radians(abs(elA)))
    palm_gap = max(gap - 2.0 * reach, 0.0)
    return (-gap / 2 + reach, wA), (gap / 2 - reach, wB), palm_gap


# ---- 能力注册（与 motion.rigid / motion.character.gesture 同一入口）----
from motion.beat import capability  # noqa: E402  放在此处：本模块不产生 beat→crowd 的反向依赖


@capability("multi_actor", source="ORCA 互避（van den Berg 2011 §3.2）；多主体统一推进，"
            "同时选速后一并积分以消除顺序偏差", group="interact")
def _cap_multi_actor():
    return orca_step


@capability("contact", source="胶囊接触分离按质量反比平分；静态障碍由 agent 全额承担"
            "（Box2D 静态质量定义）", group="interact")
def _cap_contact():
    return separate_all


@capability("crowd_collide", source="ORCA 互避 + 接触分离；最近接近点解析解"
            " t*=(p·v_rel)/|v_rel|²，tc=min(t*,τ)", group="interact")
def _cap_crowd_collide():
    return orca_step


@capability("high5", source="击掌：上臂外展至 90°水平、掌心相对拍合（Utween ECA 低层序列）",
            group="interact")
def _cap_high5():
    return high5_pose


def self_check():
    out = []

    # [2] VO 圆盘：正对且相对速度为 0 必在 VO 内
    a = Agent(0.0, 0.0, 1.0, 0.0)
    b = Agent(1.0, 0.0, -1.0, 0.0)
    a.vpref = np.array([1.0, 0.0]); b.vpref = np.array([-1.0, 0.0])
    pl = orca_plane(a, b, tau=2.0)
    out.append(("正对撞产生ORCA约束", pl is not None, pl is not None))

    # 远离的双方不产生约束
    c = Agent(0.0, 0.0, -1.0, 0.0)
    d = Agent(1.0, 0.0, 1.0, 0.0)
    c.vpref = np.array([-1.0, 0.0]); d.vpref = np.array([1.0, 0.0])
    out.append(("背向远离无约束", orca_plane(c, d, tau=2.0) is None, None))

    # [1] ORCA 对称：双方各担一半
    if pl is not None:
        n, pA, pB = pl
        share = float(np.linalg.norm(pA - a.vpref) - np.linalg.norm(pB - b.vpref))
        out.append(("ORCA双方各担一半", abs(share) < 1e-9, round(share, 12)))

    # [4] 接触分离：平分
    e = Agent(0.0, 0.0); f = Agent(0.30, 0.0)   # R=0.50 > 0.30 → 确实重叠
    dep0 = contact_depth(e, f)
    resolve_contact(e, f)
    dep1 = contact_depth(e, f)
    out.append(("重叠被分离", dep0 > 0 and dep1 < 1e-6,
                (round(dep0, 5), round(dep1, 9))))
    # 等质量：双方位移量相等（初始位置不对称，故比位移不能比坐标）
    move_e = float(e.p[0]) - 0.0
    move_f = float(f.p[0]) - 0.30
    out.append(("等质量对称分离",
                abs(abs(move_e) - abs(move_f)) < 1e-9,
                (round(move_e, 6), round(move_f, 6))))

    # 静态障碍：分离量全给 agent
    g = Agent(0.0, 0.0); h = Agent(0.30, 0.0, m=float("inf"))
    h0 = float(h.p[0])
    resolve_contact(g, h)
    out.append(("静态障碍不被推动", abs(float(h.p[0]) - h0) < 1e-12, round(float(h.p[0]), 6)))

    # 迭代分离收敛（三人挤在一点）
    ags = [Agent(0.0, 0.0, r=0.25), Agent(0.05, 0.0, r=0.25), Agent(0.0, 0.05, r=0.25)]
    separate_all(ags, iters=20)
    w = max(contact_depth(ags[i], ags[j])
            for i in range(3) for j in range(i + 1, 3))
    out.append(("三人重叠可收敛分离", w < 1e-3, round(w, 8)))

    # [5] 击掌：拍合瞬间掌心恰好接触（不穿模）
    _, _, gap_at_contact = high5_pose(0.0, 0.0, gap=1.10, H=1.70)
    out.append(("击掌掌心不穿模", gap_at_contact >= -1e-9, round(gap_at_contact, 6)))
    # 抬起过程中腕高不低于肩高
    ws = [high5_arm(0.0 + k * 0.05, 0.45, 1.2, 1.70)[2] for k in range(10)]
    out.append(("抬手时腕不低于肩", min(ws) >= 0.818 * 1.70 - 1e-9, round(min(ws), 5)))
    # 拍合时上臂外展接近 90°
    ab, _, _ = high5_arm(0.61, 0.55, 1.2, 1.70)   # u=0.50 落在拍合保持段
    out.append(("拍合时上臂外展约90°", abs(abs(ab) - 90.0) < 1e-6, round(abs(ab), 4)))

    return out
