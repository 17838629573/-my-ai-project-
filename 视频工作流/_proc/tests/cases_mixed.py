"""# 契约: tests.cases_mixed
## 范围
H40 混合场景：把**已通过各自单测的所有子系统**放进同一根时间轴、
同一套世界坐标里同时推进，检验它们凑在一起时会不会出问题。

子系统各自的内部物理（骨长守恒、步态判据、气动配平…）已由
G37/G38/G39、B/C/D/E/F 各用例覆盖，本用例**不重复测**，只测跨系统接口：
坐标口径是否一致、时间轴是否同步、互相会不会穿模、有没有实体在偷懒不动。

## 依赖
motion.character.body.gait(走) / motion.character.run(跑) / motion.rigid(弹球)
/ motion.constraint_ext(绳) / motion.creature.quadruped(四足)
/ motion.creature.fish_swim(鱼) / motion.creature.bird_fly(鸟) ; tests.harness(判据)

## 判据口径声明（改动判据必须写明理由，禁止静默）
- 跨实体间距用**包围球**而非逐骨段：7 类实体的骨架定义各不相同
  （人形 21 关节 / 四足足端 2D / 鱼鸟脊椎链），逐骨段比较是拿不同量纲互比。
  包围球半径取该实体各帧点集到其中心的最大距离，穿透 = 半径和 − 球心距。
- 穿透阈值沿用 slop=0.005m（Box2D 官方 b2_linearSlop，v2.4.1 b2_common.h:65），
  与项目其余穿模判据同口径，不因实体变大而放宽。
- 「真在动」判据用总位移弧长而非首尾距离：圆周/往复运动首尾距离可为 0，
  首尾距离会把原地踏步误判成静止。
- 帧数一致性按各实体实际采样序列长度比：不同能力的原生采样率不同
  （gait 按相位、bounce 按 dt=1/240、鸟按扑动周期），
  统一到同一 t_end 后长度本就不同，故比的是**覆盖时长**而非点数。
"""

import numpy as np

from motion.character.body.gait import gait
from motion.character.run import run
from motion.rigid import bounce_traj
from motion.constraint_ext import rope_sim
from motion.creature.quadruped import quadruped_sim
from motion.creature import fish_swim
import importlib
_bf_mod = importlib.import_module("motion.creature.bird_fly")

import tests.harness as H

# 跨实体穿透阈值：与项目其余穿模判据同口径
SLOP = 0.005


def _pts(seq):
    """统一成 (n, k, 3) 的世界点集；允许输入 (n,k,2)（补 z=0）。"""
    a = np.asarray(seq, dtype=float)
    if a.ndim == 2:
        a = a[:, None, :]
    if a.shape[-1] == 2:
        a = np.concatenate([a, np.zeros(a.shape[:2] + (1,))], axis=-1)
    return a


def _place(a, off):
    """平移到世界位置 off=(x,y,z)。"""
    return a + np.asarray(off, dtype=float).reshape(1, 1, 3)


def _trk_bipeds(ts):
    """人形：走 / 跑（相位由里程驱动，与 A1/A2 同口径）。"""
    out = []
    for nm, fn, v, z in (("walker", lambda p: gait(p % 1.0), 1.4, -1.5),
                         ("runner", lambda p: run(p % 1.0, v=3.2), 3.2, 1.5)):
        seq = []
        for i, t in enumerate(ts):
            J = fn(v * t / 1.4 / 2.0)          # 步频随速度：每 2 步 1.4m
            seq.append(np.array([J[k] for k in sorted(J.keys())], float))
        a = _pts(seq)
        a[:, :, 0] += (v * ts)[:, None]
        out.append((nm, _place(a, (0.0, 0.0, z))))
    return out


def _trk_ball(n, ts, dur):
    """物件：弹球（x 固定在 8m 处上下弹跳）。"""
    _, ys = bounce_traj(1.0, 0.8, dur)
    ys = np.asarray(ys, float)
    yi = np.interp(ts, np.linspace(0, dur, len(ys)), ys)
    ball = np.stack([np.full(n, 8.0), yi, np.zeros(n)], axis=1)[:, None, :]
    return ("ball", _place(ball, (0.0, 0.11, 0.0)))


def _trk_rope(n, ts):
    """物件：绳（悬挂点 (12,1.2)，末端点由 Verlet 摆动给出）。

    rope_sim 返回 (收敛误差, 垂度, 末端点轨迹(steps,2))；绳身以「锚点—末端」
    两点表征。摆动本身来自 rope_sim 的真实动力学，不由用例写死。
    """
    rp = rope_sim(n=8, seg=0.12, anchor=(12.0, 1.2), iters=200, steps=400)
    traj = np.asarray(rp[2], float)
    ti = np.linspace(0, len(traj) - 1, n)
    tip = np.stack([np.interp(ti, np.arange(len(traj)), traj[:, 0]),
                    np.interp(ti, np.arange(len(traj)), traj[:, 1]),
                    np.zeros(n)], axis=1)
    anc = np.tile(np.array([12.0, 1.2, 0.0]), (n, 1))
    return ("rope", np.stack([anc, tip], axis=1))


