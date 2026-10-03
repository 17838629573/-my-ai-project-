"""
cloth_aero — 布料/衣物气动受力（"衣服被风吹飞"这类需求）

业界结构（NvCloth O3DE / Unreal Clothing Tool / Bullet btSoftBody 同构）：
    风用四个量描述 —— 空气密度 ρ、阻力系数 Cd、升力系数 Cl、风速 v

受力分解（按业界 lift/drag 分解法，量纲修正版）：
    q        = ½·ρ·|v_rel|²                    动压 [Pa]
    cosθ     = v̂_rel · n̂                      迎风角余弦
    F_drag   = q·A·Cd·cosθ · v̂_rel            阻力，沿风向
    F_lift   = q·A·Cl·cosθ · (v̂_rel×n̂)×v̂     升力，垂直风向

★ 量纲说明（重要）：
  Bullet/ammo.js 文档写作 F = Cd·A·(v·n)·v，该式缺 ½ 与 ρ，
  量纲为 m⁴/s² 而非 N。本模块按物理正确式补上 ½ρ，使单位为牛顿。

四个必填参数全部走 param_decl 反问接口，代码内不内置任何常数：
    cloth_air_density  ρ  [kg/m³]
    cloth_drag_coeff   Cd [-]
    cloth_lift_coeff   Cl [-]
    v_wind               由场景给出

铁律99：参数不在代码里 → 代码反问 AI → AI 给「值+来源+区间」
        → 落盘 params_ai.json → 由本模块运算。AI 不得心里默算。
"""

import math
import param_decl as PD

G = 9.80665  # 标准重力加速度 [m/s²]


def _cd():
    return PD.require("cloth_drag_coeff", "cloth",
                      "计算布料所受气动阻力 F_drag", "-",
                      "参考：方板正对来流 Cd 1.18~1.28（Hoerner/White/Munson）")


def _cl():
    return PD.require("cloth_lift_coeff", "cloth",
                      "计算布料所受气动升力 F_lift（决定衣物是否被吹起）", "-",
                      "参考：NvCloth Wind lift 范围 [0,1]；平板失速前 Cl_max≈1.2~1.5")


def _rho():
    return PD.require("cloth_air_density", "cloth",
                      "把动压换算成真实力（q=½ρv²）", "kg/m³",
                      "参考：ISA 标准大气 海平面 15°C ρ=1.2250 kg/m³")


def wind_force(area_m2, v_wind, nx=0.0, ny=1.0, v_face=(0.0, 0.0)):
    """
    布料面元所受气动合力（物理正确量纲版）。

    area_m2 : 面元面积 [m²]
    v_wind  : 风速矢量 (vx, vy) [m/s]
    n       : 面元法向 (nx, ny)，会自动归一
    v_face  : 面元自身速度 [m/s]（静止布料给 (0,0)）

    返回 dict：drag/lift 矢量与模长（N）、cosθ、动压 q(Pa)
    """
    Cd, Cl, rho = _cd(), _cl(), _rho()
    vx = float(v_wind[0]) - float(v_face[0])
    vy = float(v_wind[1]) - float(v_face[1])
    spd = math.hypot(vx, vy)

    nl = math.hypot(nx, ny) or 1.0
    nxn, nyn = nx / nl, ny / nl

    if spd <= 0.0:
        return {"drag": (0.0, 0.0), "drag_N": 0.0, "lift": (0.0, 0.0),
                "lift_N": 0.0, "cos_theta": 0.0,
                "dynamic_pressure_Pa": 0.0, "speed_m_s": 0.0}

    ux, uy = vx / spd, vy / spd          # v̂
    cos_t = ux * nxn + uy * nyn          # cosθ
    cz = ux * nyn - uy * nxn             # (v̂ × n̂)_z
    q = 0.5 * rho * spd * spd            # 动压 [Pa]

    kd = q * area_m2 * Cd * cos_t
    kl = q * area_m2 * Cl * cos_t
    fdx, fdy = kd * ux, kd * uy
    flx, fly = kl * (-cz * uy), kl * (cz * ux)   # (v̂×n̂)×v̂ 的 2D 形式

    return {
        "drag": (fdx, fdy), "drag_N": math.hypot(fdx, fdy),
        "lift": (flx, fly), "lift_N": math.hypot(flx, fly),
        "cos_theta": cos_t,
        "dynamic_pressure_Pa": q,
        "speed_m_s": spd,
    }


