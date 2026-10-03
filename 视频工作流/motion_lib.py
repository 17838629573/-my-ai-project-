"""运动原子函数集 Motion Atom Library
短名约定：族前缀 + 动作，全部 <=4 字母，见 NAMES
经搜索确定：MJ=Flash&Hogan最小急动度, FS=傅里叶阶次拟合, IP/SLIP/LIPM=倒立摆族
CP=Pratt捕获点, VRL=Verlet, AERO=UCSD CSE169空气动力
"""

import math

NAMES = """
mj    最小急动度五次多项式(点到点:坐/站/蹲/躺)  MJ(t,T,x0,x1)
fs    傅里叶级数(周期:走/跑关节角)             FS(t,coef,w)
ip    倒立摆角加速度                            IP(th,l)
slip  弹簧腿力(跑)                              SLIP(l,l0,k,c,dl)
lipm  线性倒立摆水平加速度                      LIPM(x,p,zc)
cp    捕获点XCoM(落脚点/稳定)                   CP(x,v,zc)
mos   稳定裕度(质检)                            MOS(xcom,cop)
verlet Verlet积分(布料/头发)                    VRL(x,xo,a,dt,damp)
aero  空气动力(风/衣摆)                         AERO(v,n,A,rho,cd,cl)
spr   弹簧力                                    SPR(d,L0,k)
dmp   阻尼力                                    DMP(v1,v2,kd)
pnoise Perlin风扰动                             PNOISE(t,seed)
add   附加层叠加(非对冲)                        ADD(base,*offs)
"""


def mj(t, T, x0, x1):
    """最小急动度 (Flash&Hogan 1985). 起止速度/加速度均为0, 天然平滑.
    用于坐/站/蹲/躺等点到点动作, 不可用于周期性动作."""
    if T <= 0:
        return x0
    tau = max(0.0, min(1.0, t / T))
    return x0 + (x1 - x0) * (10 * tau**3 - 15 * tau**4 + 6 * tau**5)


def fs(t, coef, w, n=None):
    """傅里叶级数. coef=[a0,a1,b1,a2,b2,...] 或 (a0,aj,bj 交替)
    周期动作关节角. 国内论文: 髋3阶/膝5阶/踝6阶, R^2>0.999"""
    n = n or (len(coef) - 1) // 2
    v = coef[0] / 2.0
    for j in range(1, n + 1):
        a = coef[2 * j - 1]
        b = coef[2 * j]
        v += a * math.cos(j * w * t) + b * math.sin(j * w * t)
    return v


def ip(th, l, g=9.8):
    """倒立摆角加速度. 小角度近似自然频率 w=sqrt(g/l), 人体步频落此附近(共振步态)"""
    return (g / l) * math.sin(th)


def w_ip(l, g=9.8):
    """倒立摆自然频率. 注意: l必须用等效摆长(~0.3m), 不是腿全长(0.864m).
    用全长算得32步/分, 与人体110-130不符; 用0.3m得~109步/分 — 已实测"""
    return math.sqrt(g / l)


L_EFF = 0.3   # 等效摆长(腿回转半径), 非腿全长. 经搜索+实测校准


def cadence_spm(l=L_EFF, g=9.8):
    """由等效摆长反推步频(步/分). 一步=半个振荡周期"""
    w = math.sqrt(g / l)
    return 60.0 / (math.pi / w)


def slip(l, l0, k, c=0.0, dl=0.0):
    """弹簧倒立摆腿力(跑). F = k(l0-l) - c*dl"""
    return k * (l0 - l) - c * dl


def lipm(x, p, zc, g=9.8):
    """线性倒立摆水平加速度. 假设重心高度恒定(实际波动2-5cm)"""
    return (g / zc) * (x - p)


def cp(x, v, zc, g=9.8):
    """捕获点 XCoM = x + v/w. 超出支撑多边形必须迈步才能不倒"""
    return x + v / math.sqrt(g / zc)


def mos(xcom, cop):
    """稳定裕度. 越小越不稳, 可用于自动质检每一帧是否物理站得住"""
    return abs(xcom - cop)


def verlet(x, xo, a, dt, damp=1.0):
    """Verlet积分. 速度隐含在(x-xo), 约束可直接改位置. 布料/头发/飘带"""
    return x + (x - xo) * damp + a * dt * dt


def aero(v, n, A, rho=1.225, cd=1.0, cl=0.5):
    """空气动力. F = 0.5*rho*A*[(cd-cl)(v.n)*v + cl*|v|^2*n]  (CS184/Wilson+14)
    注意|v|^2已含在(v.n)*v里, 不可再乘一次 — 初版多乘导致结果大50倍.
    v=相对风速向量, n=面法线(单位), A=该三角面面积. 按面施加才会抖"""
    v2 = sum(c * c for c in v)
    if v2 <= 0:
        return tuple(0.0 for _ in v)
    vn = sum(v[i] * n[i] for i in range(len(v)))
    return tuple(0.5 * rho * A * ((cd - cl) * vn * v[i] + cl * v2 * n[i])
                 for i in range(len(v)))


