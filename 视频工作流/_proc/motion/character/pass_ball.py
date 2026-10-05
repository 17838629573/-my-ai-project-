"""D22 两人传球：A 投 → 飞行 → B 接 → 缓冲 → B 投回 → A 接

契约: motion/character/pass_ball
  输入: 全局时间 t_phys（秒，∈ [0, T_TOTAL]）
  输出: pose_A(t)/pose_B(t) 关节字典（本地归一化身高）
        ball_world(t) 球心世界坐标（米，x 横向 / y 离地）
        XC_A/XC_B/YAW_A/YAW_B 两人站位与朝向
  依赖: numpy .ball .throw .catch
  被依赖: tests/cases_crowd (D22)
  约束: 球飞行段为解析抛物线，不做数值积分；
        接球点取 catch.intercept_point()，手与球同时到达（tau 耦合），
        故球-手在接触时刻严格重合，不需要额外容差；
        两人间距、飞行时间、缓冲时长必须有出处

为什么单独成模块
  throw / catch 都是单人本地坐标，球轨迹在 catch 内是硬编码的来球。
  传球需要"一条被两人共享的球"：A 的出手点是 B 来球的起点，
  故世界坐标与时序必须由上层编排，不能塞进任一单人模块。

公式出处:
  · 两人间距 3.5 m：篮球双手胸前传球教学，两人一组相距 3~5 m
  · 手与球同时到达（tau 时间-接触信息）：
    Peper, Bootsma, Mestre & Bakker (1994) "Catching balls: How to get
    the hand to the right place at the right time"
  · 接球策略（预测 vs 反应）取决于反应时间与任务时长之比：
    Belousov, Giese & Neumann (NIPS 2016) "Catching heuristics are
    optimal control policies"
  · 触球后顺势屈肘后引缓冲：篮球双手胸前传球教学（接球缓冲）
"""
import numpy as np

from . import ball
from . import throw as TH
from . import catch as CT
from ..beat import capability

G = ball.G

# ---- 站位（依据: 篮球传球教学 两人一组 3~5 m）----
D_APART = 3.5
XC_A = -D_APART / 2.0
XC_B = +D_APART / 2.0
YAW_A = 90.0        # 面朝 +X（本地前向 u → 世界 +X）
YAW_B = -90.0       # 面朝 -X（本地前向 u → 世界 -X）

# ---- 时序 ----
T_THROW = TH.T_TOTAL     # 1.60 投掷动作时长
T_CATCH = CT.T_TOTAL     # 1.20 接球动作时长
F_REL = TH.F_REL         # 0.50 投掷释放点（归一化）
T_MOVE = CT.T_MOVE       # 0.62 伸手到拦截点所需时间
# 飞行时间由球速决定（因果：先定球速，再算飞行时间），而非由伸手时间反推
V_PASS = 5.3             # 胸前传球球速 m/s（Shimizu et al. 轮椅篮球实测
                         #   有经验组 5.3+-0.5 m/s）

# 飞行时间 = 水平位移 / 球速：距离变，飞行时间自动变，球速恒定 5.3 m/s
_XA0 = XC_A + TH.hand_center(F_REL)[0]
_XB0 = XC_B + CT.intercept_point()[0]
T_FLY = abs(_XB0 - _XA0) / V_PASS
# 接球者须在球到达前完成伸手（预判启动），而非球出手才开始
assert T_MOVE <= T_FLY, "伸手慢于球到，来不及接"
T_BUF = 0.30             # 触球后缓冲（篮球教学：顺势屈肘后引）

T_REL_A = F_REL * T_THROW              # 0.80  A 出手
T_ARRIVE1 = T_REL_A + T_FLY            # 球到 B
# B 提前 T_MOVE 启动，使「手到位」与「球到达」同一时刻（对齐因果）
T_B_CATCH0 = T_ARRIVE1 - T_MOVE
T_B_CATCH1 = T_B_CATCH0 + T_CATCH      # 2.00  B 接球动作结束
T_B_THROW0 = T_B_CATCH1 + T_BUF        # 2.30  B 开始投回
T_REL_B = T_B_THROW0 + F_REL * T_THROW  # 3.10 B 出手
T_ARRIVE2 = T_REL_B + T_FLY            # 3.72  球到 A
T_A_CATCH0 = T_ARRIVE2 - T_MOVE        # 3.10  A 开始伸手
T_A_CATCH1 = T_A_CATCH0 + T_CATCH      # 4.30
T_TOTAL = T_A_CATCH1


