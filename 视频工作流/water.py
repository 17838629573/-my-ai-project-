"""
water.py —— 降水与水体纯函数层（雨滴 / 溅射 / 涉水 / 水面波）

一切表现由「无量纲数 + 经验公式」算出，禁凭印象填像素或频率。
业界出处见 IMPROVE_water.md；契约见 contracts/precipitation.md
"""
import math

# ---------------- 常量（唯一定义，业务模块禁重写） ----------------
G = 9.81                # m/s^2
SIGMA_W = 0.0728        # N/m  水-空气表面张力 @20C
RHO_W = 1000.0          # kg/m^3
MU_W = 1.002e-3         # Pa·s
RHO_A = 1.204           # kg/m^3 空气 @20C

# Atlas-Ulbrich 终速幂律 U = a*D^b (D in cm -> cm/s)
AU_A, AU_B = 1767.0, 0.67
# Marshall-Palmer
MP_N0 = 8000.0          # m^-3 mm^-1
# Best 中值体积直径 a = 1.30*R^0.232 (cm)
BEST_A, BEST_N = 1.30, 0.232
# 溅射阈值
K_C_LOW, K_C_HIGH = 2000.0, 3000.0
# 涉水：中国人体参数（相对淹没体积 / 人体体积）
WAD_A1, WAD_B1 = 0.633, 0.367
BODY_A2, BODY_B2 = 1.015e-3, -4.937e-3   # V_p = a2*m + b2  (m^3)
# 失稳临界（Rescdam 实验区间）
TST_CRIT_LO, TST_CRIT_HI = 0.64, 1.29
# 毛细/重力分界波长
LAMBDA_CG = 0.017       # m  (1.7 cm)


# ---------------- 雨滴终速 ----------------
def drop_terminal_velocity(D_mm, model="uplinger"):
    """静止空气中雨滴终速 m/s。D_mm 直径 mm。

    uplinger: V = 4.854*D*exp(-0.195*D)  —— 1~5mm 与 Gunn-Kinzer 实测吻合最好
    atlas   : U = 1767*D_cm^0.67 cm/s    —— 幂律形式，0.5~5mm 适用
    """
    if D_mm <= 0:
        raise ValueError(f"D_mm 必须 >0，收到 {D_mm}")
    if model == "uplinger":
        return 4.854 * D_mm * math.exp(-0.195 * D_mm)
    if model == "atlas":
        return AU_A * (D_mm / 10.0) ** AU_B / 100.0
    raise ValueError(f"未知终速模型 {model!r}")


# ---------------- 粒径分布（Marshall-Palmer） ----------------
def marshall_palmer_lambda(I_mm_h):
    """Λ = 4.1 * I^-0.21  (1/mm)，I 降雨强度 mm/h"""
    if I_mm_h <= 0:
        raise ValueError(f"雨强必须 >0，收到 {I_mm_h}")
    return 4.1 * I_mm_h ** (-0.21)


def drop_count_above(D_mm, I_mm_h):
    """单位体积空气中直径 >= D_mm 的滴数 (1/m^3)"""
    lam = marshall_palmer_lambda(I_mm_h)
    return (MP_N0 / lam) * math.exp(-lam * D_mm)


def median_volume_diameter(I_mm_h):
    """Best(1950) 中值体积直径 mm —— 控制液滴总体积的一半"""
    return 10.0 * BEST_A * I_mm_h ** BEST_N


def rain_intensity_class(I_mm_h):
    """US Fed. Meteor. Handbook No.1 分级"""
    if I_mm_h <= 2.5:
        return "light"
    if I_mm_h <= 7.6:
        return "moderate"
    return "heavy"


# ---------------- 风驱雨 ----------------
def rain_inclination(v_wind, D_mm):
    """偏离垂直的倾角 rad。α = arctan(v_wind / U)
    业界标准（MDPI / Purdue / AMS 三处独立一致）：
    1mm 滴(U≈4)在 4m/s 风中 → 45°；6.5m/s 滴在 1.5m/s 风中 → 13°
    """
    u = drop_terminal_velocity(D_mm)
    if u <= 0:
        raise ValueError("终速必须 >0")
    return math.atan2(v_wind, u)


def rain_velocity_vector(v_wind, D_mm):
    """雨滴速度矢量 (vx, vy) m/s，vy 向下为正"""
    u = drop_terminal_velocity(D_mm)
    return (v_wind, u)


def streak_length(v, t_exposure, D_mm):
    """雨线长度 m。L = V*t + 2R（V*t 为曝光位移，2R 为滴本身直径）"""
    return v * t_exposure + 2.0 * (D_mm / 1000.0)


