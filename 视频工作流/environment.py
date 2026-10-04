# -*- coding: utf-8 -*-
"""
environment ·红 环境黑板（单一数据源）+ 地表材质
史:notes/environment.md

结构来源：RDR2 GDC2021 terrain blackboard + Unity DOTS GlobalWeatherState
  —— 环境是 singleton，所有物体读同一份，禁止各算各的

物理规律统一在此，不在各系统内重复实现：
  1 相对速度   v_rel = v_wind - v_actor      （风阻取决于相对速度）
  2 力矩       tau   = F * r                 （力臂为0处位移必为0）
  3 地表摩擦   F_f   = mu * N                （干/湿/沙/雪/泥/碎石）
  4 面积反推   A     = k * (M/rho)^(2/3)     （由 mass 算，禁手填）
"""
import math
import physics as ph
import physics_rules as pr

# ---------------------------------------------------------- 地表材质
# 来源：OpenStax University Physics Table 6.1；SATRA TM144；GB/T 3903.6
# 实测规律：湿态比干态低 18~25%（水膜填充纹路间隙形成润滑层）
SURFACE = {
    #            mu_static  mu_kinetic  沉降   扬尘
    "stone":   dict(us=0.85, uk=0.76, sink=0.00, dust=0.10),  # 干燥石板/砖
    "stone_w": dict(us=0.66, uk=0.59, sink=0.00, dust=0.02),  # 湿石板 -22%(文献18-25%)
    "earth":   dict(us=0.80, uk=0.68, sink=0.01, dust=0.30),  # 夯土路面
    "sand":    dict(us=0.55, uk=0.45, sink=0.06, dust=0.55),  # 沙地（下沉+扬尘）
    "gravel":  dict(us=0.65, uk=0.52, sink=0.02, dust=0.25),  # 碎石
    "mud":     dict(us=0.45, uk=0.35, sink=0.12, dust=0.05),  # 泥泞
    "snow":    dict(us=0.30, uk=0.22, sink=0.15, dust=0.08),  # 积雪（下沉最深）
    "ice":     dict(us=0.10, uk=0.05, sink=0.00, dust=0.00),  # 冰（危险值）
    "water":   dict(us=0.20, uk=0.12, sink=0.30, dust=0.00),  # 涉水
}

# 蒲福风级 -> 风速。【逻辑唯一】改由 physics.beaufort 提供（数值表在 physics.BEAUFORT）
def beaufort(level):
    return ph.beaufort(level)


class Env:
    """环境黑板：一镜一份，所有 actor 读同一实例"""

    def __init__(self, wind_level=0, wind_dir=0.0, surface="stone",
                 temp_c=25.0, precip=0.0):
        self.wind_level = wind_level
        self.wind_speed = beaufort(wind_level)   # m/s
        self.wind_dir = wind_dir                 # rad, 0=+x
        self.surface = surface
        self.temp_c = temp_c
        self.precip = precip                    # mm/h
        self.surf = SURFACE.get(surface, SURFACE["stone"])

    # ---- 1 相对速度：这是风阻的正确输入 ----
    def rel_wind(self, actor_vel):
        """v_rel = v_wind - v_actor，返回 (vx, vy) m/s"""
        wx = self.wind_speed * math.cos(self.wind_dir)
        wy = self.wind_speed * math.sin(self.wind_dir)
        return (wx - actor_vel[0], wy - actor_vel[1])

    def drag_on(self, actor, actor_vel=(0.0, 0.0)):
        """完整风阻：相对速度 -> 力。返回 (Fx, Fy) N"""
        vr = self.rel_wind(actor_vel)
        sp = math.hypot(*vr)
        if sp <= 0.0:
            return (0.0, 0.0)
        area = pr.frontal_area(actor["mass"], actor["kind"])
        F = pr.drag_force(sp, area, actor.get("cd", 1.0),
                          b=actor.get("b_vogel", 0.0))
        return (F * vr[0] / sp, F * vr[1] / sp)

    # ---- 2 力矩：力臂为 0 处位移必为 0 ----
    @staticmethod
    def torque(F, r):
        """tau = F * r。r=0 -> tau=0（旗杆处锁死的物理依据）"""
        return F * r

    @staticmethod
    def swing_profile(t, r_ratio, freq=0.6, phase=0.0):
        """
        摆动幅度沿长度的分布：pinned 端 0，自由端最大。
        r_ratio: 0=固定端 1=自由端
        """
        return r_ratio * math.sin(2 * math.pi * freq * t + phase)

    # ---- 3 地表摩擦 ----
    def friction(self, mass, moving=True):
        """F_f = mu * N，N = m*g。返回 (力N, 判据)"""
        mu = self.surf["uk"] if moving else self.surf["us"]
        N = mass * pr.G
        return mu * N, mu

    def slip(self, mass, tangential_force):
        """是否打滑：切向力 > 最大静摩擦则滑"""
        f_max, mu = self.friction(mass, moving=False)
        return tangential_force > f_max, mu, f_max

    # ---- 3b 3D Coulomb 摩擦锥（X_b）----
    def cone_directions(self, k=8):
        """摩擦锥金字塔近似的方向向量（水平面内均分）。"""
        import math
        return [(math.cos(2 * math.pi * i / k), 0.0,
                 math.sin(2 * math.pi * i / k)) for i in range(k)]

    def slip_cone(self, force3, normal_dir=(0.0, 1.0, 0.0), moving=False):
        """3D Coulomb 摩擦锥判据 -> (是否打滑, 切向/法向比值, mu)

        接触稳定条件（业界标准）：
          f·a > 0                     法向力必须由地面指向物体
          ||f^t|| <= mu * ||f^n||     切向力不得超出摩擦锥，否则进入滑动
        其中 f^n = (f·a)a，f^t = f - f^n。

        数值优化中常用【金字塔近似】把二阶锥线性化（本文 k=8）。
        保留原 slip() 不动 —— 它已是本判据的一维特例。
        """
        a = _norm3(normal_dir)
        f = tuple(float(x) for x in force3)
        fn = _dot(f, a)                       # 法向分量（标量）
        if fn <= 0.0:
            return (False, float("inf"), self.surf["uk" if moving else "us"])
        ft = _sub(f, _scale(a, fn))           # 切向分量（向量）
        ratio = _len3(ft) / fn
        mu = self.surf["uk"] if moving else self.surf["us"]
        return (ratio > mu, ratio, mu)

    # ---- 4 扬尘/沉降：地表 + 风速共同决定 ----
    def dust_amount(self):
        """扬尘强度 = 地表扬尘系数 * 风速归一化"""
        return min(1.0, self.surf["dust"] * (self.wind_speed / 12.0))

    def sink_px(self, px_per_m):
        """脚下沉降（像素）"""
        return self.surf["sink"] * px_per_m


