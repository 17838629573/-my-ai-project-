# 契约: proc/motion/phenom
#   一句话: 常见物理现象能力族（leaf_fall/fracture/water_jet/newton_cradle/turntable）
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""常见物理现象包：统一导出 + 自检"""
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

import math
import numpy as np

from ..beat import capability

G = 9.8


from .leaf import leaf_fall_sim, _leaf_load, _leaf_classify
from .fracture import fracture_sim
from .water import water_jet_sim
from .cradle import newton_cradle_sim
from .turntable import turntable_sim

__all__ = ["leaf_fall_sim", "fracture_sim", "water_jet_sim",
           "newton_cradle_sim", "turntable_sim", "self_check"]


def self_check():
    """自检：五现象各自的物理不变量（数据表化，执行器统一跑）。"""
    from base.assertrun import Checker
    c = Checker("phenom")
    for _probe in (_chk_leaf, _chk_frac, _chk_water, _chk_cradle, _chk_turn):
        _probe(c)
    return c.report()


def _chk_leaf(c):
    """树叶飘落探针：flutter 涌现 + tumbling 给定自转 + 终端速度合理。"""
    mode, v_term, n_swings, dtheta, traj = leaf_fall_sim()
    v_free = math.sqrt(2 * G * 2.0)
    c.chk("leaf 终端速度存在且远小于自由落体（阻力起作用）",
          v_term > 0.0 and v_term < 0.5 * v_free,
          "v_term=%.4f, v_free=%.4f" % (v_term, v_free))
    c.chk("leaf 产生水平漂移（非竖直直线下落）",
          abs(traj[-1][0] - traj[0][0]) > 1e-4,
          "dx=%.5f" % abs(traj[-1][0] - traj[0][0]))
    # flutter：从静止涌现，表现为左右摆动、净转角远小于 2π
    c.chk("leaf 静止释放呈 flutter（摆动滑翔，净转角 < 2π）",
          mode == "flutter" and n_swings >= 2 and abs(dtheta) < 2.0 * math.pi,
          "mode=%s swings=%d dtheta=%.3f" % (mode, n_swings, dtheta))
    # tumbling：给定自转角速度，净转角 > 2π，且终端速度仍在合理区间
    mt, vt, _, dt_t, _ = leaf_fall_sim(spin=3.0, T=6.0)
    c.chk("leaf 给定自转呈 tumbling（净转角 > 2π）",
          mt == "tumbling" and abs(dt_t) > 2.0 * math.pi,
          "mode=%s dtheta=%.3f" % (mt, dt_t))
    c.chk("leaf tumbling 终端速度仍在 0.05~1.5 m/s",
          0.05 < vt < 1.5, "v_term=%.4f" % vt)
    c.note("leaf 默认(flutter) mode=%s v_term=%.4f m/s swings=%d dtheta=%.3f rad"
           % (mode, v_term, n_swings, dtheta))
    c.note("leaf tumbling(spin=3) v_term=%.4f m/s dtheta=%.3f rad" % (vt, dt_t))
    c.note("已知限制：tumbling 为给定自转角速度，自持翻滚的涌现未实现"
           "（唯象双稳态模型在本求解器下不稳定，不冒充涌现）")


def _chk_frac(c):
    """砖墙碎裂探针：静置稳定 + 撞击断键 + 真裂成多块 + 球减速。"""
    n_broken, n_frag, max_disp, mom_err, stable_disp, v_end = fracture_sim()
    c.chk("fracture 未受撞时墙自身稳定", stable_disp < 1e-3,
          "settle_disp=%.6f" % stable_disp)
    c.chk("fracture 撞击后 bond 断裂", n_broken > 0, "n_broken=%d" % n_broken)
    c.chk("fracture 裂成多个连通碎块", n_frag > 1, "n_frag=%d" % n_frag)
    c.chk("fracture 球撞击后减速（动量传给墙）",
          v_end < 10.0, "v_ball_end=%.4f < v0=10.0" % v_end)
    c.chk("fracture 碎块位移有界（未数值爆炸）", 0.0 < max_disp < 1.0,
          "max_disp=%.4f" % max_disp)
    c.note("fracture n_broken=%d n_frag=%d max_disp=%.4f v_ball_end=%+.4f"
           % (n_broken, n_frag, max_disp, v_end))
    c.note("已知限制：PBD 位置投影本身不严格守恒动量，mom_err 仅作参考"
           "（实测 %.3f），不作判据" % mom_err)


def _chk_water(c):
    """水流探针：不穿透地面 + 铺展 + 粒子不丢失。"""
    min_y, spread, rho_rel, n_alive = water_jet_sim()
    c.chk("water 不穿透地面", min_y >= -1e-9, "min_y=%.6f" % min_y)
    c.chk("water 冲击后横向铺展", spread > 1.0, "spread=%.3f" % spread)
    c.chk("water 粒子无丢失/无NaN", n_alive == 180,
          "n_alive=%d" % n_alive)
    c.chk("water 密度接近静息密度（不可压缩约束成立）", rho_rel < 0.10,
          "rho_rel=%.4f" % rho_rel)
    c.note("water min_y=%.6f spread=%.3f rho_rel=%.4f n_alive=%d"
           % (min_y, spread, rho_rel, n_alive))


def _chk_cradle(c):
    """牛顿摆探针：末球弹出 + 中间球静止（首次碰撞窗口内）+ 能量守恒。"""
    v_last, th_mid, th_last, mom_err, en_err = newton_cradle_sim()
    th0 = 0.60
    v_in = math.sqrt(2.0 * G * 0.50 * (1.0 - math.cos(th0)))
    c.chk("cradle 末球弹出（速度接近首球入射速度）",
          abs(v_last - v_in) < 0.15 * v_in,
          "v_last=%.4f v_in=%.4f" % (v_last, v_in))
    c.chk("cradle 中间球几乎不动（首次碰撞后 0.25s 内角位移≈0）",
          th_mid < 0.05 * th0, "th_mid=%.5f rad < %.4f" % (th_mid, 0.05 * th0))
    c.chk("cradle 末球被弹出到接近初始摆角",
          th_last > 0.5 * th0, "th_last=%.4f > %.4f" % (th_last, 0.5 * th0))
    c.chk("cradle 能量近似守恒", en_err < 0.05, "en_err=%.5f" % en_err)
    c.note("cradle v_last=%.4f th_mid=%.5f th_last=%.4f en_err=%.5f"
           % (v_last, th_mid, th_last, en_err))
    c.note("口径说明：中间球静止只在首次碰撞后短窗口内成立；末球摆回二次"
           "撞击后中间球必然动起来，这是真实牛顿摆行为")


def _chk_turn(c):
    """转台探针：离心超标后滑移且被甩出。"""
    r, slip, lat = turntable_sim()
    c.chk("turntable 离心超静摩擦后滑移", slip is True, "slip=%s" % slip)
    c.chk("turntable 物块被甩向外侧", r > 0.10, "r_end=%.4f" % r)
    c.chk("turntable 科氏产生横向偏转", lat > 1e-6, "lateral=%.6f" % lat)
    # 对照：转速极低时不滑移
    r2, slip2, _ = turntable_sim(om_p=0.1)
    c.chk("turntable 低速不滑移（自证判据有效）", slip2 is False,
          "slip=%s" % slip2)
    c.note("turntable r_end=%.4f lateral=%.6f (低速 r=%.4f slip=%s)"
           % (r, lat, r2, slip2))
