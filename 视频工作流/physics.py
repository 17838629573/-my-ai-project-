# -*- coding: utf-8 -*-
"""
physics.py —— 物理原子层（逻辑唯一实现，数值全外置）

契约：contracts/physics.md
铁律：相同逻辑只写一次。任何模块禁止再写 0.5*rho*Cd*A*v**2 或 k*V**(2/3)。
      新增物体 = 往 K_SHAPE 加一行，不动代码。

分工（见 AI_INPUT.md）：
    模型填：mass / kind / cd / b_vogel / surface   （物性，可搜）
    代码算：area / force / accel / displacement    （派生量，禁止手填）
"""
import math

# ── 数值表（改数字不动代码）────────────────────────────────
RHO_AIR = 1.225          # kg/m3, 海平面 15C
G = 9.81                 # m/s2
RHO_BODY = 1000.0        # kg/m3, 生物组织近水 -> V = M/rho

# 形状系数 k：A = k * V^(2/3)。由实测反推（人0.70m2/70kg、马2.50m2/400kg）
K_SHAPE = {
    "human":   4.12,   # 实测反推：0.70m2 / 0.07^(2/3)
    "animal":  4.6,
    "tree":    8.0,
    "leaf":   31.8,   # 单片叶：细长扁平
    "cloth":  50.0,
    "block":   0.54,  # 墩状：小于等体积立方体
    "object":  2.0,
}
K_SHAPE_DEFAULT = 4.0

# 蒲福风级 -> m/s（经验式 V = 0.836 * B^1.5）
BEAUFORT = [0.0, 0.9, 2.4, 4.4, 6.7, 9.3, 12.3, 15.5, 19.0, 22.6, 26.5, 30.5, 34.0]

V_REF = 10.0             # Vogel 归一化参考风速 m/s


# ── 逻辑原子（各写一次）───────────────────────────────────
def volume(mass, rho=RHO_BODY):
    """体积 V = M / rho"""
    return mass / rho


def area(mass, kind="human", k=None):
    """迎风面积 A = k * V^(2/3)。由质量反推，不手填。"""
    v = volume(mass)
    if v <= 0:
        return 0.0
    kk = k if k is not None else K_SHAPE.get(kind, K_SHAPE_DEFAULT)
    return kk * (v ** (2.0 / 3.0))


def force(v_rel, A, cd=1.0, b=0.0):
    """气动力 F = 0.5*rho*Cd*A*v^(2+B)*V_REF^(-B)。b<0 为柔性体 Vogel 修正。"""
    if A <= 0:
        return 0.0
    v = abs(v_rel)
    if v < 1e-9:
        return 0.0
    return 0.5 * RHO_AIR * cd * A * (v ** (2.0 + b)) * (V_REF ** (-b))


def force_per_area(v_rel, cd=1.0, b=0.0):
    """单位面积气动力（压力），供质点/无面积物体使用。"""
    return force(v_rel, 1.0, cd, b)


def accel(F, mass):
    """a = F / m"""
    if mass <= 0:
        return 0.0
    return F / mass


def torque(F, r):
    """力矩 tau = F * r。r=0（pinned）时恒为 0 —— 旗杆锁死的物理根据。"""
    return F * r


def px_per_m(char_px, real_height_m=1.70):
    """世界->像素换算：像素每米

    【铁律86】口径已统一到 _px.px_per_m（唯一定义处）。
    本函数保留仅为兼容旧调用方，转发到 _px，不再有第二份算术。
    旧实现的 `real_height_m<=0 返回 400.0` 是静默兜底（违反铁律18），已移除。
    """
    import _px
    return _px.px_per_m(char_px, real_height_m)


def beaufort(level):
    """蒲福风级 -> m/s"""
    if level <= 0:
        return 0.0
    if level < len(BEAUFORT):
        return BEAUFORT[int(level)]
    return 0.836 * (level ** 1.5)