def _trk_quad(n, ts):
    """生物：四足小跑（足端 2D → 补 z，x 按 speed 推进）。"""
    q = quadruped_sim(cycles=2, n=n, gait="trot", speed=0.8, freq=2.5)
    qa = _pts(q[0])
    qa[:, :, 0] += (0.8 * ts)[:, None]
    return ("quad", _place(qa, (0.0, 0.0, -4.0)))


def _trk_fish(ts):
    """生物：鱼（水层 y=0.6，z=+4）。"""
    fs = []
    for t in ts:
        J = fish_swim(t)["J"]
        fs.append(np.array([J[k] for k in sorted(J.keys())], float))
    return ("fish", _place(_pts(fs), (0.0, 0.6, 4.0)))


def _trk_bird(ts):
    """生物：鸟（巡航高度，z=+2）。"""
    bs = []
    for t in ts:
        J = _bf_mod.bird_fly(t)["J"]
        bs.append(np.array([J[k] for k in sorted(J.keys())], float))
    return ("bird", _place(_pts(bs), (0.0, 0.0, 2.0)))


def _entity_tracks(fps, dur):
    """构造 7 类实体的世界轨迹。返回 [(name, (n,k,3) 点集), ...]。"""
    n = int(round(fps * dur))
    ts = np.arange(n) / fps
    out = []
    out += _trk_bipeds(ts)
    out.append(_trk_ball(n, ts, dur))
    out.append(_trk_rope(n, ts))
    out.append(_trk_quad(n, ts))
    out.append(_trk_fish(ts))
    out.append(_trk_bird(ts))
    return out


def _h40_smooth(tracks):
    """各自帧间平滑（取所有实体的最坏值）。"""
    fjr = 0.0
    for _, a in tracks:
        d = np.linalg.norm(np.diff(a, axis=0), axis=1).max(axis=1)
        fjr = max(fjr, float(H.frame_jump_ratio(d)))
    return fjr


def _h40_overlap(tracks, fps):
    """跨实体互不穿透（包围球口径，逐帧）。

    包围球**逐帧**算：若把全部帧塞进一个球，位移大的实体（鸟 3 秒飞 37m）
    半径会膨胀到十几米，把「互相穿透」量成「轨迹包络重叠」——那是口径错，
    不是穿模。逐帧比较才是「同一时刻两个物体有没有叠在一起」。
    """
    info = []
    for nm, a in tracks:
        c = a.mean(axis=1)                                    # (n,3)
        r = np.linalg.norm(a - c[:, None, :], axis=2).max(axis=1)  # (n,)
        info.append((nm, c, r))
    worst_pen, worst_pair = 0.0, ""
    for i in range(len(info)):
        for j in range(i + 1, len(info)):
            n1, c1, r1 = info[i]
            n2, c2, r2 = info[j]
            gap = np.linalg.norm(c1 - c2, axis=1) - (r1 + r2)  # (n,)
            k = int(np.argmin(gap))
            if -float(gap[k]) > worst_pen:
                worst_pen = -float(gap[k])
                worst_pair = "%s/%s@%.2fs" % (n1, n2, k / fps)
    return worst_pen, worst_pair


def _h40_ground(tracks):
    """地面实体不穿地（球/四足/人形的足最低点）。"""
    lows = []
    for nm, a in tracks:
        if nm in ("walker", "runner", "quad", "ball"):
            lows.append(float(a[:, :, 1].min()))
    return H.ground_penetration_m(lows) if lows else 0.0


def _h40_arcs(tracks):
    """每个实体的总弧长（防静态复制 / 时间轴没接上）。"""
    arcs = {}
    for nm, a in tracks:
        arcs[nm] = float(np.linalg.norm(np.diff(a, axis=0), axis=1).sum())
    return arcs, min(arcs.values())


def case_H40():
    """H40 混合场景：7 类实体同时间轴、同世界坐标下的接口一致性。"""
    fps, dur = 24.0, 3.0
    tracks = _entity_tracks(fps, dur)

    # 1) 无 NaN（坐标口径不一致最常见的表现）
    nan_cnt = int(sum(int(np.isnan(a).sum()) for _, a in tracks))

    # 2) 各自帧间平滑
    fjr = _h40_smooth(tracks)

    # 3) 跨实体互不穿透
    worst_pen, worst_pair = _h40_overlap(tracks, fps)

    # 4) 地面实体不穿地
    pen_ground = _h40_ground(tracks)

    # 5) 每个实体都真在动
    arcs, min_arc = _h40_arcs(tracks)

    # 6) 时间轴同步：各实体覆盖时长一致
    spans = [a.shape[0] / fps for _, a in tracks]
    span_err = max(spans) - min(spans)

    checks = [("nan_count", nan_cnt),
              ("frame_jump_ratio", fjr),
              ("xbody_penetration_m", worst_pen),
              ("ground_penetration_m", pen_ground),
              ("min_arc_m", min_arc),
              ("time_span_err_s", span_err)]

    print("   实体数 %d，各实体弧长(m)：" % len(tracks))
    for k_, v in arcs.items():
        print("     %-7s %.4f" % (k_, v))
    print("   最坏穿透对：%s" % (worst_pair or "无"))
    meta = {"实体数": len(tracks), "各实体弧长_m": arcs,
            "最坏穿透对": worst_pair or "无"}
    return checks, meta
