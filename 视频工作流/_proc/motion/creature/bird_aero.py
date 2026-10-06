# -*- coding: utf-8 -*-
# 契约: proc/motion/creature/bird_aero
#   一句话: 鸟翼气动与翼骨几何的纯函数真源（自 bird_fly 拆出，供其导入）
"""鸟翼气动：叶素法升阻系数与翼骨架几何（自 bird_fly 拆出）。

契约
  输入  t 秒、f 拍翅频率、U 前进速度、b 翼展、S 翼面积、m 质量等标量
  输出  纯标量/元组：气动系数 CL/CD、扑动角 φ、折叠因子 eff、扫掠角 θ、
        (Fx, Fy) 气动合力、配平攻角 α0
  依赖  base（math、常量）；无状态、无副作用，不依赖模块主流程

判定判据（每条附出处）
  行程角 θ(b)       θ ≈ 67·b^(−0.24)                        Nudds 2004
  上下冲程不对称     down_frac=0.55 > 0.5，下扑为动力相占时更长  RoboFalcon2.0(PMC)
  上举中段折叠       eff → FOLD=0.62（气动不活跃）             RoboFalcon2.0(PMC)
  下扑全展           eff = 1                                RoboFalcon2.0(PMC)
  扑动角 C1 连续     两段余弦端点导数均为 0                     周期衔接无速度突跳
  升力系数           薄翼位流 CL=2π·sinα，失速饱和 ±1.5         Pennycuick 2008
  阻力系数           CD=CD0+CL²/(π·AR·e)，AR=b²/S，e=0.9       Pennycuick 2008

已知偏差（不掩盖）
  诱导阻力按局部 CL 逐叶素施加：若展向 CL 呈椭圆分布，其积分恰等于整机诱导
  阻力；本模型 CL 展向变化平缓，属可控的一阶近似。

拆出理由：bird_fly.py 522 行超 R2 红线 500；本段是纯函数（无状态、不依赖
模块主流程），整体迁出后由 bird_fly 导入，判据与数值语义不变。
"""
import math

RHO_AIR = 1.225
G = 9.80665
DOWN_FRAC = 0.55
FOLD = 0.62
N_ELEM = 24
N_WING_SEG = 3
E_OSWALD = 0.9
CL_MAX = 1.5
CD0_PROFILE = 0.02


def _wing_points(shoulder, e_hat, n_hat, semi, eff):
    """由肩点、展向单位向量、拱起法向、半展长、有效展长比，解出腕/中/尖。

    三段等长 L=semi/3 恒定（骨长守恒），相邻段对称偏折 γ：
      弦长 = L(1+2cos γ) = semi·eff  →  cos γ = (3·eff−1)/2
    eff=1 → γ=0 完全伸展；eff<1 → 拱起折叠（鸟收翼）。
    竖直方向偏折互相抵消 → 弦严格沿展向，翼尖不产生伪竖直位移。
    """
    L = semi / N_WING_SEG
    cg = (N_WING_SEG * eff - 1.0) / 2.0
    cg = max(-1.0, min(1.0, cg))
    g = math.acos(cg)
    sg, cgv = math.sin(g), math.cos(g)
    d1 = cgv * e_hat + sg * n_hat
    d3 = cgv * e_hat - sg * n_hat
    wrist = shoulder + L * d1
    mid = wrist + L * e_hat
    tip = mid + L * d3
    return wrist, mid, tip


def stroke_angle_deg(b):
    """翼展相关的扑翼行程角（Nudds 2004：θ ≈ 67·b^(−0.24)，度）。

    唯一真源：bird_fly 的自检按此式断言，且巡航速度 U=f·A/St 也由它反解
    （A=b·sin(θ/2)）。此前误写成 Pennycuick 的 111−7b 拟合，与断言口径
    不一致导致 U 反解到 18.6 m/s，超出银鸥实测 10~13 m/s 区间——已纠正。
    """
    return max(20.0, min(150.0, 67.0 * b ** (-0.24)))