# ---------------------------------------------------------- 自检
if __name__ == "__main__":
    import actors
    print("=" * 70)
    print("environment 自检")
    print("=" * 70)

    ok = True

    # 1 相对速度：逆风 vs 顺风
    e = Env(wind_level=6, wind_dir=math.pi)  # 风向 -x
    xz = actors.ACTORS["xz"]
    v_walk = 120 / 60 * 0.765          # 步频120/分 x 步幅0.765
    F_head = e.drag_on(xz, (v_walk, 0))[0]     # 逆风（人往+x，风往-x）
    F_tail = e.drag_on(xz, (-v_walk, 0))[0]    # 顺风
    print("1 相对速度（走 1.53 m/s，6级风 12.29 m/s）")
    print(f"   逆风 F={abs(F_head):.1f}N   顺风 F={abs(F_tail):.1f}N")
    d = abs(F_head) / abs(F_tail)
    # 人非柔性体，Vogel B=0，F ∝ v^2：(13.82/10.76)^2 = 1.65
    th = ((12.29 + v_walk) / (12.29 - v_walk)) ** 2
    print(f"   比值 {d:.2f}x  (理论 {th:.2f})  "
          f"{'OK' if abs(d - th) < 0.05 else '偏差'}")
    ok &= abs(d - th) < 0.05

    # 2 力矩：力臂 0 -> 位移 0
    print("2 力矩（力臂为0处必须锁死）")
    r0 = abs(Env.swing_profile(0.5, 0.0))
    r1 = abs(Env.swing_profile(0.5, 1.0))
    print(f"   r=0 位移 {r0:.3f}   r=1 位移 {r1:.3f}")
    print(f"   {'OK' if r0 < 1e-9 and r1 > 0 else 'FAIL'}")
    ok &= r0 < 1e-9 and r1 > 0

    # 3 地表摩擦：湿态必须低于干态
    print("3 地表摩擦（湿态应低于干态 18-25%）")
    for dry, wet in [("stone", "stone_w")]:
        fd, _ = Env(surface=dry).friction(62.0)
        fw, _ = Env(surface=wet).friction(62.0)
        drop = (1 - fw / fd) * 100
        print(f"   {dry} {fd:.0f}N -> {wet} {fw:.0f}N  降 {drop:.0f}%  "
              f"{'OK' if 15 < drop < 30 else '偏差'}")
        ok &= 15 < drop < 30

    # 4 打滑判据：冰面必须滑
    print("4 打滑判据")
    for s in ["stone", "sand", "ice"]:
        sl, mu, fmax = Env(surface=s).slip(62.0, 300.0)
        print(f"   {s:<7} mu={mu:.2f} f_max={fmax:6.0f}N  打滑={sl}")
    sl_ice, _, _ = Env(surface="ice").slip(62.0, 300.0)
    sl_st, _, _ = Env(surface="stone").slip(62.0, 300.0)
    print(f"   {'OK' if sl_ice and not sl_st else 'FAIL'}")
    ok &= sl_ice and not sl_st

    # 5 扬尘/沉降随地表变化
    print("5 扬尘与沉降")
    for s in ["stone", "sand", "snow"]:
        en = Env(wind_level=6, surface=s)
        print(f"   {s:<7} 扬尘 {en.dust_amount():.2f}  沉降 "
              f"{en.sink_px(406.5):.1f}px")
    ok &= Env(wind_level=6, surface="sand").dust_amount() > \
        Env(wind_level=6, surface="stone").dust_amount()

    print("=" * 70)
    print("PASS" if ok else "FAIL")


def _norm3(v):
    import math
    n = math.sqrt(sum(float(x) ** 2 for x in v))
    if n < 1e-12:
        return (0.0, 1.0, 0.0)
    return tuple(float(x) / n for x in v)


def _dot(u, v):
    return sum(float(a) * float(b) for a, b in zip(u, v))


def _scale(v, s):
    return tuple(float(x) * s for x in v)


def _sub(u, v):
    return tuple(float(a) - float(b) for a, b in zip(u, v))


def _len3(v):
    import math
    return math.sqrt(sum(float(x) ** 2 for x in v))
