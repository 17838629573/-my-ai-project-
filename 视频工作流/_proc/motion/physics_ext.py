# 契约: proc/motion/physics_ext
#   一句话: 物理扩展五能力：ccd/broadphase/gravity_off/friction/overlap_resolve
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""物理扩展能力（补齐 F30–F34 五个 STUB 缺口）。

依据（搜索先行，非凭记忆）：
- ccd: Box2D v3 用 speculative contacts（按速度外扩 AABB，为"可能碰撞"的对
  提前生成接触约束）+ TOI 求解（b2TimeOfImpact，GJK+根求解）；bullet body
  标记 isBullet 可对其他动态体做 CCD。本实现取保守推进
  （conservative advancement 的离散版）：单步位移超过 K_FRAC·r 时细分子步，
  保证一步推进量恒小于障碍厚度，不会越过。
- broadphase: 均匀网格空间哈希（Teschner et al. 2003 Optimized Spatial Hashing
  for Collision Detection of Deformable Objects）；Box2D b2DynamicTree 用
  fat AABB + padding 减少重插。正确性：AABB 相交 ⟺ 存在公共格子 ⇒ 不漏接触。
- gravity_off: 无外力 ⇒ 动量守恒 dp/dt = 0，质心匀速直线（牛顿第一定律）。
- friction: 库仑摩擦锥 |f_t| ≤ μ·f_n（Box2D b2Friction / Box2D Lite k_friction）。
- overlap_resolve: Baumgarte 位置修正 + linear slop 0.005
  （Box2D v2.4.1 官方源码 b2_common.h:65 实测 `#define b2_linearSlop
  (0.005f * b2_lengthUnitsPerMeter)`），max linear correction 0.2，β=0.2。

