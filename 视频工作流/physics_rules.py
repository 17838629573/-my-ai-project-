"""
physics_rules.py —— 物性推导与风力计算

【分工铁律】
  模型（搜）填：M 质量 / rho 密度 / kind（定 k）/ Cd / B_vogel / body_type
  代码（算）：V = M/rho → A = k·V^(2/3) → F → a = F/m → 位移
  禁止模型直接填"摆多少像素" —— 那是结果不是输入。
  （前车之鉴：COM_V_RATIO 手填 0.018，实测峰峰 6.1cm 超文献上限 5cm）

来源：notes/physics.md
"""
import math

__all__ = ["RHO_AIR", "G", "K_SHAPE", "B_VOGEL", "BEAUFORT",
           "volume_of", "frontal_area", "vogel_exponent", "drag_force",
           "accel", "beaufort", "raindrop_v", "describe"]

# ---------------------------------------------------------------- 常量
RHO_AIR = 1.225      # kg/m³ 海平面 15°C
G = 9.81             # m/s²
RHO_TISSUE = 1000.0  # kg/m³ 生物组织近水

# ------------------------------------------------- 形状系数 k（按 kind）
# A = k · V^(2/3)。k = 细长度(长径比)，实测反推见 notes/physics.md
K_SHAPE = {
    "human":  4.12,   # 70kg → A=0.70 m²（文献正面迎风 0.68-0.9）
    "animal": 4.61,   # 400kg 马 → A=2.50 m²
    "cloth":  50.0,   # 薄片
    "leaf":   31.8,   # 【单片叶】反推，不可用于整树
    "tree":   8.0,    # 整树冠（含叶，粗估，需按树种校准）
    "plant":  31.8,   # 兼容旧名 = leaf
    "object": 0.54,   # 块体/建筑
    "fluid":  1.0,    # 面积另给，不适用
}
# 圆柱（树干）半径恒定时 S ∝ V^1.0 而非 2/3 —— Galileo 已指出
TRUNK_EXPONENT = 1.0

# -------------------------------------------- Vogel 指数（柔性体重构型）
# F ∝ v^(2+B)，B 为负：风大时迎风面积自己变小，阻力增长比平方慢
B_VOGEL = {
    "poplar":  -0.71,   # 整棵杨树（带叶）
    "daffodil": -0.60,
    "grass":   -0.52,
    "seaweed": -0.93,
}

# ------------------------------------------------------ 蒲福风级（m/s）
# (下限, 上限, 陆上现象)
BEAUFORT = [
    (0.0,  0.2,   "静，烟直上"),
    (0.3,  1.5,   "烟能表示风向"),
    (1.6,  3.3,   "树叶微响"),
    (3.4,  5.4,   "树叶与小枝摇动不息，旌旗展开"),
    (5.5,  7.9,   "扬尘，小树枝摇动"),
    (8.0,  10.7,  "有叶小树整棵摇摆"),
    (10.8, 13.8,  "大树枝摇动，电线呼呼"),
    (13.9, 17.1,  "全树摇动"),
    (17.2, 20.7,  "树枝折断"),
    (20.8, 24.4,  "建筑轻微损坏"),
    (24.5, 28.4,  "树木拔起"),
]


def volume_of(mass, rho=RHO_TISSUE):
    """V = M / ρ"""
    return mass / rho


def frontal_area(mass, kind="human", rho=RHO_TISSUE, trunk=False):
    """
    A = k · V^(2/3)
    trunk=True 用于树干：半径恒定 → 指数 1.0（Galileo）
    """
    v = volume_of(mass, rho)
    if v <= 0:
        return 0.0
    e = TRUNK_EXPONENT if trunk else (2.0 / 3.0)
    k = K_SHAPE.get(kind, 1.0)
    return k * (v ** e)


def vogel_exponent(kind="human", flexible=False):
    """柔物体返回 Vogel 指数 B（负），刚体返回 0.0"""
    if not flexible:
        return 0.0
    return B_VOGEL.get(kind, -0.6)


def drag_force(v, area, cd=1.0, rho=RHO_AIR, b=0.0):
    """
    F = ½·ρ·v²·Cd·A         刚体
    F = ½·ρ·v^(2+B)·Cd·A    柔性体（B<0，阻力增长更慢）
    """
    if v <= 0 or area <= 0:
        return 0.0
    # 指数修正时以 1 m/s 为基准保持量纲一致
    vv = (v ** (2.0 + b)) if b else (v * v)
    return 0.5 * rho * vv * cd * area


def accel(force, mass):
    """a = F / m"""
    if mass <= 0:
        return 0.0
    return force / mass


def beaufort(v):
    """风速 → (等级, 描述)

    【铁律88·改动】旧实现用本地 (lo,hi,desc) 表，与 _common 区间表
    不同，同风速风级最高差 1 级。现统一委托 _common.beaufort_scale()。
    """
    import _common
    bf = _common.beaufort_scale(v)
    return bf["level"], bf["name"]


def raindrop_v(d_mm):
    """雨滴终端速度 Gunn-Kinzer 拟合，R²=0.999"""
    return 9.5 * (1.0 - math.exp(-0.54 * (d_mm ** 1.13)))


def describe(name, mass, kind, wind_v, cd=1.0, flexible=False):
    """一行诊断：物性 → 受力 → 加速度"""
    A = frontal_area(mass, kind)
    b = vogel_exponent(kind, flexible)
    F = drag_force(wind_v, A, cd, b=b)
    a = accel(F, mass)
    bft, desc = beaufort(wind_v)
    return (f"{name:<8} M={mass:<8.4g} A={A:<7.3f} "
            f"F={F:<8.3f}N a={a:<7.3f}m/s²  {bft}级({desc[:8]})")


if __name__ == "__main__":
    print("=== physics_rules 自检 ===")
    print("1 面积公式反推（对照实测）")
    for n, m, k, exp in [("人70kg", 70, "human", 0.70),
                         ("马400kg", 400, "animal", 2.50)]:
        a = frontal_area(m, k)
        print(f"   {n:<9} 算得A={a:.3f} 实测≈{exp}  "
              f"误差{abs(a-exp)/exp*100:.1f}%")
    print()
    print("2 风力 → 加速度（10 m/s，5级风）")
    for n, m, k in [("玄奘", 70, "human"), ("赤马", 400, "animal"),
                    ("旗", 1, "cloth"), ("叶", 0.0005, "plant")]:
        print("  ", describe(n, m, k, 10.0))
    print()
    print("3 刚性 vs Vogel 修正（整树 200kg，B=-0.71）")
    A = frontal_area(200, "tree")
    fr = drag_force(20.0, A)
    fv = drag_force(20.0, A, b=-0.71)
    print(f"   刚性 F={fr:.1f}N   Vogel F={fv:.1f}N   "
          f"比值={fv/fr:.3f}（刚性会高估 {(fr/fv-1)*100:.0f}%）")
    print()
    print("4 蒲福风级")
    for v in [2.0, 8.0, 15.0, 25.0]:
        b_, d_ = beaufort(v)
        print(f"   {v:>5.1f} m/s → {b_} 级 {d_}")
    print()
    print("5 雨滴终端速度")
    for d in [0.5, 1.0, 2.0, 5.0]:
        print(f"   D={d}mm → v={raindrop_v(d):.2f} m/s")