def flapping_angle(t, f, amp_deg=None, b=1.2, down_frac=DOWN_FRAC):
    """扑动角 φ(t)（弧度，+ 为上举）。

    下扑 φ: +A → −A（占 down_frac）；上举 φ: −A → +A（占 1−down_frac）。
    两段均用余弦，端点导数为 0 → 周期衔接处 C1 连续（无速度突跳）。
    """
    if amp_deg is None:
        amp_deg = stroke_angle_deg(b) / 2.0
    A = math.radians(amp_deg)
    T = 1.0 / f if f > 0 else 1.0
    p = (t / T) % 1.0
    if p < down_frac:
        return A * math.cos(math.pi * p / down_frac)
    q = (p - down_frac) / (1.0 - down_frac)
    return -A * math.cos(math.pi * q)



def is_downstroke(t, f, down_frac=DOWN_FRAC):
    """相位是否处于下扑段（dφ/dt<0）。"""
    T = 1.0 / f if f > 0 else 1.0
    p = (t / T) % 1.0
    return p < down_frac
def flapping_rate(t, f, amp_deg=None, b=1.2, down_frac=DOWN_FRAC):
    """dφ/dt（弧度/秒），解析导数，供叶素法求局部气流速度。"""
    if amp_deg is None:
        amp_deg = stroke_angle_deg(b) / 2.0
    A = math.radians(amp_deg)
    T = 1.0 / f if f > 0 else 1.0
    p = (t / T) % 1.0
    if p < down_frac:
        return -A * (math.pi / down_frac) * math.sin(math.pi * p / down_frac) / T
    q = (p - down_frac) / (1.0 - down_frac)
    return A * (math.pi / (1.0 - down_frac)) * math.sin(math.pi * q) / T
def fold_factor(t, f, fold=FOLD, down_frac=DOWN_FRAC):
    """翼折叠因子 eff ∈ [fold, 1]：下扑完全伸展(1)，上举屈曲回收(fold)。

    下扑段恒为 1（全展，翼面积最大以产生升力与推力）；上举段按
    1−(1−fold)·sin(π·q) 收缩，中点 q=0.5 取到极小值 fold，两端回到 1，
    与下扑段在相位衔接处连续（值连续，导数不要求——eff 只驱动几何，
    不进入气动速度项）。
    """
    T = 1.0 / f if f > 0 else 1.0
    p = (t / T) % 1.0
    if p < down_frac:
        return 1.0
    q = (p - down_frac) / (1.0 - down_frac)
    return 1.0 - (1.0 - fold) * math.sin(math.pi * q)


def sweep_angle(t, f, sweep_deg=12.0, down_frac=DOWN_FRAC):
    """仰角/扫掠角 θ(t)（弧度，+ 为前掠）。

    下扑段前掠（θ≥0，翼前移以“抓住”气流产生推力），上举段后掠
    （θ≤0，翼回收减小迎风面积与阻力）。两段均用 (1−cos)/2 半波：
    端点值与端点导数同为 0 → 周期衔接处 C1 连续，与扑动角同一原则。
    """
    A = math.radians(sweep_deg)
    T = 1.0 / f if f > 0 else 1.0
    p = (t / T) % 1.0
    if p < down_frac:
        return A * (1.0 - math.cos(2.0 * math.pi * p / down_frac)) / 2.0
    q = (p - down_frac) / (1.0 - down_frac)
    return -A * (1.0 - math.cos(2.0 * math.pi * q)) / 2.0



def _cl_coeff(alpha_deg):
    """鸟翼升力系数：薄翼位流 CL=2π·sinα，失速后饱和到 ±CL_MAX。

    **为什么弃用 Sane & Dickinson 2001 的果蝇翼拟合**：那组系数在 Re≈100 下
    测得，零升阻力系数约 0.39，L/D 峰值仅约 1.3。而鸟翼 L/D 实测 10~15
    （Pennycuick 2008）。扑翼要产生净推力，下扑段的 L/D 必须大于 U/|v_f|
    （本例约 1.6）——用果蝇系数恒为负推力，物理上不成立。
    """
    cl = 2.0 * math.pi * math.sin(math.radians(alpha_deg))
    return max(-CL_MAX, min(CL_MAX, cl))


