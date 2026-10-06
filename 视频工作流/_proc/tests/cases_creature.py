"""# 契约: tests.cases_creature
## 范围
三个新生物能力的门检用例执行体：
  G37 攀岩（climb_rock） / G38 鱼游（fish_swim） / G39 四足六步态（quadruped）

## 依赖
motion.creature(攀岩/鱼游) / motion.creature.quadruped ; tests.harness(判据)

## 判据口径声明（改动判据必须写明理由，禁止静默）
- G37 滑移用 climb_rock._effectors 返回的 mv 标志界定支撑相（mv=False 即固定），
  不使用"位移小即支撑"的循环论证口径。
- G37 穿壁用 ground_penetration_m（半空间 x>=0 的穿透深度），与穿地同口径：
  岩壁是竖直半空间，判据复用 slop=0.005m（Box2D 官方 b2_linearSlop）。
- G38 段长守恒判据为相邻脊椎点距离与 body_len/n_seg 的最大偏差；
  鱼体是等弧长离散链，弧长投影后 x 方向略短属正常（见 fish_swim 注释）。
- G39 支撑足缺口按 GAIT_TABLE 每步态各自的期望值比较（bound/gallop 期望 0，
  有腾空相），不统一用 2 足——否则会把合法腾空误判为失败。
"""

import numpy as np

from motion.creature import climb_rock, fish_swim, fish_strouhal  # noqa: F401
from motion.creature.climb_rock import _effectors, ORDER

from motion.creature.quadruped import (quadruped_sim, foot_slip,
                                          GAIT_TABLE, GAIT_NAMES)
import tests.harness as H


# ---------------------------------------------------------------- G37
def case_G37():
    """G37 攀岩：三点支撑 / 支撑相零滑移 / 不穿壁 / 帧间平滑。"""
    MAP = {"lh": "wri_l", "rh": "wri_r", "lf": "ank_l", "rf": "ank_r"}
    fps, dur = 24.0, 3.0
    n = int(fps * dur)
    Js, mvs = [], []
    for i in range(n):
        t = i / fps
        Js.append(climb_rock(t))
        _, mv, _ = _effectors(t)
        mvs.append(mv)
    keys = sorted(Js[0].keys())
    arr = np.array([[Js[k_][k] for k in keys] for k_ in range(n)], float)

    d = np.linalg.norm(np.diff(arr, axis=0), axis=1).max(axis=1)
    fjr = H.frame_jump_ratio(d)

    slip = 0.0
    min_sup = 99
    for i in range(1, n):
        mv = mvs[i]
        fixed = [nm for nm in ORDER if nm != mv]      # 每时刻恰有 1 个在移动
        min_sup = min(min_sup, len(fixed))
        for nm in fixed:
            j = keys.index(MAP[nm])
            slip = max(slip, float(np.linalg.norm(arr[i, j] - arr[i - 1, j])))

    pen = H.ground_penetration_m([float(arr[:, :, 0].min())])

    checks = [("support_min", min_sup), ("foot_slip_m", slip),
              ("ground_penetration_m", pen), ("frame_jump_ratio", fjr)]
    meta = {"帧数": n, "最少支撑效应器": min_sup, "最深穿壁_m": pen}
    return checks, meta


# ---------------------------------------------------------------- G38
def case_G38():
    """G38 鱼游：脊椎段长守恒 / Strouhal 区间 / 帧间平滑。"""
    body_len, n_seg = 0.30, 13
    fps, dur = 24.0, 2.0
    n = int(fps * dur)
    Js, meta0 = [], None
    for i in range(n):
        r = fish_swim(i / fps, body_len=body_len, freq=2.0, speed=0.50,
                      n_seg=n_seg)
        Js.append(r["J"])
        meta0 = r["meta"]
    keys = sorted(Js[0].keys())
    arr = np.array([[Js[k_][k] for k in keys] for k_ in range(n)], float)

    seg = np.linalg.norm(np.diff(arr, axis=1), axis=2)
    seg_err = float(np.abs(seg - body_len / n_seg).max())

    d = np.linalg.norm(np.diff(arr, axis=0), axis=1).max(axis=1)
    fjr = H.frame_jump_ratio(d)
    st = float(meta0["strouhal"])

    checks = [("seg_len_err", seg_err), ("strouhal_lo", st),
              ("strouhal_hi", st), ("frame_jump_ratio", fjr)]
    meta = {"模式": meta0["mode"], "St": st, "体长_m": body_len,
            "段长误差": seg_err}
    return checks, meta


# ---------------------------------------------------------------- G39
def case_G39():
    """G39 四足六步态：支撑足缺口 / 足端滑移 / 帧间平滑。"""
    worst_def, worst_slip, worst_fjr = -99, 0.0, 0.0
    per = {}
    for g in GAIT_NAMES:
        feet, body_y, off, support = quadruped_sim(cycles=2, n=120, gait=g,
                                                     world=True)
        sup = np.asarray(support, bool)
        exp = GAIT_TABLE[g][2]
        mins = int(sup.sum(axis=1).min())
        defi = max(0, exp - mins)
        slip = float(foot_slip(feet, sup))
        fjr = H.frame_jump_ratio(np.abs(np.diff(np.asarray(body_y, float))))
        worst_def = max(worst_def, defi)
        worst_slip = max(worst_slip, slip)
        worst_fjr = max(worst_fjr, fjr)
        per[g] = (mins, exp, slip)

    checks = [("gait_contact_deficit", worst_def),
              ("foot_slip_m", worst_slip),
              ("frame_jump_ratio", worst_fjr)]
    meta = {"步态数": len(GAIT_NAMES), "逐步态(实测最少支撑/期望/滑移)": per}
    return checks, meta