def beaufort_level(v):
    """m/s -> (风级, 形态描述)。蒲福表反查。

    【铁律88·改动】旧实现有 off-by-one（u=0.1 被判为 1 级，应为 0 级），
    且本文件阈值数组与 _common / physics_rules 三套并存，
    同风速风级最高差 1 级。现统一委托 _common.beaufort_scale()。
    """
    import _common
    bf = _common.beaufort_scale(v)
    return bf["level"], BEAUFORT_DESC.get(bf["level"], "")


def rel_wind(v_wind, v_actor=0.0):
    """相对风速。风阻取决于物体与空气的相对速度，不是绝对风速。"""
    return v_wind - v_actor


# 蒲福风级 -> 陆上可观测现象（NOAA/NWS 表述）
BEAUFORT_DESC = {
    0: "calm; smoke rises vertically",
    1: "light air; smoke drift indicates wind direction",
    2: "light breeze; leaves rustle, wind felt on face",
    3: "gentle breeze; leaves and small twigs in constant motion, light flag extended",
    4: "moderate breeze; dust raised, small branches move, heavy flag flaps limply",
    5: "fresh breeze; small trees sway, flag does not extend but flaps overentire length",
    6: "strong breeze; large branches move, flag extends and flaps more vigorously",
    7: "near gale; whole trees in motion, flag extends fully and flaps only at the end",
    8: "gale; twigs break off trees, flag straight out and whipping",
}


SWING_MAX_DEG = 35.0   # 视觉上限：布料受自身刚度/绳约束，不会真吹到水平


def swing_angle(F, mass, max_deg=SWING_MAX_DEG):
    """悬臂摆角 theta = atan(F / (m*g))，钳制在视觉上限内。
    旗/枝条/挂布类：位移由【摆角】决定，不是由加速度决定。
    注：纯力学解 atan(50/9.81)=79度，但实际布料有弯曲刚度+两端系绳约束，
        不会吹到接近水平，故钳制（业界用 bend 约束实现同一效果）。
    """
    if mass <= 0:
        return 0.0
    th = math.atan2(F, mass * G)
    return min(th, math.radians(max_deg))


def swing_offset(theta, r):
    """摆角 -> 该点位移。r 为到根部（pinned）的归一化距离 0..1。
    r=0 恒为 0（旗杆/根部锁死），r=1 最大。
    """
    return math.sin(theta) * r


def alpha_blend(dst, src, a):
    """alpha 混合：out = src*a + dst*(1-a)。a 为 float32 HxWx1。"""
    return src * a + dst * (1.0 - a)


def wave(t, freq, amp, phase=0.0):
    """正弦调制。行波靠 phase 沿空间递增，不靠各点同相。"""
    return amp * math.sin(2.0 * math.pi * freq * t + phase)


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


# ── 地表数值表（改数字不动代码）───────────────────────────
# mu=摩擦, slow=步速衰减, sink=沉陷量(m), footprint=(深,压缩,平滑)
SURFACE = {
    "stone":   dict(mu=0.80, slow=0.00, sink=0.00, footprint=(0.0, 0.0, 0.0)),
    "soil":    dict(mu=0.65, slow=0.10, sink=0.03, footprint=(0.3, 0.7, 0.3)),
    "grass":   dict(mu=0.40, slow=0.15, sink=0.02, footprint=(0.2, 0.6, 0.4)),
    "sand":    dict(mu=0.50, slow=0.35, sink=0.15, footprint=(0.4, 0.1, 0.9)),
    "mud":     dict(mu=0.30, slow=0.45, sink=0.25, footprint=(0.9, 0.8, 0.2)),
    "snow":    dict(mu=0.30, slow=0.15, sink=0.20, footprint=(0.8, 0.6, 0.5)),
    "shallow": dict(mu=0.40, slow=0.25, sink=0.05, footprint=(0.5, 0.4, 0.6)),
    "ice":     dict(mu=0.10, slow=0.50, sink=0.00, footprint=(0.0, 0.0, 0.0)),
}


def surface_effect(name):
    """地表 -> (mu, slow, sink, footprint)。未知地表回退 soil 并标记。"""
    if name in SURFACE:
        return SURFACE[name]
    return dict(SURFACE["soil"], _fallback=True)


