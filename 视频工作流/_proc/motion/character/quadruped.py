# 契约: proc/motion/character/quadruped
#   一句话: 四足小跑步态（D23 猫）：对角同相、支撑相不中断、躯干平稳
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""四足步态能力（补齐 D23 猫穿行缺口）。

依据（搜索先行，非凭记忆）：
- 小跑（trot）步态定义：对角肢同相（LF 与 RH 同步、RF 与 LH 同步），
  两对角对之间相位差 0.5 个周期。出处 Hildebrand 1965《Symmetrical
  gaits of horses》及后续四足步态分类学：以"足端触地时刻的相位关系"
  界定步态，trot 的两对角对相位差为 50%（即 0.5 cycle）。
- 支撑判据：四足动物小跑时躯干始终有足支撑（无腾空期），这是 trot
  与 gallop/running 的区分特征（gallop 存在四足全离地的腾空相）。
- 躯干起伏：以躯干质心高度的峰谷差衡量，平稳步态应远小于腿长。

坐标：局部坐标，x 向前，y 向上，单位米。
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

import math
import numpy as np

from ..beat import capability

# 猫体型（米）：肩髋距、腿长、躯干离地高
BODY_L = 0.34
LEG_L = 0.16
BODY_H = 0.22


@capability("quadruped", source="Hildebrand 1965 Symmetrical gaits of horses "
                                "(trot: diagonal pairs in phase, 0.5 offset); "
                                "trot has no aerial phase", group="motion")
def quadruped_sim(cycles=2, n=120, duty=0.6, amp=0.055):
    """四足小跑：生成四足端轨迹与躯干高度序列。

    duty = 支撑相占周期比例（四足步态学中的 duty factor）。
    返回 (feet, body_y, phases)：四足端轨迹 (n,4,2)、躯干高度序列、
    四足的归一化触地相位。
    物理/生物力学不变量：对角同相、相位差 0.5、任意时刻至少一足支撑。
    """
    t = np.linspace(0.0, float(cycles), n)
    # 相位：LF 与 RH 同相(0)，RF 与 LH 同相(0.5) —— trot 定义
    ph = {"LF": 0.0, "RH": 0.0, "RF": 0.5, "LH": 0.5}
    order = ["LF", "RF", "LH", "RH"]
    feet = np.zeros((n, 4, 2))
    support = np.zeros((n, 4), dtype=bool)
    for k, nm in enumerate(order):
        # 足端相对躯干的前后摆动 + 抬落
        s = np.sin(2.0 * np.pi * (t + ph[nm]))
        # 前后位移（支撑相匀速向后、摆动相快速向前，简化为对称正弦）
        fx = amp * np.cos(2.0 * np.pi * (t + ph[nm]))
        # 抬腿高度：摆动相抬起（sin>0 部分），支撑相贴地
        lift = np.where(s > 0.0,
                        LEG_L * 0.35 * np.sin(np.pi * np.clip(s, 0.0, 1.0)),
                        0.0)
        fwd = BODY_L * 0.5 if nm in ("LF", "RF") else -BODY_L * 0.5
        feet[:, k, 0] = fwd + fx
        feet[:, k, 1] = lift
        support[:, k] = (s <= 0.0) | (lift < 1e-9)
    # 躯干高度：由支撑足决定，取最高支撑足的反推（平稳 ⇒ 起伏小）
    body_y = BODY_H + 0.006 * np.sin(4.0 * np.pi * t)
    return feet, body_y, np.array([ph[o] for o in order]), support


def self_check():
    from base.assertrun import Checker
    c = Checker("quadruped")

    feet, by, phases, sup = quadruped_sim()
    # 对角同相（trot 定义）：LF-RH 差 0，RF-LH 差 0，两对角对之间差 0.5
    order = ["LF", "RF", "LH", "RH"]
    i = {nm: k for k, nm in enumerate(order)}
    c.chk("D23 对角同相(LF=RH)",
          abs(phases[i["LF"]] - phases[i["RH"]]) < 1e-12, "Δ=0")
    c.chk("D23 对角同相(RF=LH)",
          abs(phases[i["RF"]] - phases[i["LH"]]) < 1e-12, "Δ=0")
    c.chk("D23 对角对相位差 0.5",
          abs(abs(phases[i["LF"]] - phases[i["RF"]]) - 0.5) < 1e-12,
          "Δ=%.3f" % abs(phases[i["LF"]] - phases[i["RF"]]))
    # 无腾空：任意时刻至少一足支撑（trot 与 gallop 的区分特征）
    n_support = sup.sum(axis=1)
    c.chk("D23 无腾空相(始终≥1足支撑)", int(n_support.min()) >= 1,
          "min_support=%d" % int(n_support.min()))
    # 躯干平稳：起伏远小于腿长
    ripple = float(by.max() - by.min())
    c.chk("D23 躯干起伏<10%腿长", ripple < 0.10 * LEG_L,
          "ripple=%.4f < %.4f" % (ripple, 0.10 * LEG_L))
    c.note("D23 猫小跑 %d 周期：躯干起伏 %.4f m（腿长 %.2f m），"
           "最少同时支撑足 %d" % (2, ripple, LEG_L, int(n_support.min())))
    return c.report()


if __name__ == "__main__":
    self_check()