def _wx_a(p):
    """A 的本地(米) → 世界(米)：yaw=90，本地前向 → 世界 +X"""
    return np.array([XC_A + float(p[0]), float(p[1])])


def _wx_b(p):
    """B 的本地(米) → 世界(米)：yaw=-90，本地前向 → 世界 -X"""
    return np.array([XC_B - float(p[0]), float(p[1])])


def _solve(p0, tgt, T):
    """反解初速：使球在 T 秒后精确到达 tgt（解析抛物线）"""
    p0 = np.asarray(p0, float)
    tgt = np.asarray(tgt, float)
    v = np.array([(tgt[0] - p0[0]) / T,
                  (tgt[1] - p0[1] + 0.5 * G * T * T) / T])
    return p0, v


_P1, _V1 = _solve(_wx_a(TH.hand_center(F_REL)),
                  _wx_b(CT.intercept_point()), T_FLY)
_P2, _V2 = _solve(_wx_b(TH.hand_center(F_REL)),
                  _wx_a(CT.intercept_point()), T_FLY)


def _flat(x):
    return np.asarray(x, float).reshape(2)


def flight1(tt):
    """第一程（A→B）：tt 为出手后秒数"""
    return _flat(ball.flight(_P1, _V1, tt))


def flight2(tt):
    """第二程（B→A）：tt 为出手后秒数"""
    return _flat(ball.flight(_P2, _V2, tt))


def release_vel1():
    return _V1.copy()


def release_vel2():
    return _V2.copy()


# ------------------------------------------------------------------ 姿态
def pose_A(t):
    """A（左侧，面朝 +X）：投 → 站立等待 → 接"""
    t = float(t)
    if t <= T_THROW:
        return TH.throw(min(1.0, max(0.0, t / T_THROW)))
    if t < T_A_CATCH0:
        return TH.throw(1.0)
    u = (t - T_A_CATCH0) / T_CATCH
    return CT.catch(min(1.0, max(0.0, u)))


def pose_B(t):
    """B（右侧，面朝 -X）：站立等待 → 接 → 缓冲 → 投回"""
    t = float(t)
    if t < T_B_CATCH0:
        return CT.catch(0.0)
    if t <= T_B_CATCH1:
        return CT.catch(min(1.0, max(0.0, (t - T_B_CATCH0) / T_CATCH)))
    if t < T_B_THROW0:
        return CT.catch(1.0)
    if t <= T_B_THROW0 + T_THROW:
        return TH.throw(min(1.0, max(0.0, (t - T_B_THROW0) / T_THROW)))
    return TH.throw(1.0)


def held_by(t):
    """球此刻在谁手里（None 表示飞行中）"""
    t = float(t)
    if t <= T_REL_A:
        return "A"
    if t <= T_ARRIVE1:
        return None
    if t <= T_REL_B:
        return "B"
    if t <= T_ARRIVE2:
        return None
    return "A"


def hand_world(t):
    """持球者的手心世界坐标（米）"""
    t = float(t)
    if t <= T_REL_A:
        return _wx_a(TH.hand_center(t / T_THROW))
    if t <= T_B_CATCH1:
        return _wx_b(CT.hand_center((t - T_B_CATCH0) / T_CATCH))
    if t <= T_B_THROW0:
        return _wx_b(CT.hand_center(1.0))
    if t <= T_REL_B:
        return _wx_b(TH.hand_center((t - T_B_THROW0) / T_THROW))
    if t <= T_ARRIVE2:
        return _wx_a(CT.hand_center((t - T_A_CATCH0) / T_CATCH))
    return _wx_a(CT.hand_center(min(1.0, (t - T_A_CATCH0) / T_CATCH)))