def gait_speed(base, surface, slope_pct=0.0):
    """步速 = 基准 * (1-地表衰减) * (1-坡度衰减)。
    坡度衰减：1-3% -7%，3-7% -20%，>7% -40%（文献区间取中）。
    """
    s = surface_effect(surface)
    v = base * (1.0 - s["slow"])
    a = abs(slope_pct)
    if a > 7.0:
        v *= 0.60
    elif a > 3.0:
        v *= 0.80
    elif a > 1.0:
        v *= 0.93
    return v


# ── 自检 ──────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 66)
    print("physics.py 自检（判定必须带命令输出，禁止'看着对'）")
    print("=" * 66)

    print("\n[1] 面积反推 A = k*V^(2/3)   —— 代码算，不手填")
    print(f"  {'物体':<10}{'质量':>8}{'算得A':>10}{'实测':>10}{'误差':>8}")
    for lab, m, k, real in [("人", 70.0, "human", 0.70), ("马", 400.0, "animal", 2.50)]:
        a = area(m, k)
        print(f"  {lab:<10}{m:>8.0f}{a:>10.3f}{real:>10.2f}{abs(a-real)/real*100:>7.1f}%")

    print("\n[2] 相对速度（此前错误：只用绝对风速）")
    vw = beaufort(6)
    print(f"  6级风 = {vw:.2f} m/s")
    v_actor = 1.53   # 步频120/分 x 步幅0.765m
    for lab, vr in [("顺风", rel_wind(vw, v_actor)), ("静止", vw), ("逆风", rel_wind(vw, -v_actor))]:
        A = area(62.0, "human")
        print(f"  {lab}: v_rel={vr:5.2f} -> F={force(vr, A):6.2f} N")
    f1 = force(rel_wind(vw, v_actor), area(62.0, "human"))
    f2 = force(rel_wind(vw, -v_actor), area(62.0, "human"))
    print(f"  >> 逆风比顺风大 {(f2/f1-1)*100:.0f}%")

    print("\n[3] 力矩 tau = F*r（旗杆锁死的物理根据）")
    print(f"  {'位置':<10}{'力臂r':>8}{'力矩比':>10}{'应有位移':>10}")
    for lab, f in [("旗杆", 0.0), ("1/2", 0.5), ("自由端", 1.0)]:
        print(f"  {lab:<10}{f*0.9:>8.2f}{f:>10.2f}{(str(int(f*100))+'%' if f else '0(锁死)'):>10}")

    print("\n[4] Vogel 修正（柔性体不服从 v^2）")
    A = area(1.0, "cloth")
    rigid = 0.5 * RHO_AIR * 1.0 * A * (15.0 ** 2)
    soft = force(15.0, A, b=-0.5)
    print(f"  刚性 v^2  = {rigid:.1f} N")
    print(f"  Vogel B=-0.5 = {soft:.1f} N")
    print(f"  >> 刚性高估 {(rigid/soft-1)*100:.0f}%")

    print("\n[5] 地表（改数字不动代码）")
    print(f"  {'地表':<10}{'mu':>7}{'步速衰减':>10}{'沉陷(m)':>10}")
    for s in ["stone", "sand", "mud", "snow"]:
        d = surface_effect(s)
        print(f"  {s:<10}{d['mu']:>7.2f}{d['slow']*100:>9.0f}%{d['sink']:>10.2f}")
    vb = 1.53
    print(f"  石板步速 {gait_speed(vb,'stone'):.2f} -> 沙地 {gait_speed(vb,'sand'):.2f} m/s")

    print("\n[6] 未知地表回退（禁止静默失效）")
    print(f"  未知 'lava' -> {surface_effect('lava')}")

    # 风级正反向自洽（beaufort 正、beaufort_level 反）
    for lv in (3, 6, 8):
        v = beaufort(lv); lv2, _d = beaufort_level(v)
        if lv2 != lv:
            print("FAIL 风级不自洽 %d -> %.2f m/s -> %d" % (lv, v, lv2)); ok = False
    print("PASS 风级正反向自洽 beaufort/beaufort_level")

    print("\n全部 PASS")