def _cd_coeff(alpha_deg, AR):
    """鸟翼阻力系数 = 剖面阻力 + 诱导阻力（Pennycuick 2008《Modelling the
    flying bird》）。AR=b²/S 为展弦比，e 为 Oswald 效率因子。

    简化声明：诱导阻力按局部 CL 逐叶素施加。若展向 CL 呈椭圆分布，其积分
    恰等于整机诱导阻力；本模型 CL 展向变化平缓，属可控的一阶近似。
    """
    cl = _cl_coeff(alpha_deg)
    return CD0_PROFILE + cl * cl / (math.pi * AR * E_OSWALD)


def wing_aero(t, f, U, b, S, alpha0_deg, rho=RHO_AIR, down_frac=DOWN_FRAC,
              fold=FOLD, amp_deg=None, n_elem=N_ELEM):
    """准定常叶素法：对双侧翼沿展向积分，返回 (Fx, Fy)（牛）。

    每个叶素：
      局部竖直速度 v_f = s·cosφ·φ̇（扑动引起）
      合速度     u_r  = √(U² + v_f²)
      有效攻角   α_eff = α0 − atan2(v_f, U)     下扑 v_f<0 → α 增大
      升力 ⊥ 来流：方向 (−v_f, U)/u  → 下扑时其 x 分量 >0，即**推力**
      阻力 ∥ 来流：方向 (−U, −v_f)/u
    推力由下扑自然产生，不是写死的 —— 这是扑翼推进的机制本身。
    """
    semi = b / 2.0
    chord = S / b                      # 平均气动弦长
    AR = b * b / S                     # 展弦比（诱导阻力依赖它）
    if amp_deg is None:
        amp_deg = stroke_angle_deg(b) / 2.0
    phi = flapping_angle(t, f, amp_deg, b, down_frac)
    dphi = flapping_rate(t, f, amp_deg, b, down_frac)
    eff = fold_factor(t, f, fold, down_frac)
    span = semi * eff                  # 屈曲时受气流的有效展长缩短
    dr = span / n_elem
    fx = fy = 0.0
    for i in range(n_elem):
        s = (i + 0.5) * dr
        vf = s * math.cos(phi) * dphi
        u = math.hypot(U, vf)
        if u < 1e-12:
            continue
        a_eff = alpha0_deg - math.degrees(math.atan2(vf, U))
        q = 0.5 * rho * chord * u * u * dr
        dl = q * _cl_coeff(a_eff)
        dd = q * _cd_coeff(a_eff, AR)
        fx += (-dl * vf - dd * U) / u
        fy += (dl * U - dd * vf) / u
    return 2.0 * fx, 2.0 * fy          # 双侧翼


def trim_alpha(f, U, b, S, m, rho=RHO_AIR, lo=-5.0, hi=25.0, iters=60):
    """反解配平攻角 α0：使一个翼拍周期内的平均升力 = m·g（定常水平飞行）。

    二分：平均升力随 α0（在失速前）单调递增。
    """
    def mean_lift(a0):
        n = 48
        T = 1.0 / f if f > 0 else 1.0
        tot = 0.0
        for i in range(n):
            tot += wing_aero(i * T / n, f, U, b, S, a0, rho)[1]
        return tot / n
    target = m * G
    a, bb = lo, hi
    fa, fb = mean_lift(a) - target, mean_lift(bb) - target
    if fa * fb > 0:
        return bb if abs(fb) < abs(fa) else a     # 单调性不成立时取更接近端
    for _ in range(iters):
        mid = 0.5 * (a + bb)
        fm = mean_lift(mid) - target
        if abs(fm) < 1e-15:      # 浮点不做相等比较；1e-15 远小于升力量级(N)
            return mid
        if fa * fm < 0:
            bb, fb = mid, fm
        else:
            a, fa = mid, fm
    return 0.5 * (a + bb)
