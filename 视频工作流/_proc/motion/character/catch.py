"""接球（B11 / D22 通用）

契约: motion/character/catch
  输入: t∈[0,1] 全局进度; 来球初态 P0,V0(米)
  输出: 关节字典(u,v,w 归一化身高); 球心(米)
  依赖: numpy motion.character.leg motion.character.ball motion.character.throw ..beat
  被依赖: tests/run_all
  约束: 手走最小急动度轨迹到预测拦截点 IP; 接触瞬间球停并随手;
        不采用"匹配球速"策略(球受重力加速, 该策略下手速单调增, 与实测 PMV 不符)
公式出处:
  · 预测策略: 先向预估拦截点 IP 做预编程移动, 接触前有修正子运动;
    实测存在 PMV(point of minimal velocity)
    (Minimum Jerk for Human Catching Movements in 3D, TUM mediatum 1285786)
  · 最小急动度 5 次多项式 x(u)=x0+(x1-x0)(10u³-15u⁴+6u⁵) (Flash & Hogan 1985)
"""
import os as _os, sys as _sys
if __package__ in (None, ""):
    _d = _os.path.dirname(_os.path.abspath(__file__))
    while _d != _os.path.dirname(_d) and _os.path.basename(_d) != "_proc":
        _d = _os.path.dirname(_d)
    for _p in (_os.path.dirname(_d), _d):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    __package__ = _os.path.relpath(
        _os.path.dirname(_os.path.abspath(__file__)), _d).replace(_os.sep, ".")

import numpy as np

from .body.leg import two_bone_ik
from . import ball
from .throw import (H_M, HIP_STAND, R_TRUNK, _AU, _AF, _GRIP,
                    _S, _ss, _stance, _arm_left)
from ..beat import capability

G = ball.G
T_TOTAL = 1.20
T_MOVE = 0.62
F_CATCH = T_MOVE / T_TOTAL
P0 = np.array([4.20, 1.10])     # 来球初始位置(米)
V0 = np.array([-6.20, 3.40])    # 来球初速(米每秒)
_SH_Y = HIP_STAND + R_TRUNK - 0.02
_A0 = np.array([-0.02, -0.12])  # 手起点(胸前, 归一化身高)
_BACK = np.array([-0.03, -0.16])


def ball_flight(t_phys):
    """来球(米): 解析抛物线, t_phys 单位秒"""
    t = np.atleast_1d(np.asarray(t_phys, float))
    return np.stack([P0[0] + V0[0] * t,
                     P0[1] + V0[1] * t - 0.5 * G * t * t], axis=1)


def intercept_point():
    """预测拦截点 IP(米): 球在 T_MOVE 时刻的位置(预测策略)"""
    return ball_flight(T_MOVE)[0]


def _mj(u):
    """最小急动度 5 次多项式 (Flash & Hogan 1985)"""
    u = min(1.0, max(0.0, float(u)))
    return 10.0 * u ** 3 - 15.0 * u ** 4 + 6.0 * u ** 5


def _hand_rel(t):
    """手相对肩(归一化身高): 最小急动度到 IP, 接触后缓冲回收"""
    ip = intercept_point()
    ip_rel = np.array([ip[0] / H_M, ip[1] / H_M - _SH_Y])
    if t < F_CATCH:
        return _A0 + (ip_rel - _A0) * _mj(t / F_CATCH)
    u = _ss((t - F_CATCH) / (1.0 - F_CATCH))
    return ip_rel + (_BACK - ip_rel) * u


def _arm_chain(t):
    """(肩, 肘, 腕) 归一化身高: 手心目标给定, 反解腕位

    手心 = 腕 + 抓握偏移(沿前臂方向), 而拦截点 IP 是手心应到的位置,
    故腕 = IP - 抓握偏移; 抓握方向依赖肘, 迭代 3 次收敛(误差二阶小)
    """
    t = min(1.0, max(0.0, float(t)))
    sh = np.array([0.0, _SH_Y])
    tgt = sh + _hand_rel(t)
    wr = tgt.copy()
    for _ in range(3):
        el = two_bone_ik(sh, wr, _AU, _AF, bend=(1.0, 0.0))
        d = wr - el
        n = max(np.linalg.norm(d), 1e-12)
        wr = tgt - (_GRIP / n) * d
    el = two_bone_ik(sh, wr, _AU, _AF, bend=(1.0, 0.0))
    return sh, el, wr


