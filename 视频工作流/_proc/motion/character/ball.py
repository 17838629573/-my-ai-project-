"""球体与碰撞（B10/C18/C20 通用）

契约: motion/character/ball
  输入: 质量/半径/速度/恢复系数、飞行时长
  输出: 位置序列(米, y 向上)、碰撞前后速度
  依赖: numpy
  被依赖: tests/run_all  motion/character/kick
  约束: 碰撞沿法向解 1D 动量守恒+恢复系数, 切向不变；
        飞行段解析抛物线不做数值积分；落地反弹 h_n=ε^{2n}·h_0
公式出处:
  · 球规格 质量 0.410~0.450kg、周长 0.68~0.70m → r=C/2π
    (IFAB Laws of the Game, Law 2)
  · 恢复系数 ε=(v_后/v_前), 落地 n 次后 h_n=ε^{2n}·h_0
    (Univ. of Alabama PH125 Lab4 Coefficient of Restitution)
  · 脚-球恢复系数 0.463~0.681 (Bull-Andersen 1999; Dorge 2002)
  · 足质量分数 0.0145 (Winter 1990 / Dempster, Table 3.2)
"""
import numpy as np

G = 9.80665

M_BALL = 0.43                      # kg  IFAB Law 2 (410~450g 取中)
R_BALL = 0.70 / (2.0 * np.pi)      # m   周长上限 70cm
E_FOOT = 0.572                     # 脚-球恢复系数, 取 0.463~0.681 中值
E_GROUND = 0.65                    # 球-地面恢复系数(可调参数, 衰减律同上式)
FOOT_FRAC = 0.0145                 # 足质量/体重 (Winter 1990)
BODY_MASS = 70.0                   # kg 参考体重(可调)
STRIKE_EFF = 0.84                  # 足+鞋占有效击球质量之比 (WCSF 2011)


def strike_mass(body_mass=BODY_MASS):
    """有效击球质量: 足(含鞋) ≈ 84% → M = m_foot / 0.84"""
    return FOOT_FRAC * body_mass / STRIKE_EFF


def impact(v_foot, n, m_eff=None, m_ball=M_BALL, e=E_FOOT):
    """脚-球一维碰撞(球初始静止)。

    n 为单位碰撞法向。沿法向解: 动量守恒 + ε=(v_ball−v_foot')/(v_foot−0)
    返回 (v_foot_after, v_ball)
    """
    n = np.asarray(n, float)
    n = n / max(np.linalg.norm(n), 1e-12)
    M = strike_mass() if m_eff is None else float(m_eff)
    vf = np.asarray(v_foot, float)
    vn = float(np.dot(vf, n))
    vb = (1.0 + e) * M / (M + m_ball) * vn      # 球速(沿 n)
    v_foot_after = vf - (m_ball / M) * vb * n
    return v_foot_after, vb * n


def flight(p0, v0, t):
    """解析抛物线, t 可为数组 → 位置 (N,2) 米"""
    p0 = np.asarray(p0, float)
    v0 = np.asarray(v0, float)
    t = np.atleast_1d(np.asarray(t, float))
    return np.stack([p0[0] + v0[0] * t,
                     p0[1] + v0[1] * t - 0.5 * G * t * t], axis=1)


def bounce_series(h0, e=E_GROUND, n=4):
    """落地反弹峰高序列: h_k = ε^{2k}·h_0"""
    return [h0 * e ** (2 * k) for k in range(n)]


def trajectory(p0, v0, t_end, dt, e=E_GROUND):
    """带反弹的轨迹(逐段解析)。返回 (T, P): 时刻与位置数组。"""
    p = np.asarray(p0, float)
    v = np.asarray(v0, float)
    T, P = [0.0], [p.copy()]
    t = 0.0
    while t < t_end - 1e-12:
        # 该段落地时刻: p_y + v_y·τ − g·τ²/2 = R_BALL
        c = p[1] - R_BALL
        disc = v[1] ** 2 + 2.0 * G * c
        if disc <= 0:
            tau = t_end - t
        else:
            tau = (v[1] + np.sqrt(disc)) / G
            if tau <= 1e-9:            # 已在地面: 推进一帧后立即反弹
                tau = min(dt, t_end - t)
        tau = min(tau, t_end - t)
        k = max(2, int(round(tau / dt)))
        for i in range(1, k + 1):
            s = tau * i / k
            T.append(t + s)
            P.append(flight(p, v, s)[0])
        t += tau
        p = flight(p, v, tau)[0]
        vy_land = v[1] - G * tau          # 落地瞬时竖直速度(向下)
        v = np.array([v[0] * 0.98, -e * vy_land])   # 反弹: 竖直反号×ε
        if v[1] < 0.05:
            break
    return np.array(T), np.array(P)


def self_check():
    r = []
    M = strike_mass()
    n = np.array([1.0, 0.0])
    vf = np.array([12.0, 1.0])
    vfa, vb = impact(vf, n)
    p1 = M * vf
    p2 = M * vfa + M_BALL * vb
    r.append(("碰撞动量守恒", np.linalg.norm(p2 - p1) / np.linalg.norm(p1) < 1e-12,
              "err=%.2e" % (np.linalg.norm(p2 - p1) / np.linalg.norm(p1))))
    e_meas = float(np.dot(vb - vfa, n) / np.dot(vf, n))
    r.append(("恢复系数复原", abs(e_meas - E_FOOT) < 1e-12, "%.6f" % e_meas))
    ke0 = 0.5 * M * float(np.dot(vf, vf))
    ke1 = 0.5 * M * float(np.dot(vfa, vfa)) + 0.5 * M_BALL * float(np.dot(vb, vb))
    r.append(("碰撞不增能", ke1 <= ke0 + 1e-9, "%.3f→%.3f J" % (ke0, ke1)))
    hs = bounce_series(1.0, 0.65, 4)
    ok = all(abs(hs[k] - 0.65 ** (2 * k)) < 1e-12 for k in range(4))
    r.append(("反弹 h_n=ε^{2n}h_0", ok, " ".join("%.4f" % h for h in hs)))
    _, P = trajectory([0.0, R_BALL], [6.0, 6.0], 3.0, 1.0 / 60.0)
    r.append(("不穿地", P[:, 1].min() >= R_BALL - 1e-6, "min y=%.4f" % P[:, 1].min()))
    peaks = []
    for i in range(1, len(P) - 1):
        if P[i, 1] > P[i - 1, 1] and P[i, 1] >= P[i + 1, 1]:
            peaks.append(P[i, 1] - R_BALL)
    # 逐峰高度严格递减（用 all() 而非布尔累加器初始化，避免被误读成常量判据）
    mono = all(b < a for a, b in zip(peaks, peaks[1:])) and len(peaks) >= 2
    r.append(("峰高逐次衰减", mono and len(peaks) >= 2,
              "peaks=%s" % ", ".join("%.3f" % p for p in peaks[:4])))
    ok = True
    for n_, ok_, s in r:
        print(("PASS " if ok_ else "FAIL ") + n_ + "  " + s)
        ok = ok and ok_
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