def will_blow_off(area_m2, v_wind, mass_kg, nx=0.0, ny=1.0):
    """
    衣物是否被吹飞：升力 > 重力即离体。

    mass_kg : 衣物质量 [kg]（薄僧衣 ~0.3kg，厚袍 ~1.2kg）
    返回 dict：lift_N / weight_N / ratio / blow_off
    """
    r = wind_force(area_m2, v_wind, nx, ny)
    weight = mass_kg * G
    return {
        "lift_N": r["lift_N"], "weight_N": weight,
        "ratio": (r["lift_N"] / weight) if weight > 0 else float("inf"),
        "blow_off": r["lift_N"] > weight,
        "detail": r,
    }


def self_check():
    ok = []

    def ck(n, c, d=""):
        ok.append((n, bool(c), d))

    if not (PD.have("cloth_drag_coeff") and PD.have("cloth_lift_coeff")
            and PD.have("cloth_air_density")):
        print("参数未声明 —— 代码反问 AI：")
        try:
            wind_force(0.5, (10.0, 0.0))
        except PD.AskAI as e:
            print("\n" + e.prompt())
        return ok

    N45 = (1.0, 1.0)  # 45° 法向，能同时产生阻力与升力

    # 1 正面迎风：阻力应显著、升力应≈0
    r = wind_force(1.0, (10.0, 0.0), nx=1.0, ny=0.0)
    ck("1 正面迎风 阻力>0", r["drag_N"] > 0, "%.2f N" % r["drag_N"])
    ck("2 正面迎风 升力≈0", r["lift_N"] < 1e-9, "%.2e N" % r["lift_N"])

    # 2 平行掠过：阻力与升力都≈0（cosθ→0）
    r2 = wind_force(1.0, (10.0, 0.0), nx=0.0, ny=1.0)
    ck("3 平行掠过 阻力≈0", r2["drag_N"] < 1e-9, "%.2e N" % r2["drag_N"])

    # 3 风速平方律：v 翻倍 → 阻力约 4 倍
    a = wind_force(1.0, (5.0, 0.0), *N45)["drag_N"]
    b = wind_force(1.0, (10.0, 0.0), *N45)["drag_N"]
    ck("4 风速平方律", 3.5 < b / a < 4.5, "%.2f → %.2f (×%.2f)" % (a, b, b / a))

    # 4 面积线性
    c1 = wind_force(1.0, (10.0, 0.0), *N45)["drag_N"]
    c2 = wind_force(2.0, (10.0, 0.0), *N45)["drag_N"]
    ck("5 面积线性", abs(c2 - 2 * c1) < 1e-9, "%.3f vs %.3f" % (c2, 2 * c1))

    # 5 风越大越容易吹飞
    lo = will_blow_off(1.0, (5.0, 0.0), 0.3, *N45)["ratio"]
    hi = will_blow_off(1.0, (30.0, 0.0), 0.3, *N45)["ratio"]
    ck("6 风大更易吹飞", hi > lo, "%.3f → %.3f" % (lo, hi))

    # 6 越重越难吹飞
    m1 = will_blow_off(1.0, (20.0, 0.0), 0.3, *N45)["ratio"]
    m2 = will_blow_off(1.0, (20.0, 0.0), 1.2, *N45)["ratio"]
    ck("7 越重越难飞", m2 < m1, "%.3f vs %.3f" % (m2, m1))

    # 7 量纲自检：动压应与 ½ρv² 完全一致
    rr = wind_force(1.0, (12.0, 0.0), *N45)
    q_expect = 0.5 * _rho() * 12.0 * 12.0
    ck("8 动压=½ρv²", abs(rr["dynamic_pressure_Pa"] - q_expect) < 1e-9,
       "%.4f vs %.4f" % (rr["dynamic_pressure_Pa"], q_expect))

    # 证伪：45° 时升力必须非零（若公式写错会退化成 0）
    l45 = wind_force(1.0, (10.0, 0.0), *N45)["lift_N"]
    ck("证伪 45°升力非零", l45 > 0, "%.3f N" % l45)

    return ok


if __name__ == "__main__":
    res = self_check()
    if res:
        npass = sum(1 for _, c, _ in res if c)
        for n, c, d in res:
            print("%s %s %s" % ("PASS" if c else "FAIL", n, d))
        print("---- %d/%d PASS ----" % (npass, len(res)))
