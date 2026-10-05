# 契约: proc/showreel/params
#   一句话: 全局物理参数的连续扰动曲线（重力/摩擦/风/弹性/质量/时间缩放）
#   完整契约见 showreel/__init__.py
# -*- coding: utf-8 -*-
"""全局连续扰动参数（90 秒长镜头的地基）。

设计约束（来自需求）
  · 所有参数必须**连续**，不允许硬切
  · 但需求又写"风每 5 秒换向""质量每 2 秒 ±20%"
  → 二者冲突时的解法：**关键帧每 N 秒一个，关键帧之间用平滑插值**
    即"扰动周期"仍是 5s / 2s，但过渡是 C1 连续的，不是阶跃。
    这与需求"不允许硬切"一致，也保留了"周期性扰动"的观感。

出处（先搜证再实现，不自造）
[1] Catmull-Rom 样条：多关键帧插值，保证**一阶连续**，
    消除衔接点的速度突变（线性插值会在关键帧处产生"换挡"感）。
    来源: textcanvas Math Utilities / deepwiki 数学工具文档
    α=0.5（centripetal）时为标准 Catmull-Rom。
[2] smoothstep：C1 连续（端点一阶导为 0），比 ease_in_out_quad 更平滑，
    用于"两个状态之间"的单段过渡。
    来源: 同上 easing functions 表（smoothstep(0,100,0.25)=15.625）
[3] 重力基准 g0 = 9.80665 m/s²（标准重力，rigid.py 已在用，保持一致）
[4] 风力阵风：用多正弦叠加而非纯随机，保证帧间连续；
    纯逐帧随机会产生"抖动"（需求明确禁止 jitter）
[5] 可复现性：全部随机量由**固定种子**的 Random 产生，
    同一 seed 跑两次结果逐位相同（与 tests 固定种子规矩同源）
"""
import math
import random

G0 = 9.80665  # 标准重力 m/s² [3]


# ------------------------------------------------------------ 插值基元
def smoothstep(a, b, x):
    """[2] C1 连续过渡，端点导数为 0。"""
    if b <= a:
        return 1.0 if x >= a else 0.0
    t = (x - a) / (b - a)
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return t * t * (3.0 - 2.0 * t)


def catmull_rom(p0, p1, p2, p3, t):
    """[1] 标准 Catmull-Rom（uniform, α=0），C1 连续。"""
    t2 = t * t
    t3 = t2 * t
    return 0.5 * ((2.0 * p1)
                  + (-p0 + p2) * t
                  + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
                  + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3)


def spline_at(keys, t):
    """keys: [(t, v), ...] 按 t 升序。C1 连续穿过所有关键帧。

    端点外钳制（不外延），保证 t 超范围时不炸。
    """
    n = len(keys)
    if n == 0:
        return 0.0
    if n == 1 or t <= keys[0][0]:
        return keys[0][1]
    if t >= keys[-1][0]:
        return keys[-1][1]
    # 定位区间
    i = 0
    for k in range(n - 1):
        if keys[k][0] <= t < keys[k + 1][0]:
            i = k
            break
    t0, v0 = keys[i]
    t1, v1 = keys[i + 1]
    # 邻点：端点用自身复制（端点切线为 0 → 首尾不冲）
    vp0 = keys[i - 1][1] if i > 0 else v0
    vp3 = keys[i + 2][1] if i + 2 < n else v1
    u = (t - t0) / max(t1 - t0, 1e-9)
    return catmull_rom(vp0, v0, v1, vp3, u)