def spr(p1, p2, L0, k):
    """弹簧力向量(质点p1受p2). F = -k[(p1-p2) - L0*(p1-p2)/|p1-p2|]"""
    d = tuple(p1[i] - p2[i] for i in range(len(p1)))
    n = math.sqrt(sum(c * c for c in d))
    if n <= 1e-9:
        return tuple(0.0 for _ in d)
    return tuple(-k * (d[i] - L0 * d[i] / n) for i in range(len(d)))


def dmp(v1, v2, kd):
    """阻尼力. F = kd*(v2-v1)"""
    return tuple(kd * (v2[i] - v1[i]) for i in range(len(v1)))


def pnoise(t, seed=0, oct=3):
    """Perlin风格风扰动(简化value noise). 用于随机风场, 增强不可压缩随机性"""
    v = 0.0
    amp, freq = 1.0, 1.0
    tot = 0.0
    for o in range(oct):
        x = t * freq + seed * 17.13 + o * 5.7
        i = math.floor(x)
        f = x - i
        f = f * f * (3 - 2 * f)
        h = lambda k: math.sin(k * 12.9898 + seed * 78.233) * 43758.5453 % 1.0
        v += amp * (h(i) * (1 - f) + h(i + 1) * f)
        tot += amp
        amp *= 0.5
        freq *= 2.0
    return v / tot


def add(base, *offs):
    """附加层叠加(ADDITIVE, 非对冲). base=主运动, offs=局部偏移
    业界: 一个走路循环+附加偏移可产生数十种视觉变化, 可堆叠"""
    out = list(base) if hasattr(base, '__iter__') else [base]
    for o in offs:
        ov = list(o) if hasattr(o, '__iter__') else [o]
        for i in range(min(len(out), len(ov))):
            out[i] = out[i] + ov[i]
    return out


# ── 预置姿态系数 (经搜索: 国内论文拟合值, 单位=度, 量纲待校准) ──
# 髋3阶 / 膝5阶 / 踝6阶 是文献一致结论
HIP_FS = [56.08, 20.33, -7.278, 5.186, 1.583, -0.1338, 2.202]   # a0,a1,b1,a2,b2,a3,b3


def walk_hip(t, w=0.05884):
    """走路髋关节角(度). 系数来源: 下肢康复机器人论文, R^2≈1"""
    return fs(t, HIP_FS, w, n=3)


if __name__ == '__main__':
    print("=== 运动原子函数集 自检 ===")
    # MJ: 起止速度必须为0
    T = 1.0
    v0 = (mj(0.001, T, 0, 1) - mj(0.0, T, 0, 1)) / 0.001
    v1 = (mj(T, T, 0, 1) - mj(T - 0.001, T, 0, 1)) / 0.001
    print(f"MJ  端点速度 v0={v0:.4f} v1={v1:.4f}  (应≈0)")
    print(f"MJ  中点     {mj(T/2, T, 0, 1):.4f}     (应=0.5)")

    # FS 周期性
    a, b = fs(0.0, HIP_FS, 0.05884, 3), fs(2 * math.pi / 0.05884, HIP_FS, 0.05884, 3)
    print(f"FS  周期闭合 {a:.6f} vs {b:.6f} 差 {abs(a-b):.2e}")

    # IP 自然频率 vs 人体步频
    l = 0.864
    w = w_ip(l)
    print(f"IP  腿长{l}m 自然频率 {w:.3f} rad/s = {w*60/(2*math.pi):.1f} 步/分 (人体110-130)")

    # CP/MOS
    x, v, zc = 0.1, 1.2, 0.9
    print(f"CP  x={x} v={v} zc={zc} -> XCoM={cp(x,v,zc):.4f}  MoS={mos(cp(x,v,zc),0.0):.4f}")

    # Verlet 自由落体
    x, xo, dt = 0.0, 0.0, 1/60
    for _ in range(60):
        x, xo = verlet(x, xo, -9.8, dt), x
    print(f"VRL 1秒自由落体 {-x:.4f} m  (理论4.9)")

    # AERO 迎风
    f = aero((0, 0, 10), (0, 0, 1), 0.01)
    print(f"AERO 10m/s迎风1cm² {tuple(round(c,4) for c in f)} N")

    # ADD 叠加
    print(f"ADD base+off -> {add([1.0,2.0],[0.1,-0.2])}")