# ---------------- 溅射（无量纲判据） ----------------
def dimensionless(D_mm, V):
    """返回 We / Re / Oh / Fr / K，判据 K = We * Oh^-0.4"""
    D = D_mm / 1000.0
    We = RHO_W * V * V * D / SIGMA_W
    Re = RHO_W * V * D / MU_W
    Oh = MU_W / math.sqrt(RHO_W * SIGMA_W * D)
    Fr = V * V / (G * D)
    K = We * Oh ** (-0.4)
    return {"We": We, "Re": Re, "Oh": Oh, "Fr": Fr, "K": K}


def splash_regime(K):
    """K < Kc 低 → 铺展合并；Kc 附近 → 冠状；远大于 → 完全飞溅（Worthington 射流）"""
    if K < K_C_LOW:
        return "spread"
    if K < K_C_HIGH:
        return "crown"
    return "splash"


# ---------------- 涉水 ----------------
def body_volume(mass_kg):
    """人体体积 m^3。V_p = a2*m + b2"""
    v = BODY_A2 * mass_kg + BODY_B2
    if v <= 0:
        raise ValueError(f"质量过小，体积非正：{mass_kg}kg")
    return v


def submerged_fraction(h_water, h_person):
    """相对淹没体积 Vb/Vp = a1*x^2 + b1*x, x = h_f/h_p（0<=x<=1）"""
    x = h_water / h_person
    x = min(max(x, 0.0), 1.0)
    return WAD_A1 * x * x + WAD_B1 * x


def buoyancy_force(h_water, h_person, mass_kg):
    """浮力 N"""
    return RHO_W * G * body_volume(mass_kg) * submerged_fraction(h_water, h_person)


def drag_force(v, area_m2, Cd=1.0):
    """拖曳力 F = 0.5*rho*Cd*S*v^2"""
    return 0.5 * RHO_W * Cd * area_m2 * v * v


def stability_abt(height_m, mass_kg):
    """Abt et al.(1989) 临界水深流速积 hv_c (m^2/s)"""
    return 0.0929 * (math.exp(0.001906 * height_m * mass_kg + 1.09)) ** 2


def wading_state(depth_m, v_flow, height_m, mass_kg):
    """涉水状态：滑移/倾倒双判据（铁律98）"""
    hv = depth_m * v_flow          # TST 倾倒
    hv2 = depth_m * v_flow ** 2    # SST 滑移
    crit = stability_abt(height_m, mass_kg)
    if hv >= crit:
        verdict = "toppling"
    elif hv >= TST_CRIT_LO:
        verdict = "marginal"
    else:
        verdict = "stable"
    return {
        "TST_d_v": hv, "SST_d_v2": hv2, "crit_abt": crit,
        "verdict": verdict,
        "buoyancy_N": buoyancy_force(depth_m, height_m, mass_kg),
        "drag_N": drag_force(v_flow, 0.026 * (depth_m / max(height_m, 1e-6))),
    }


# ---------------- 水面波 ----------------
def wave_omega(k, depth_m=None):
    """ω = sqrt((g*k + σ*k^3/ρ) * tanh(k*h))
    depth=None 视为深水 tanh->1
    """
    t = 1.0 if depth_m is None else math.tanh(k * depth_m)
    return math.sqrt((G * k + SIGMA_W * k ** 3 / RHO_W) * t)


def wave_speed(lambda_m, depth_m=None):
    """相速 cp = ω/k"""
    if lambda_m <= 0:
        raise ValueError("波长必须 >0")
    k = 2.0 * math.pi / lambda_m
    return wave_omega(k, depth_m) / k


def wave_regime(lambda_m):
    """λ < 1.7cm 毛细主导；否则重力主导"""
    return "capillary" if lambda_m < LAMBDA_CG else "gravity"


def capillary_gravity_crossover():
    """最小相速对应波长 m（猫爪波 ~1.7cm）"""
    return LAMBDA_CG


def ripple_from_rain(I_mm_h, depth_m=None):
    """雨滴击水产生的涟漪主波长 —— 取中值体积直径量级的毛细波"""
    d = median_volume_diameter(I_mm_h) / 1000.0
    lam = max(d * 4.0, LAMBDA_CG * 0.5)
    return {"lambda_m": lam, "cp_m_s": wave_speed(lam, depth_m),
            "regime": wave_regime(lam)}