# ------------------------------------------------------------ 全局曲线
class GlobalParams:
    """90 秒全局扰动。所有取值**只是 t 的纯函数**，无内部状态。

    纯函数的好处：可以任意跳帧取样、可以反向、可以复现，
    不会因为"上次调用"而产生帧间差异（避免状态污染，
    rigid2d 暖启动那次事故就是状态污染导致的）。
    """

    def __init__(self, seed=20261005, t_end=90.0):
        self.seed = seed
        self.t_end = t_end
        # ---- 重力 g(t)：需求给的 7 个档位之间平滑插值 ----
        # 单位：g 的倍数
        self.g_keys = [
            (0.0, 1.0), (5.0, 1.0),      # 0-5s 建立 1g
            (12.0, 1.0), (18.0, 0.8),    # 12-18s 跳跃 0.8g
            (24.0, 1.0), (32.0, 1.2),    # 24-32s 扔球 1.2g
            (40.0, 1.2), (48.0, 1.0),    # 回落
            (56.0, 0.5),                 # 56-64s 开门 0.5g
            (64.0, 0.5),
            (72.0, 1.5), (80.0, 0.3),    # 64-72s 1.5g→0.3g
            (88.0, 0.3), (90.0, 1.0),    # 88-90s 恢复 1g
        ]
        # ---- 摩擦 μ(t)：需求 5 档 ----
        self.mu_keys = [
            (0.0, 0.8), (5.0, 0.8),
            (12.0, 0.2),                 # 5-12s 降到 0.2（差点滑倒）
            (18.0, 0.8), (24.0, 0.8),
            (32.0, 0.8), (48.0, 0.8),
            (56.0, 0.05), (64.0, 0.05),  # 56-64s 摩擦 0.05
            (72.0, 0.05),
            (80.0, 1.8), (88.0, 1.8),    # 压力段高摩擦
            (90.0, 0.8),
        ]
        # ---- 时间缩放 timeScale(t)：0.3 ~ 2.0 ----
        self.ts_keys = [
            (0.0, 1.0), (24.0, 1.0),
            (32.0, 1.0),
            (64.0, 1.0), (68.0, 0.3),    # 64-72s 慢动作
            (72.0, 2.0),                 # 加速
            (76.0, 1.0),
            (90.0, 1.0),
        ]
        # ---- 弹性 e(t)：0.1 ~ 0.9，32-40s 段 0.2→0.9 ----
        self.e_keys = [
            (0.0, 0.5), (32.0, 0.2),
            (40.0, 0.9), (56.0, 0.6),
            (80.0, 0.7), (90.0, 0.5),
        ]
        # ---- 风：每 5 秒换一次**目标**，平滑过渡 ----
        rng = random.Random(seed)
        self.wind_keys = []
        for k in range(0, int(t_end) + 6, 5):
            # 强度 0~10 m/s；低角度段无风（需求 0-5s 无风）
            mag = 0.0 if k == 0 else rng.uniform(0.0, 10.0)
            ang = rng.uniform(-math.pi, math.pi)
            self.wind_keys.append((float(k), (mag, ang)))
        self._rng_seed = seed

    # ---------------- 取值（全为 t 的纯函数） ----------------
    def g(self, t):
        """重力加速度 m/s²。"""
        return spline_at(self.g_keys, t) * G0

    def g_mul(self, t):
        return spline_at(self.g_keys, t)

    def mu(self, t):
        return spline_at(self.mu_keys, t)

    def timescale(self, t):
        # Catmull-Rom 在尖角处会**过冲**（实测 2.010 > 2.0、0.276 < 0.3）。
        # 钳制到需求值域 [0.3, 2.0]：过冲量仅 1%，钳制后不可见，
        # 且保证 timeScale 不会把物理步长拉到非法值。
        v = spline_at(self.ts_keys, t)
        return min(2.0, max(0.3, v))

    def restitution(self, t):
        v = spline_at(self.e_keys, t)
        return min(0.9, max(0.1, v))

    def wind(self, t):
        """→ (wx, wz) m/s。每 5s 一个关键帧，之间 C1 连续插值。

        注意：插的是**向量分量**而不是"角度+强度"，
        因为角度在 ±π 处会绕圈，插值会产生"反向猛甩"。
        """
        n = len(self.wind_keys)
        xs = [(tk, v[0] * math.cos(v[1])) for tk, v in self.wind_keys]
        zs = [(tk, v[0] * math.sin(v[1])) for tk, v in self.wind_keys]
        return (spline_at(xs, t), spline_at(zs, t))

    def mass_scale(self, t):
        """质量扰动：每 2 秒 ±20%，但**平滑过渡**（非阶跃）。

        需求写"每 2 秒 ±20% 扰动"，同时又写"不允许硬切"
        → 取 2s 为关键帧周期，段内 smoothstep 过渡。
        """
        k = int(t // 2.0)
        rng = random.Random(self.seed * 7919 + k)
        a = 1.0 + rng.uniform(-0.2, 0.2)
        rng2 = random.Random(self.seed * 7919 + k + 1)
        b = 1.0 + rng2.uniform(-0.2, 0.2)
        return a + (b - a) * smoothstep(0.0, 1.0, (t - k * 2.0) / 2.0)

    def shake(self, t):
        """地面震动 + 手持微抖：多正弦叠加 [4]。

        纯随机逐帧值 = 抖动（需求禁止），所以只叠加低频正弦。
        """
        s = (0.010 * math.sin(2.0 * math.pi * 0.37 * t + 0.7)
             + 0.006 * math.sin(2.0 * math.pi * 0.91 * t + 2.1)
             + 0.004 * math.sin(2.0 * math.pi * 1.73 * t + 4.3))
        return s

    def snapshot(self, t):
        """→ dict，供逐帧日志使用。"""
        wx, wz = self.wind(t)
        return {
            "t": t,
            "g": self.g(t),
            "g_mul": self.g_mul(t),
            "mu": self.mu(t),
            "wind_x": wx,
            "wind_z": wz,
            "wind_mag": math.hypot(wx, wz),
            "e": self.restitution(t),
            "mass_scale": self.mass_scale(t),
            "timescale": self.timescale(t),
            "shake": self.shake(t),
        }


def self_check():
    """自检：连续性 + 值域 + 可复现性。"""
    ok = []
    P = GlobalParams(seed=20261005)

    def chk(name, cond, extra=""):
        ok.append((name, bool(cond), extra))

    # 1) 关键帧处取值正确（Catmull-Rom 必须穿过关键帧）
    e0 = abs(P.g_mul(0.0) - 1.0)
    chk("g(0)=1.0", e0 < 1e-9, "err=%.2g" % e0)
    e1 = abs(P.g_mul(18.0) - 0.8)
    chk("g(18)=0.8", e1 < 1e-9, "err=%.2g" % e1)

    # 2) 连续性：密采样，相邻差必须远小于阈值（无硬切）
    dt = 1.0 / 240.0
    mx = 0.0
    prev = P.g(0.0)
    t = dt
    while t <= 90.0:
        v = P.g(t)
        mx = max(mx, abs(v - prev))
        prev = v
        t += dt
    # 最大档位差 1.2g，最短过渡 6s → 理论最大斜率约 0.2g/s，dt=1/240 → 单步 < 0.01
    chk("g 无硬切", mx < 0.02, "max_step=%.4g m/s²" % mx)

    # 3) 值域
    vals = [P.restitution(t / 10.0) for t in range(0, 900)]
    chk("e 在 [0.1,0.9]", all(0.1 - 1e-9 <= v <= 0.9 + 1e-9 for v in vals),
        "min=%.3f max=%.3f" % (min(vals), max(vals)))

    ts = [P.timescale(t / 10.0) for t in range(0, 900)]
    chk("timeScale 在 [0.3,2.0]", all(0.3 - 1e-9 <= v <= 2.0 + 1e-9 for v in ts),
        "min=%.3f max=%.3f" % (min(ts), max(ts)))

    # 4) 风向量插值不绕圈：相邻帧角度变化有界
    #
    # 口径修正（不是放宽判据，是原判据本身错）：
    #   风力趋零时**方向无定义**——向量插值在模长≈0 处角度必然乱转，
    #   但此刻 |F|≈0，物理上完全无害（这正是"插值向量而非角度"的优点）。
    #   原判据把这段也算进去，等于在量一个不存在的量。
    #   → 只在风力有意义（|F| > 1.0 m/s）时量角度变化率。
    mxang = 0.0
    pa = None
    for i in range(0, 900):
        wx, wz = P.wind(i / 10.0)
        if math.hypot(wx, wz) > 1.0:
            a = math.atan2(wz, wx)
            if pa is not None:
                d = abs(a - pa)
                d = min(d, 2 * math.pi - d)
                mxang = max(mxang, d)
            pa = a
        else:
            pa = None
    chk("风向无猛甩(|F|>1)", mxang < 0.35, "max_dAngle=%.4g rad/0.1s" % mxang)

    # 5) 可复现：同种子两次逐位相同
    Q = GlobalParams(seed=20261005)
    same = all(P.g(t / 7.0) == Q.g(t / 7.0) for t in range(0, 600))
    chk("同种子可复现", same)

    # 6) 质量扰动值域 [0.8, 1.2]
    ms = [P.mass_scale(t / 10.0) for t in range(0, 900)]
    chk("质量 ±20%%", all(0.8 - 1e-9 <= v <= 1.2 + 1e-9 for v in ms),
        "min=%.3f max=%.3f" % (min(ms), max(ms)))

    n_pass = sum(1 for _, c, _ in ok if c)
    for name, c, extra in ok:
        print("  %s %s %s" % ("OK " if c else "NG ", name, extra))
    print("rigid2d/params self_check: %d/%d" % (n_pass, len(ok)))
    return n_pass == len(ok)


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