def ball_world(t):
    """球心世界坐标（米）"""
    t = float(t)
    if t <= T_REL_A:                       # A 持球
        return _wx_a(TH.hand_center(t / T_THROW))
    if t <= T_ARRIVE1:                     # 飞行 1
        return flight1(t - T_REL_A)
    if t <= T_B_CATCH1:                    # B 接住并回收
        return _wx_b(CT.hand_center((t - T_B_CATCH0) / T_CATCH))
    if t <= T_B_THROW0:                    # B 缓冲持球
        return _wx_b(CT.hand_center(1.0))
    if t <= T_REL_B:                       # B 投掷持球
        return _wx_b(TH.hand_center((t - T_B_THROW0) / T_THROW))
    if t <= T_ARRIVE2:                     # 飞行 2
        return flight2(t - T_REL_B)
    u = min(1.0, (t - T_A_CATCH0) / T_CATCH)
    return _wx_a(CT.hand_center(u))        # A 接住


@capability("pass_ball", "Peper et al. 1994 tau 耦合; "
            "Belousov et al. NIPS 2016 接球策略; 篮球双手胸前传球教学",
            group="interaction")
def _vx_err(ts, lo, hi):
    """飞行段水平速度相对极差：分段量（两程方向相反，混量会跨正负号虚高）。"""
    vs = [(ball_world(b)[0] - ball_world(a)[0]) / (b - a)
          for a, b in zip(ts[:-1], ts[1:]) if lo <= a and b <= hi]
    if len(vs) < 3:
        return 9.9
    return (max(vs) - min(vs)) / max(abs(float(np.mean(vs))), 1e-9)


def _chk_time(c):
    """时序单调且覆盖全程。"""
    seq = [0.0, T_REL_A, T_ARRIVE1, T_B_CATCH1, T_B_THROW0,
           T_REL_B, T_ARRIVE2, T_TOTAL]
    c.chk("时序单调递增", all(seq[i] < seq[i + 1] for i in range(len(seq) - 1)))


def _chk_ball(c, ts):
    """球：接触重合、水平速度守恒、不脱手、不落地。"""
    # 球-手在接触时刻严格重合（tau 耦合的结果，不是容差凑出来的）
    d1 = float(np.linalg.norm(ball_world(T_ARRIVE1) - hand_world(T_ARRIVE1)))
    d2 = float(np.linalg.norm(ball_world(T_ARRIVE2) - hand_world(T_ARRIVE2)))
    c.chk("接触1 球手重合", d1 < 1e-9, "dist=%.3e" % d1)
    c.chk("接触2 球手重合", d2 < 1e-9, "dist=%.3e" % d2)
    # 飞行段水平速度守恒（水平方向无外力）
    vx_err = max(_vx_err(ts, T_REL_A, T_ARRIVE1), _vx_err(ts, T_REL_B, T_ARRIVE2))
    c.chk("飞行水平速度守恒", vx_err < 1e-6, "rel=%.3e" % vx_err)
    held = 0.0
    for t in ts:
        if held_by(t) is not None:
            held = max(held, float(np.linalg.norm(ball_world(t) - hand_world(t))))
    c.chk("持球段不脱手", held < 1e-9, "max=%.3e" % held)
    ymin = min(ball_world(t)[1] for t in ts)
    c.chk("球不落地", ymin > ball.R_BALL, "min y=%.4f m" % ymin)


def _chk_people(c):
    """人：间距、臂展、出手速度。"""
    c.chk("两人间距", abs((XC_B - XC_A) - D_APART) < 1e-12,
          "%.4f" % (XC_B - XC_A))
    from .proportions import arm_reach
    sh = np.array([0.0, CT._SH_Y]) * CT.H_M
    reach = float(arm_reach(sh, np.asarray(CT.intercept_point()), CT.H_M))
    c.chk("拦截点在臂展内", reach < 0.40, "%.4f" % reach)
    # 出手速度合理（< 12 m/s，超出即编排有误）
    sp = max(float(np.linalg.norm(_V1)), float(np.linalg.norm(_V2)))
    c.chk("出手速度合理", sp < 12.0, "%.3f m/s" % sp)


def self_check():
    """对传自检：判据不变，断言交统一执行器。"""
    from base.assertrun import Checker
    c = Checker("pass_ball")
    ts = np.linspace(0.0, T_TOTAL, 241)
    _chk_time(c)
    _chk_ball(c, ts)
    _chk_people(c)
    return c.report()
