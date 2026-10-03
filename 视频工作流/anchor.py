#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
anchor.py —— 物理点锚点层
========================
契约: contracts/anchor.md

把物性 → 无量纲数 → 物理点表，作为生图的几何锚点。
不画质感，只算几何。质感交给生图模型。

来源（搜到的权威判据，非自造）：
  R1/R2/Re/St 定义      Connell & Yue 2007, JFM
  regime 区间            Izawa et al. 2024 (ICJWSF2024)
  A/L > 1.6 (flapping)  Izawa 2024 实测
  悬臂梁 β1 = 1.8751     经典解
"""
import math

__all__ = ["FAMILIES", "dimensionless", "judge_regime", "strouhal_freq",
           "cantilever_points", "pendulum2_points", "build_anchor", "self_check"]

# 常量（外置，改数字不动代码）
RHO_F = 1.225          # 空气密度 kg/m^3
NU = 1.5e-5            # 空气运动粘度 m^2/s
G = 9.81
ST_TARGET = 0.2        # Connell&Yue: flapping 时 St≈0.2
BETA1 = 1.8751         # 悬臂梁(clamped-free)一阶模态特征值

# 【铁律45】A_OVER_L 不再是常量 —— 已删除。
# 旧值 1.6 是 Izawa 2024 测得的 **flapping 态**峰峰振幅比，
# 被当无条件常数写死后导致"3 级风也画成 6 级风的大幅抽打"，
# 且 solver 查表算出的值传不进 build_anchor（断链，查了等于没查）。
# 现值必须由调用方显式传入（a_over_l 形参），来源 = 风级查表，
# 表由 AI 搜证传入（铁律32）。函数体内引用本名即视为断链回归。

# regime 区间（Izawa 2024 实测）
R2_STRAIGHT = 4.06e-3
R2_DEFLECT = 1.72e-3

FAMILIES = ("cantilever", "pendulum2", "hinge", "free_surface")


# ------------------------------------------------------------ 无量纲数
def dimensionless(L, sigma, B, U, H=None):
    """
    R1 = 质量比 M*      = sigma/(rho_f·L)
    R2 = 无量纲弯曲刚度 = B/(rho_f·U^2·L^3)
    Re = U·L/nu
    """
    return {
        "R1": sigma / (RHO_F * L),
        "R2": B / (RHO_F * U * U * L ** 3),
        "Re": U * L / NU,
    }


def judge_regime(R2, family="cantilever"):
    """
    Izawa 2024 实测区间 —— 仅对 cantilever 有效。
    二级摆/铰链/自由液面不适用该判据，返回 "n/a"。
    """
    if family != "cantilever":
        return "n/a"
    if R2 > R2_STRAIGHT:
        return "straight"
    if R2 > R2_DEFLECT:
        return "flapping"
    return "deflected"


def strouhal_freq(U, L, a_over_l=None):
    """
    St = 2A·f/U  →  f = St·U/(2A)
    【铁律20】A 是振幅不是长度。混用 St=f·L/U 会错 1.6 倍。
    A_pp = a_over_l·L（峰峰），单边 A = A_pp/2
    【铁律45】a_over_l 必须显式传入（来自风级查表）。
    传 None 即报错 —— 旧默认值 1.6 会让小风也画成大风形态。
    """
    if a_over_l is None:
        raise ValueError("strouhal_freq 缺 a_over_l（铁律45：须由风级查表传入，"
                         "禁静默取 1.6 常数）")
    a_pp = a_over_l * L
    a_single = a_pp / 2.0
    f = ST_TARGET * U / (2.0 * a_single)
    return f, (1.0 / f if f else 0.0)


# ------------------------------------------------------------ 物理点
def _phi(s):
    """标准悬臂梁一阶模态 φ(s)，β1=1.8751"""
    sig = ((math.cosh(BETA1) + math.cos(BETA1)) /
           (math.sinh(BETA1) + math.sin(BETA1)))
    return ((math.cosh(BETA1 * s) - math.cos(BETA1 * s)) -
            sig * (math.sinh(BETA1 * s) - math.sin(BETA1 * s)))


def cantilever_points(n=8, waves=0.75):
    """
    悬臂梁物理点：s=0 clamped（位移0、切角0），s=1 自由端（弯矩0）
    返回 [(s, A/A_max, phase_lag_deg), ...]
    """
    raw = [_phi(i / n) for i in range(n + 1)]
    mx = raw[-1]
    k = 2 * math.pi * waves
    pts = []
    for i, v in enumerate(raw):
        s = i / n
        env = v / mx if mx else 0.0
        lag = math.degrees(k * s)
        pts.append((round(s, 3), round(env, 3), round(lag, 1)))
    return pts


def pendulum2_points(n=4, waves=1.0):
    """
    二级摆：顶端受迫振动（跟随驱动点，振幅已最大）+ 自身摆动
    摆幅包络从顶端起就 >0 且单调增，末端最大 —— 与悬臂梁 s=0 归零不同
    """
    k = 2 * math.pi * waves
    pts = []
    for i in range(n + 1):
        s = i / n
        env = 1.0 + 0.8 * s          # 驱动点振幅(1.0) + 自身摆动增量
        lag = math.degrees(k * s)
        pts.append((round(s, 3), round(env, 3), round(lag, 1)))
    return pts


# ------------------------------------------------------------ 主入口
def build_anchor(name, L, H, sigma, B, U, family="cantilever", n=8,
                 a_over_l=None):
    """
    返回完整锚点包：无量纲数 + regime + 周期 + 物理点表 + 硬约束

    【铁律45】a_over_l 必须显式传入（风级查表值），禁回退常数。
    旧实现在内部硬用 A_OVER_L=1.6，导致 solver 查表结果传不进来（断链）。
    """
    if family not in FAMILIES:
        raise ValueError("family=%r 非法，须为 %s" % (family, "/".join(FAMILIES)))
    if a_over_l is None:
        raise ValueError("build_anchor 缺 a_over_l（铁律45：须由风级查表传入）")
    dm = dimensionless(L, sigma, B, U, H)
    regime = judge_regime(dm["R2"], family)
    f, T = strouhal_freq(U, L, a_over_l=a_over_l)
    if family == "cantilever":
        pts = cantilever_points(n)
    elif family == "pendulum2":
        pts = pendulum2_points(max(n // 2, 3))
    else:
        pts = []
    return {
        "actor": name, "family": family,
        "dimensionless": {k: round(v, 6) for k, v in dm.items()},
        "regime": regime,
        "freq_hz": round(f, 3), "period_s": round(T, 3),
        "tip_pp_amp_m": round(a_over_l * L, 3),
        "points": pts,
        "hard_constraints": _constraints(family, regime, L, T,
                                         a_over_l * L),
    }


def _constraints(family, regime, L, T, a_pp=0.0):
    if family == "cantilever":
        c = ["s=0 固定端位移=0、切角=0（杆全程垂直静止）",
             "摆动周期 %.3f s" % T]
    elif family == "pendulum2":
        # 二级摆 s=0 是驱动点（跟随幡身末端），不是固定端
        c = ["s=0 为驱动点，振幅=驱动点振幅(1.0)，非固定端",
             "摆动周期 %.3f s" % T]
    else:
        c = ["摆动周期 %.3f s" % T]
    if regime == "flapping":
        c.append("末端峰峰摆幅 >= %.2f m (旗长 %.2f m 的 %.1f 倍)"
                 % (a_pp, L, a_pp / L if L else 0.0))
        c.append("沿弧长行波相位滞后，禁整体同相")
        c.append("St≈%.1f 邻域，非严格周期，含不规则性" % ST_TARGET)
    elif regime == "straight":
        c.append("整体绷直接近水平，仅末端小幅抖")
    elif regime == "deflected":
        c.append("向一侧弯曲不拍打")
    else:  # n/a —— 非悬臂梁族，regime 判据不适用
        c.append("regime 判据不适用本族（Izawa区间仅对悬臂梁有效）")
    if family == "pendulum2":
        c.append("二级摆：末端摆幅 > 驱动点（旗身末端）摆幅")
    return c


# ------------------------------------------------------------ 自检
def self_check():
    ok = True
    # 1. 悬臂梁固定端必须归零
    pts = cantilever_points()
    s0 = pts[0]
    if abs(s0[1]) > 1e-6:
        print("FAIL 悬臂梁 s=0 振幅应为0，实为", s0[1]); ok = False
    else:
        print("PASS 悬臂梁固定端 A(0)=0（杆不动的几何保证）")
    # 2. 包络单调递增
    envs = [p[1] for p in pts]
    if all(envs[i] <= envs[i + 1] for i in range(len(envs) - 1)):
        print("PASS 振幅包络单调递增 末端=%.3f" % envs[-1])
    else:
        print("FAIL 包络非单调"); ok = False
    # 3. St 自洽：用算出的 f 反算 St，应回到 0.2
    U, L = 12.3, 0.90
    AOL_6 = 1.60          # 6 级风查表值（flapping 态），此处仅作自检输入
    f, T = strouhal_freq(U, L, a_over_l=AOL_6)
    a_pp = AOL_6 * L
    st_back = 2 * (a_pp / 2) * f / U
    if abs(st_back - ST_TARGET) < 1e-6:
        print("PASS St 自洽: f=%.3fHz -> 反算 St=%.3f" % (f, st_back))
    else:
        print("FAIL St 不自洽 %.3f" % st_back); ok = False
    # 4. St 定义混用检测：f·L/U 与 2A·f/U 必须不同
    st_wrong = f * L / U
    if abs(st_wrong - ST_TARGET) > 0.05:
        print("PASS 铁律20: St=f·L/U=%.3f 与 2A·f/U=%.3f 相差 %.2f 倍（禁混用）"
              % (st_wrong, ST_TARGET, ST_TARGET / st_wrong))
    else:
        print("FAIL 两个 St 定义意外接近，检测失效"); ok = False
    # 5. 6级风应判 flapping
    dm = dimensionless(0.90, 0.095, 0.30, 12.3)
    rg = judge_regime(dm["R2"])
    if rg == "flapping":
        print("PASS 6级风 R2=%.2e -> flapping（大幅拍打，非平直）" % dm["R2"])
    else:
        print("FAIL 6级风判为 %s" % rg); ok = False
    # 6. 二级摆摆幅必须大于驱动点
    p2 = pendulum2_points()
    if p2[-1][1] > 1.0:
        print("PASS 二级摆末端 %.2f > 驱动点 1.0（垂带摆幅大于旗身）" % p2[-1][1])
    else:
        print("FAIL 二级摆末端未超出驱动点"); ok = False
    # 7. 铁律29：序列帧数由周期反算，不得手填 24
    import framerate as fr
    f, T = strouhal_freq(12.3, 0.90, a_over_l=AOL_6)
    N = fr.frames_for_period(T)
    if N != 24:
        print("PASS 序列帧数由周期反算 T=%.3fs -> %d 帧（非手填 24）" % (T, N))
    else:
        print("FAIL 帧数恰为 24，疑似手填"); ok = False
    try:
        fr.playrate(24, N)
        print("FAIL 24 帧素材未被拒"); ok = False
    except ValueError:
        print("PASS 24 帧素材被拒（须按 %d 帧重新生成）" % N)
    # 8. 铁律45：a_over_l 必须真正传导（防断链回归）
    #    旧实现内部硬用常数 1.6，solver 查表值传不进来 —— 查了等于没查
    a_small = build_anchor("t", 0.90, 0.90, 0.062, 1e-3, 4.4, a_over_l=0.35)
    a_big = build_anchor("t", 0.90, 0.90, 0.062, 1e-3, 12.3, a_over_l=1.60)
    if a_small["tip_pp_amp_m"] < a_big["tip_pp_amp_m"] - 1e-6:
        print("PASS A/L 传导生效: 4级摆幅 %.3fm < 6级 %.3fm"
              % (a_small["tip_pp_amp_m"], a_big["tip_pp_amp_m"]))
    else:
        print("FAIL A/L 未传导（断链回归）%.3f vs %.3f"
              % (a_small["tip_pp_amp_m"], a_big["tip_pp_amp_m"])); ok = False
    try:
        build_anchor("t", 0.90, 0.90, 0.062, 1e-3, 12.3)
        print("FAIL 缺 a_over_l 未报错（会静默回退常数）"); ok = False
    except ValueError:
        print("PASS 缺 a_over_l 报错（禁静默回退）")
    # 9. 源码扫描：build_anchor 体内不得引用 A_OVER_L 常数
    # 【自检自指误报·第4次】inspect.getsource 会连 docstring 一起取回，
    # 而 docstring 里写了 "A_OVER_L=1.6" 的说明 -> 必 FAIL。
    # 修法同 framerate/solver：用 ast 剥离 docstring 后只扫真实代码。
    import inspect, ast
    tree = ast.parse(inspect.getsource(build_anchor))
    fn = tree.body[0]
    if (fn.body and isinstance(fn.body[0], ast.Expr)
            and isinstance(fn.body[0].value, ast.Constant)
            and isinstance(fn.body[0].value.value, str)):
        fn.body = fn.body[1:]
    if "A_OVER_L" in ast.unparse(fn):
        print("FAIL build_anchor 体内仍引用 A_OVER_L 常数（断链）"); ok = False
    else:
        print("PASS build_anchor 体内无 A_OVER_L 常数引用")

    print("\n%s" % ("anchor 自检 PASS" if ok else "anchor 自检 FAIL"))
    return ok


if __name__ == "__main__":
    self_check()