def hand_center(t):
    """手心(米): 等于 _hand_rel 所给目标(拦截点/回收位), 精确无残差"""
    t = min(1.0, max(0.0, float(t)))
    sh = np.array([0.0, _SH_Y])
    return (sh + _hand_rel(t)) * H_M


def ball_center(t):
    """球心(米): 接触前按弹道, 接触后停住并随手"""
    t = min(1.0, max(0.0, float(t)))
    tp = t * T_TOTAL
    if tp <= T_MOVE:
        return ball_flight(tp)[0]
    return hand_center(t)


def catch(t):
    """接球: 返回关节字典(归一化身高)"""
    t = min(1.0, max(0.0, float(t)))
    out = _stance(t * 0.3)
    sh, el, wr = _arm_left(t * 0.3)
    out["sh_l"] = _S(sh[0], sh[1], 0.08)
    out["elb_l"] = _S(el[0], el[1], 0.08)
    out["wri_l"] = _S(wr[0], wr[1], 0.08)
    sr, el_r, wr_r = _arm_chain(t)
    out["sh_r"] = _S(sr[0], sr[1], -0.08)
    out["elb_r"] = _S(el_r[0], el_r[1], -0.08)
    out["wri_r"] = _S(wr_r[0], wr_r[1], -0.08)
    return out


def self_check():
    r = []
    N = 400
    mx = 0.0
    for i in range(N + 1):
        J = catch(i / N)
        sh, el, w = J["sh_r"][:2], J["elb_r"][:2], J["wri_r"][:2]
        mx = max(mx, abs(np.linalg.norm(el - sh) - _AU),
                 abs(np.linalg.norm(w - el) - _AF))
    r.append(("骨长守恒", mx < 1e-9, "max=%.2e" % mx))
    ip = intercept_point()
    ip_rel = np.array([ip[0] / H_M, ip[1] / H_M - _SH_Y])
    rr = float(np.linalg.norm(ip_rel))
    r.append(("拦截点在臂展内", rr <= _AU + _AF + _GRIP,
              "|rel|=%.4f vs %.4f" % (rr, _AU + _AF + _GRIP)))
    d = np.linalg.norm(hand_center(F_CATCH) - ball_flight(T_MOVE)[0])
    r.append(("接触瞬间手球重合", d < 1e-6, "dist=%.2e" % d))
    after = [np.linalg.norm(ball_center(t) - hand_center(t))
             for t in (F_CATCH + 0.1, F_CATCH + 0.25, 0.95)]
    r.append(("接触后球停并随手", max(after) < 1e-9, "max=%.2e" % max(after)))
    # 最小急动度: 速度单峰且端点→0(否定"匹配球速"的单调增)
    sp = [np.linalg.norm(hand_center(F_CATCH * k / 20.0)
                         - hand_center(F_CATCH * (k - 1) / 20.0))
          for k in range(1, 21)]
    pk = sp.index(max(sp))
    r.append(("速度单峰(最小急动度)", 0 < pk < len(sp) - 1
              and sp[-1] < 0.35 * max(sp),
              "峰在第%d/20 段, 末/峰=%.3f" % (pk + 1, sp[-1] / max(sp))))
    dm = max(np.linalg.norm(catch((i + 1) / N)["wri_r"][:2]
                            - catch(i / N)["wri_r"][:2]) for i in range(N))
    r.append(("无跳变", dm * H_M < 0.10, "%.4f m/frame" % (dm * H_M)))
    ok = True
    for n_, ok_, s in r:
        print(("PASS " if ok_ else "FAIL ") + n_ + "  " + s)
        ok = ok and ok_
    return ok


@capability("catch", source="预测拦截+最小急动度5次多项式(Flash&Hogan 1985; TUM Minimum Jerk for Human Catching Movements in 3D)",
            group="prop")
def _cap_catch(u, p):
    return catch(u)


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