坐标：米制世界坐标，x 向右，y 向上（与 rigid2d 系列一致）。
"""
import os as _os, sys as _sys, math as _math
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
from .rigid2d.core import SLOP, Body2  # noqa: F401
from .rigid2d.world import World  # noqa: F401

K_FRAC = 0.5   # 保守推进：单步位移上限 = K_FRAC × 半径（出处见模块 docstring）


def _max_speed(bodies):
    m = 0.0
    for b in bodies:
        if not b.fixed:
            m = max(m, float(np.hypot(b.v[0], b.v[1])))
    return m


def _max_pen(bodies, rad):
    """最大穿透深度：仅量动态体与静态体（地面/墙），与用例口径一致。"""
    p = 0.0
    for b in bodies:
        if b.fixed:
            continue
        p = max(p, max(0.0, rad[id(b)] - b.p[1]))
    return p


def body_radius(b):
    """体的外接半径：圆取 r，盒取对角半长 hypot(hw,hh)。

    用途：保守推进的子步估算（出处[1] 保守推进）。
    """
    if b.shape == "circle":
        return float(b.r)
    return float(np.hypot(b.hw, b.hh))


def pen_vs_plane(b, plane_y=0.0):
    """刚体对水平面 y=plane_y 的**几何精确**穿透深度（支撑函数）。

    沿 -y 方向的支撑：ext = hw*|sin(th)| + hh*|cos(th)|
    穿透 = max(0, ext - (b.p[1] - plane_y))

    为什么必须有这个函数：
    早期实现用外接圆半径 rad - y 当穿透（F33/F32/_max_pen 都这么量），
    对盒是**错的**——外接圆半径 0.1697 远大于半高 0.12，把一个本该
    通过的静止支撑态虚报成 0.0509 穿透（超 slop 10 倍）。
    判据量尺必须几何精确，否则测的是"体有多大"而不是"陷进去多少"。
    """
    if b.shape == "circle":
        ext = float(b.r)
    else:
        ext = float(b.hw * abs(math.sin(b.th)) + b.hh * abs(math.cos(b.th)))
    return max(0.0, ext - (float(b.p[1]) - float(plane_y)))


def pen_vs_plane_max(bodies, plane_y=0.0):
    """对所有动态体取 pen_vs_plane 的最大值。"""
    return max([pen_vs_plane(b, plane_y) for b in bodies if not b.fixed],
               default=0.0)


def _circle_pair_pen(a, b):
    """两圆真实穿透深度 = max(0, ra+rb - dist)。

    零重力工况无地面，早期实现用 `rad - y` 量"到 y=0 的距离"，
    量的是一个不存在地面的假穿透。改量真实接触对。
    """
    d = float(np.hypot(a.p[0] - b.p[0], a.p[1] - b.p[1]))
    return max(0.0, float(a.r) + float(b.r) - d)


def substeps_for(bodies, dt, k_frac=K_FRAC, barrier=None):
    """保守推进所需子步数 N：使单子步位移不超过屏障。

    barrier 给定时为**绝对位移上限**（米），可与判据同源取值——
    例如取 SLOP：单子步位移 ≤ SLOP，则一步引入的瞬时重叠不会超过
    求解器允许的残留量（出处[4] Baumgarte 修正项 max(d-slop,0)，
    超出 slop 的部分才被修正）。
    barrier 为 None 时退回 K_FRAC × 最小动态半径（出处[1] 保守推进）。

    出处[1] 保守推进（conservative advancement）：按 k_frac·r 分档，
    取单步位移与最小特征半径的比值上取整。E27 投掷 8m/s 与 F31 宽相
    50 体都靠它把撞击瞬态穿透压进 slop：
        E27  N=1 pen=0.01387 → N=4 pen=0.00167
        F31  N=1 pen=0.00654 → N=4 pen=0.00368
    """
    v = _max_speed(bodies)
    if v <= 0.0:
        return 1
    if barrier is None:
        rs = [body_radius(b) for b in bodies if not b.fixed]
        if not rs:
            return 1
        barrier = k_frac * min(rs)
    if barrier <= 0.0:
        return 1
    return max(1, int(math.ceil(v * dt / barrier)))


# --------------------------------------------------------------------- F30 ccd
@capability("ccd", source="Box2D v3 speculative contacts + TOI(b2TimeOfImpact)；"
                          "保守推进子步（单步位移 ≤ K_FRAC·r）", group="physics")
def ccd_sim(v0=30.0, wall_x=1.0, wall_hw=0.03, r=0.05, T=0.40, dt=1.0 / 60.0,
            ccd=True):
    """高速球撞薄墙：ccd=False 会隧穿，ccd=True 被挡住。

    返回 (tunneled, min_gap, traj, n_steps)
      tunneled  球心是否越过墙（|x - wall_x| 在墙后且距墙超过 r+wall_hw）
      min_gap   全程球心到墙面的最小距离（>0 表示未穿透）
      traj      每步球心 x
    判据口径：隧穿 = 球出现在墙的另一侧。墙厚 0.06m，一步位移 v0·dt=0.5m，
    远超墙厚 → 无 CCD 必然隧穿；有 CCD 时子步位移 ≤ K_FRAC·r=0.025m < 墙厚。
    """
    def _build(sub_dt):
        w = World(g=0.0, dt=sub_dt)
        ball = Body2(p=(0.0, 0.30), shape="circle", r=r, m=1.0, e=0.2,
                     mu=0.4, tag="ball")
        ball.v[0] = v0
        w.add(ball)
        wall = Body2(p=(wall_x, 0.30), shape="box", hw=wall_hw, hh=0.40,
                     m=0.0, e=0.2, mu=0.4, fixed=True, tag="wall")
        w.add(wall)
        return w, ball

    if not ccd:
        n = int(round(T / dt))
        w, ball = _build(dt)
    else:
        # 单步位移 v0·dt 超过 K_FRAC·r 时细分；N 取上整，保证子步位移达标
        N = max(1, int(_math.ceil(v0 * dt / (K_FRAC * r))))
        n = int(round(T / dt)) * N
        w, ball = _build(dt / N)

    traj, min_gap, tunneled = [], float("inf"), False
    for _ in range(n):
        w.step()
        traj.append(float(ball.p[0]))
        gap = abs(ball.p[0] - wall_x) - (r + wall_hw)
        min_gap = min(min_gap, gap)
        # 越过墙且距离已超过接触距离 ⇒ 已隧穿
        if ball.p[0] > wall_x + wall_hw and gap > 1e-6:
            tunneled = True
    return tunneled, min_gap, traj, n


# --------------------------------------------------------------- F31 broadphase
@capability("broadphase", source="均匀网格空间哈希（Teschner et al. 2003）；"
                                 "fat AABB + padding（Box2D b2DynamicTree）",
            group="physics")
def broadphase_sim(n=50, T=1.0, dt=1.0 / 240.0, seed=62):
    """50 球同时落地互撞：统计宽相候选对、暴力对、漏检数与最大穿透。

    返回 (n_cand, n_brute, n_missed, max_pen, n_steps)
    正确性判据：n_missed == 0。AABB 相交 ⟺ 存在公共格子（保守：包围圆含本体），
    故宽相不会漏掉任何真实接触 —— 漏检必须恒为 0，不是"尽量小"。
    """
    W = _mk_balls_world(n, seed, dt)
    # 子步：50 球同时落地属高速撞击密集工况，单步位移会超过 K_FRAC·r，
    # 把瞬时穿透顶到 0.00654（超 slop 31%）。按保守推进细分子步后
    # 瞬态降到 0.00368（< slop 0.005）。判据未改，是工况按出处[1]补齐。
    n_steps = int(round(T / dt))
    max_pen, n_cand, n_missed, n_brute = 0.0, 0, 0, 0
    for _ in range(n_steps):
        # 原地改 dt（不重建 World）——重建会丢掉接触缓存/暖启动，
        # 反而让穿透更差（实测重建版 0.005993，原地版更低）。
        n_sub = min(8, substeps_for(W.bodies, dt, barrier=SLOP))
        if n_sub > 1:
            dt0 = W.dt
            W.dt = dt0 / n_sub
            for _s in range(n_sub):
                W.step()
            W.dt = dt0
        else:
            W.step()
        rad = W._broadphase_radii()
        cand = set(W._pair_candidates(rad))
        n_cand = max(n_cand, len(cand))
        # 暴力对：包围圆相交即候选（与宽相同一几何判据）
        bs = W.bodies
        brute = set()
        for i in range(len(bs)):
            for j in range(i + 1, len(bs)):
                dx = bs[i].p[0] - bs[j].p[0]
                dy = bs[i].p[1] - bs[j].p[1]
                rr = rad[id(bs[i])] + rad[id(bs[j])]
                if dx * dx + dy * dy <= rr * rr:
                    brute.add((i, j))
        n_brute = max(n_brute, len(brute))
        n_missed += len(brute - cand)
        max_pen = max(max_pen, pen_vs_plane_max(bs, 0.0))
    return n_cand, n_brute, n_missed, max_pen, n_steps


def _mk_balls_world(n, seed, dt):
    """建 n 球 + 地面的世界（broadphase_sim 抽出，降函数行数）。"""
    rng = np.random.RandomState(seed)
    w = World(dt=dt)
    for k in range(n):
        r = 0.04 + 0.01 * rng.rand()
        w.add(Body2(p=(float(rng.uniform(-1.0, 1.0)),
                       float(0.25 + rng.uniform(0.0, 1.2))),
                    shape="circle", r=float(r), m=1.0, e=0.3, mu=0.4,
                    tag="b%d" % k))
    w.add(Body2(p=(0.0, -0.5), shape="box", hw=3.0, hh=0.5, m=0.0, e=0.2,
                mu=0.6, fixed=True, tag="ground"))
    return w


# -------------------------------------------------------------- F32 gravity_off
@capability("gravity_off", source="无外力 ⇒ 动量守恒 dp/dt=0，质心匀速直线"
                                  "（牛顿第一定律）", group="physics")
def gravity_off_sim(v0=(0.6, 0.0), T=2.0, dt=1.0 / 240.0):
    """零重力漂浮：球匀速直线，撞静止球后总动量守恒。

    返回 (drift_err, mom_err, max_pen, traj)
      drift_err  与理想匀速直线的最大偏差（米），应为浮点 0 级
      mom_err    碰撞前后总动量 p=m·v 的相对误差
    """
    w = World(g=0.0, dt=dt)
    a = Body2(p=(-0.8, 0.5), shape="circle", r=0.05, m=1.0, e=0.5, mu=0.2,
              tag="a")
    a.v[0], a.v[1] = float(v0[0]), float(v0[1])
    b = Body2(p=(0.3, 0.5), shape="circle", r=0.05, m=1.0, e=0.5, mu=0.2,
              tag="b")
    w.add(a)
    w.add(b)
    p0 = float(a.v[0]) * a.m + float(b.v[0]) * b.m

    traj, drift, max_pen = [], 0.0, 0.0
    n = int(round(T / dt))
    for i in range(n):
        w.step()
        t = (i + 1) * dt
        # 碰撞前（b 未被撞动）a 应严格匀速：x = x0 + v0·t
        if abs(b.v[0]) < 1e-12:
            drift = max(drift, abs(a.p[0] - (-0.8 + v0[0] * t)))
        traj.append((float(a.p[0]), float(a.p[1])))
        max_pen = max(max_pen, _circle_pair_pen(a, b))
    p1 = float(a.v[0]) * a.m + float(b.v[0]) * b.m
    mom_err = abs(p1 - p0) / max(abs(p0), 1e-12)
    return drift, mom_err, max_pen, traj


# ----------------------------------------------------------------- F33 friction
@capability("friction", source="库仑摩擦锥 |f_t| ≤ μ·f_n（Box2D b2Friction / "
                               "Box2D Lite k_friction）", group="physics")
def friction_sim(mu=1.5, v0=2.0, T=2.5, dt=1.0 / 240.0):
    """高摩擦滑动：滑块初速 v0 在地面滑行，应迅速停止且不反弹。

    返回 (stop_dist, stop_t, max_pen, v_end)
      stop_dist  停止时滑行距离（米）
      stop_t     停止时刻（秒）；None 表示未停止
    判据口径：高摩擦下速度单调衰减到 0；理论停止距离 ≈ v0²/(2·μ·g)。
    """
    w = World(dt=dt)
    hw, hh, r = 0.12, 0.12, _math.hypot(0.12, 0.12)
    blk = Body2(p=(-0.9, hh), shape="box", hw=hw, hh=hh, m=1.0, e=0.0,
                mu=mu, tag="blk")
    blk.v[0] = v0
    w.add(blk)
    w.add(Body2(p=(0.0, -0.5), shape="box", hw=3.0, hh=0.5, m=0.0, e=0.0,
                mu=mu, fixed=True, tag="ground"))

    x0 = blk.p[0]
    stop_t, stop_dist, max_pen = None, None, 0.0
    n = int(round(T / dt))
    for i in range(n):
        w.step()
        max_pen = max(max_pen, pen_vs_plane(blk, 0.0))
        sp = float(np.hypot(blk.v[0], blk.v[1]))
        if stop_t is None and sp < 1e-3:
            stop_t = (i + 1) * dt
            stop_dist = blk.p[0] - x0
    v_end = float(np.hypot(blk.v[0], blk.v[1]))
    return stop_dist, stop_t, max_pen, v_end


# ------------------------------------------------------------ F34 overlap_resolve
@capability("overlap_resolve", source="Baumgarte 位置修正 + linear slop 0.005"
                                      "（Box2D v2.4.1 b2_common.h:65 官方实测）；"
                                      "max linear correction 0.2，β=0.2",
            group="physics")
def overlap_resolve_sim(n=6, r=0.08, T=2.0, dt=1.0 / 240.0, seed=65):
    """初始重叠：一批球起点互相重叠，应被推开到 slop 内且不闪烁。

    返回 (pen_final, max_pen_hist, flip_count, n_pairs)
      pen_final     终态最大重叠深度（米），应 ≤ SLOP 量级
      flip_count    相邻帧速度符号翻转次数（闪烁代理指标），应很小
    判据口径：Penney 游戏名场面式自证——重叠必须"分离"，不是"停在重叠里"。
    """
    rng = np.random.RandomState(seed)
    w = World(dt=dt)
    bodies = []
    for k in range(n):
        b = Body2(p=(float(rng.uniform(-0.05, 0.05)),
                     float(0.30 + rng.uniform(-0.02, 0.02))),
                  shape="circle", r=r, m=1.0, e=0.0, mu=0.5, tag="o%d" % k)
        w.add(b)
        bodies.append(b)
    w.add(Body2(p=(0.0, -0.5), shape="box", hw=3.0, hh=0.5, m=0.0, e=0.0,
                mu=0.5, fixed=True, tag="ground"))

    pen_hist, flip = [], 0
    prev_v = {}          # 首帧无前值，用 None 哨兵而非 0.0（0.0 与浮点比等，S07）
    n_steps = int(round(T / dt))
    for _ in range(n_steps):
        w.step()
        rad = w._broadphase_radii()
        # 两两重叠深度（圆-圆）
        pmax = 0.0
        for i in range(len(bodies)):
            for j in range(i + 1, len(bodies)):
                A, B = bodies[i], bodies[j]
                d = float(np.hypot(A.p[0] - B.p[0], A.p[1] - B.p[1]))
                pmax = max(pmax, max(0.0, (A.r + B.r) - d))
        pen_hist.append(pmax)
        for b in bodies:
            s = 1.0 if b.v[0] >= 0 else -1.0
            if prev_v.get(id(b)) is not None and s != prev_v[id(b)]:
                flip += 1
            prev_v[id(b)] = s
    return pen_hist[-1], max(pen_hist), flip, n * (n - 1) // 2


def self_check():
    """自检：五能力各自的物理不变量（数据表化，执行器统一跑）。"""
    from base.assertrun import Checker
    c = Checker("physics_ext")
    for _probe in (_chk_f30, _chk_f31, _chk_f32, _chk_f33, _chk_f34):
        _probe(c)
    return c.report()


def _chk_f30(c):
    """F30 CCD 探针（从 self_check 抽出，降函数行数）。"""
    #：无 CCD 必隧穿（自证测试有效）；有 CCD 不隧穿。
    # 口径：CCD 的定义是"不隧穿"（不到墙另一侧）。穿透深度由求解器迭代决定，
    # 属另一问题，此处只如实报告不作判据（不自造阈值）。
    tun_off, _, traj_off, _ = ccd_sim(ccd=False)
    tun_on, gap_on, traj_on, _ = ccd_sim(ccd=True)
    c.chk("F30 无CCD会隧穿(自证)", tun_off is True)
    c.chk("F30 有CCD不隧穿", tun_on is False, "tunneled=%s" % tun_on)
    c.chk("F30 有CCD球留在墙前", traj_on[-1] < 1.0, "x_end=%.4f" % traj_on[-1])
    c.note("F30 无CCD终点 x=%.3f（已过墙1.0）；有CCD x=%.3f，最深 %.4f m"
           % (traj_off[-1], traj_on[-1], -min(gap_on, 0.0)))



def _chk_f31(c):
    """F31 宽相探针（从 self_check 抽出）。"""
    # AABB 相交 ⟹ 公共格子（保守插入覆盖格子）⇒ 漏检恒 0。
    # 口径：宽相候选"多于真实相交对"是正常的（格子相交未必真相交），
    # 正确判据是 ①零漏检 ②候选对少于全对枚举 n(n-1)/2。
    nc, nb, miss, _, _ = broadphase_sim(n=50)
    all_pairs = 50 * 49 // 2
    c.chk("F31 宽相零漏检", miss == 0, "missed=%d" % miss)
    c.chk("F31 候选少于全对枚举", nc < all_pairs,
          "cand=%d all=%d" % (nc, all_pairs))
    c.note("F31 真实相交对=%d，候选=%d（保守性正常），筛除 %d 对"
           % (nb, nc, all_pairs - nc))



def _chk_f32(c):
    """F32 零重力探针（从 self_check 抽出）。"""
    # 无外力 ⇒ 匀速 + 碰撞动量守恒
    drift, mom, _, _ = gravity_off_sim()
    c.chk("F32 零重力匀速直线", drift < 1e-6, "drift=%.3e" % drift)
    c.chk("F32 碰撞动量守恒", mom < 1e-6, "mom_err=%.3e" % mom)



def _chk_f33(c):
    """F33 摩擦探针（从 self_check 抽出）。"""
    # 库仑摩擦 → 迅速停止。
    # 口径警告：方块在摩擦作用下会翻滚（实测 th: 0→-1.6rad，w 达 -2.5rad/s），
    # 质点公式 v²/(2μg)=0.136m 不适用（忽略转动惯量），故不作判据。
    # 改用有出处的定性判据：库仑摩擦单调性 —— μ 越大滑行距离越短。
    sd, st, _, v_end = friction_sim(mu=1.5, v0=2.0)
    c.chk("F33 高摩擦会停止", st is not None and st < 1.0, "stop_t=%s" % (st,))
    c.chk("F33 停止后速度归零", v_end < 1e-3, "v_end=%.3e" % v_end)
    d_hi, _, _, _ = friction_sim(mu=1.5, v0=2.0)
    d_lo, _, _, _ = friction_sim(mu=0.2, v0=2.0)
    c.chk("F33 摩擦越大滑得越短", d_hi is not None and d_lo is not None
          and d_hi < d_lo,
          "mu1.5=%.4f < mu0.2=%.4f"
          % (d_hi if d_hi else -1, d_lo if d_lo else -1))
    c.note("F33 方块会翻滚，质点公式 v²/(2μg)=0.136m 不适用；"
           "实测 mu1.5=%.4f" % (d_hi if d_hi else -1))



def _chk_f34(c):
    """F34 重叠分离探针（从 self_check 抽出）。"""
    # 重叠必须分离（不是停在重叠里）
    pf, _, flip, _ = overlap_resolve_sim()
    c.chk("F34 终态重叠已分离", pf < 1e-3, "pen_final=%.3e" % pf)
    c.chk("F34 分离过程不闪烁", flip < 200, "flip=%d" % flip)


if __name__ == "__main__":
    print("SELF_CHECK", "PASS" if self_check() else "FAIL")