# ---------------- 自检 ----------------
def self_check():
    ok = []
    def _chk(name, cond, info=""):
        ok.append((name, bool(cond), info))
        return bool(cond)

    # 1 终速：1mm≈4m/s（Gunn-Kinzer）
    v1 = drop_terminal_velocity(1.0)
    _chk("终速1mm≈4", 3.5 < v1 < 4.5, f"{v1:.2f}")
    # 2 终速：2mm≈6.5
    v2 = drop_terminal_velocity(2.0)
    _chk("终速2mm≈6.5", 6.0 < v2 < 7.0, f"{v2:.2f}")
    # 3 两模型 1~3mm 差 <15%
    for d in (1.0, 2.0, 3.0):
        a, b = drop_terminal_velocity(d, "uplinger"), drop_terminal_velocity(d, "atlas")
        _chk(f"两模型{d}mm一致<15%", abs(a - b) / max(a, b) < 0.15, f"{a:.2f}/{b:.2f}")

    # 4 Marshall-Palmer: 雨强越大 Λ 越小（大滴越多）
    l5, l50 = marshall_palmer_lambda(5), marshall_palmer_lambda(50)
    _chk("雨强↑则Λ↓", l50 < l5, f"{l5:.2f}->{l50:.2f}")

    # 5 倾斜角：1mm滴 4m/s风 → 45°
    a45 = math.degrees(rain_inclination(4.0, 1.0))
    _chk("1mm@4m/s≈45°", 42 < a45 < 48, f"{a45:.1f}°")
    # 6 倾斜角：6.5m/s滴 1.5m/s风 → 13°
    a13 = math.degrees(rain_inclination(1.5, 2.0))  # 2mm≈6.5m/s
    _chk("2mm@1.5m/s≈13°", 11 < a13 < 16, f"{a13:.1f}°")

    # 7 无量纲数与文献算例吻合（4mm @4m/s）
    dm = dimensionless(4.0, 4.0)
    _chk("We≈890", 800 < dm["We"] < 980, f"{dm['We']:.0f}")
    _chk("Re≈1.6e4", 1.4e4 < dm["Re"] < 1.8e4, f"{dm['Re']:.2e}")
    _chk("Oh≈1.9e-3", 1.7e-3 < dm["Oh"] < 2.1e-3, f"{dm['Oh']:.2e}")
    _chk("K≈1.1e4", 0.9e4 < dm["K"] < 1.3e4, f"{dm['K']:.2e}")
    _chk("4mm@4m/s 判为溅射", splash_regime(dm["K"]) == "splash")

    # 8 小滴低速不溅
    ds = dimensionless(0.5, 1.0)
    _chk("0.5mm@1m/s 不溅", splash_regime(ds["K"]) != "splash", f"K={ds['K']:.0f}")

    # 9 雨强分级
    _chk("分级light", rain_intensity_class(1.0) == "light")
    _chk("分级heavy", rain_intensity_class(20.0) == "heavy")

    # 10 失稳 Abt：1.75m/75kg → 1.35
    hv = stability_abt(1.75, 75.0)
    _chk("Abt≈1.35", 1.30 < hv < 1.40, f"{hv:.3f}")

    # 11 涉水：浅水低速稳定，深水高速倾倒
    s1 = wading_state(0.2, 0.5, 1.75, 75.0)
    s2 = wading_state(1.2, 1.5, 1.75, 75.0)
    _chk("浅水稳定", s1["verdict"] == "stable", s1["verdict"])
    _chk("深水急流倾倒", s2["verdict"] == "toppling", s2["verdict"])

    # 12 最小相速 ≈0.231 m/s @1.7cm
    cp = wave_speed(LAMBDA_CG)
    _chk("cp_min≈0.231", 0.21 < cp < 0.25, f"{cp:.3f}")
    # 13 毛细/重力分界
    _chk("λ<1.7cm为毛细", wave_regime(0.01) == "capillary")
    _chk("λ>1.7cm为重力", wave_regime(0.5) == "gravity")
    # 14 深水重力波 λ=1m → cp≈1.25
    cg = wave_speed(1.0)
    _chk("λ1m重力波cp≈1.25", 1.20 < cg < 1.30, f"{cg:.3f}")

    # 15 证伪：把 K_c 阈值改成 0 必须使"不溅"变"溅"
    global K_C_LOW, K_C_HIGH
    old = (K_C_LOW, K_C_HIGH)
    K_C_LOW, K_C_HIGH = 0.0, 0.0
    falsified = splash_regime(ds["K"]) == "splash"
    K_C_LOW, K_C_HIGH = old
    _chk("证伪:K_c归零则不溅变溅", falsified)

    # 16 证伪：终速模型名非法必须报错
    try:
        drop_terminal_velocity(2.0, "nope")
        _chk("证伪:非法模型报错", False, "竟通过")
    except ValueError:
        _chk("证伪:非法模型报错", True)

    bad = [x for x in ok if not x[1]]
    for n, c, i in ok:
        print(f"{'PASS' if c else 'FAIL'} {n} {i}")
    print(f"\n{sum(1 for _,c,_ in ok if c)}/{len(ok)} PASS")
    return len(bad) == 0


if __name__ == "__main__":
    raise SystemExit(0 if self_check() else 1)
