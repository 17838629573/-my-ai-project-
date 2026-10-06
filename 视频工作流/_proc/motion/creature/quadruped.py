# 契约: proc/motion/character/quadruped
#   一句话: 四足步态——Hildebrand 占空比β+四足相位表参数化，支撑相足端零滑移
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""四足步态能力：步态表参数化（D23 猫穿行，并覆盖六种步态）。

依据（搜索先行，非凭记忆）：
- Hildebrand 1965《Symmetrical gaits of horses》：以占空比（duty factor
  β = 单足支撑相占周期比例）与"足端触地时刻的相位关系"界定步态。
  对称步态可用 (D, Φlat) 描述：walk D=0.75/Φlat=0.25，trot D=0.5/Φlat=0.5，
  pace D=0.5/Φlat=0（出处：Hildebrand 步态公式与 McGhee 推广）。
- 四足步态相位表（顺序 LF/RF/LH/RH，单位为周期比例）：
    crawl  β=0.80  φ=(0, 0.50, 0.75, 0.25)   慢速四拍
    walk   β=0.75  φ=(0, 0.25, 0.50, 0.75)   四拍依次
    trot   β=0.50  φ=(0, 0.50, 0.50, 0.00)   对角成对
    pace   β=0.50  φ=(0, 0.50, 0.00, 0.50)   同侧成对
    bound  β=0.40  φ=(0, 0.00, 0.50, 0.50)   前后成对
    gallop β=0.35  φ=(0, 0.10, 0.50, 0.60)   四拍不等间隔（transverse）
  出处：CPG 相位引导步态过渡（arXiv:2201.00206 Table I）给出
  Trot [0,π,π,0] / Pacing [0,π,0,π] / Bounding [0,0,π,π] / Walk
  [0,π/2,π,3π/2]，按 LF,RF,LH,RH 顺序与上表一一对应；
  oxiphysics_rigid 的 GaitPattern 枚举给出同构的 duty_factor + phase_offsets 表。
- 步幅-速度自洽（本模块的核心不变量）：支撑相足端相对地面静止，
  一个周期内躯干在支撑相前进的距离 = 足端相对躯干的位移 2·amp，
  即 speed·β·T = 2·amp ⇒ 步幅 stride = speed/freq = 2·amp/β。
  这恰是业界滑移指标为零的条件（arXiv:2609.35493：
  slip ⇔ ΔV_foot > ε_v 且 ΔP_foot > ε_p）。
- 无腾空 vs 腾空：trot/walk 全程有足支撑；bound/gallop 因 β<0.5
  存在四足全离地的腾空相（业界以此为与 running 类步态的区分特征）。

坐标：局部坐标 x 向前、y 向上，单位米；world=True 时 x 叠加躯干匀速前进。
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

from ..beat import capability, CapabilityError

# 猫体型（米）：肩髋距、腿长、躯干离地高
BODY_L = 0.34
LEG_L = 0.16
BODY_H = 0.22

# 腿序：左前、右前、左后、右后（与业界相位表顺序一致）
LEG_ORDER = ("LF", "RF", "LH", "RH")
_FRONT = frozenset(("LF", "RF"))

# 步态表: 名称 -> (占空比 β, 四足相位偏移, 期望最少同时支撑足)
#   期望值来自步态学描述: walk/crawl/trot/pace 全程有支撑,
#   bound/gallop 存在腾空相(0)。
GAIT_TABLE = {
    "crawl":  (0.80, (0.00, 0.50, 0.75, 0.25), 3),
    "walk":   (0.75, (0.00, 0.25, 0.50, 0.75), 3),
    "trot":   (0.50, (0.00, 0.50, 0.50, 0.00), 2),
    "pace":   (0.50, (0.00, 0.50, 0.00, 0.50), 2),
    "bound":  (0.40, (0.00, 0.00, 0.50, 0.50), 0),
    "gallop": (0.35, (0.00, 0.10, 0.50, 0.60), 0),
}
GAIT_NAMES = ("crawl", "walk", "trot", "pace", "bound", "gallop")


def _ease(u):
    """smoothstep：摆动相足端回摆的平滑过渡（端点一阶导为 0）。"""
    u = np.clip(np.asarray(u, float), 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


@capability("quadruped", source="Hildebrand 1965 Symmetrical gaits of horses "
                                "(duty factor β + footfall phase); "
                                "CPG gait table arXiv:2201.00206 Table I; "
                                "stride=speed/freq=2·amp/β ⇒ zero foot slip",
            group="locomotion")
def quadruped_sim(cycles=2, n=120, gait="trot", speed=0.8, freq=2.5,
                  world=False):
    """四足步态：生成四足端轨迹、躯干高度、触地相位与支撑标志。

    speed 前进速度(m/s)、freq 步频(Hz) ⇒ 步幅 stride=speed/freq，
    半摆幅 amp=stride·β/2（步幅-速度自洽，支撑相足端世界位移为零）。

    返回 (feet, body_y, phases, support)：
      feet    (n,4,2) 足端位置（world=True 时 x 含躯干前进）
      body_y  (n,)    躯干高度序列
      phases  (4,)    四足相位偏移（周期比例）
      support (n,4)   每帧每足是否处于支撑相
    """
    if gait not in GAIT_TABLE:
        raise CapabilityError("未知步态: %s" % gait)
    beta, off, _ = GAIT_TABLE[gait]
    T = 1.0 / float(freq)
    stride = speed / float(freq)
    amp = stride * beta / 2.0          # 步幅-速度自洽（支撑相零滑移）

    t = np.linspace(0.0, float(cycles), int(n))     # 归一化周期数
    tt = t * T                                      # 实际时间(s)
    x_body = speed * tt if world else np.zeros_like(tt)

    feet = np.zeros((int(n), 4, 2))
    support = np.zeros((int(n), 4), dtype=bool)
    for k, nm in enumerate(LEG_ORDER):
        ph = np.mod(t - off[k], 1.0)                # 该足相位
        sup = ph < beta
        u_s = np.where(sup, ph / max(beta, 1e-12), 0.0)          # 支撑相进度
        u_w = np.where(~sup, (ph - beta) / max(1.0 - beta, 1e-12), 0.0)  # 摆动相进度
        # 支撑相：足端相对躯干匀速向后 +amp → -amp（相对地面静止）
        fx_s = amp * (1.0 - 2.0 * u_s)
        # 摆动相：快速向前 -amp → +amp（ease 平滑，端点导数为 0）
        fx_w = -amp + 2.0 * amp * _ease(u_w)
        fx = np.where(sup, fx_s, fx_w)
        # 抬腿高度：摆动相抬起，支撑相贴地
        lift = np.where(sup, 0.0, LEG_L * 0.35 * np.sin(np.pi * u_w))
        fwd = BODY_L * 0.5 if nm in _FRONT else -BODY_L * 0.5
        feet[:, k, 0] = x_body + fwd + fx
        feet[:, k, 1] = lift
        support[:, k] = sup

    # 躯干高度：无腾空步态起伏很小；β<0.5 的步态有腾空，起伏显著
    ripple = 0.006 if beta >= 0.5 else 0.030
    body_y = BODY_H + ripple * np.sin(4.0 * np.pi * t)
    return feet, body_y, np.array(off, float), support


def foot_slip(feet, support):
    """业界滑移指标：支撑相足端在世界系的最大帧间位移(m)。

    出处 arXiv:2609.35493：slip ⇔ ΔV_foot > ε_v 且 ΔP_foot > ε_p。
    理想步态（步幅-速度自洽）该值应为 0。
    """
    feet = np.asarray(feet, float)
    support = np.asarray(support, bool)
    worst = 0.0
    for k in range(feet.shape[1]):
        m = support[:, k]
        idx = np.where(m[:-1] & m[1:])[0]           # 相邻两帧都在支撑相
        if idx.size:
            d = np.abs(np.diff(feet[:, k, 0])[idx])
            worst = max(worst, float(d.max()))
    return worst


def self_check():
    from base.assertrun import Checker
    c = Checker("quadruped")
    _check_gait_table(c)
    for nm in GAIT_NAMES:
        _check_one_gait(c, nm)
    _check_torso(c)
    return c.report()


# 定义性判据：相位相等关系（步态名, 腿索引对）→ 数据表驱动
_PHASE_EQ = [
    ("trot", (0, 3), "对角同相(LF=RH)"),
    ("trot", (1, 2), "对角同相(RF=LH)"),
    ("pace", (0, 2), "同侧同相(LF=LH)"),
    ("pace", (1, 3), "同侧同相(RF=RH)"),
    ("bound", (0, 1), "前后成对(LF=RF)"),
    ("bound", (2, 3), "前后成对(LH=RH)"),
]


def _check_gait_table(c):
    """步态表自洽：β∈(0,1)、偏移∈[0,1)、定义性相位相等关系。"""
    for nm in GAIT_NAMES:
        beta, off, _ = GAIT_TABLE[nm]
        c.chk("步态表 %s β∈(0,1)" % nm, 0.0 < beta < 1.0, "β=%.2f" % beta)
        c.chk("步态表 %s 偏移∈[0,1)" % nm,
              all(0.0 <= x < 1.0 for x in off), "φ=%s" % (off,))
    for nm, (i, j), desc in _PHASE_EQ:
        off = GAIT_TABLE[nm][1]
        c.chk("%s %s" % (nm, desc), abs(off[i] - off[j]) < 1e-12)

def _check_one_gait(c, nm, cycles=4, n=480, speed=0.8, freq=2.5):
    """单步态：最少支撑足 + 零滑移 + 步幅自洽 + 摆动抬腿。"""
    _, _, exp_min = GAIT_TABLE[nm]
    feet, by, phases, sup = quadruped_sim(cycles=cycles, n=n, gait=nm,
                                          speed=speed, freq=freq, world=True)
    n_sup = int(sup.sum(axis=1).min())
    c.chk("%s 最少同时支撑足=%d" % (nm, exp_min), n_sup == exp_min,
          "min_support=%d" % n_sup)
    slip = foot_slip(feet, sup)
    c.chk("%s 支撑相零滑移" % nm, slip < 1e-9, "slip=%.3e m" % slip)
    # 步幅自洽：一周期推进量 = speed/freq（LF 的 x 含躯干前进）
    adv = float(np.diff(feet[:, 0, 0]).mean()) * (n - 1) / cycles
    body_adv = speed / freq
    c.chk("%s 步幅自洽 stride=speed/freq" % nm,
          abs(adv - body_adv) < 1e-6,
          "实测=%.4f 理论=%.4f" % (adv, body_adv))
    lift = float(feet[:, :, 1].max())
    c.chk("%s 摆动相抬腿>0" % nm, lift > 1e-6, "max_lift=%.4f m" % lift)


def _check_torso(c):
    """D23 猫小跑：躯干平稳（无腾空步态起伏远小于腿长）。"""
    feet, by, phases, sup = quadruped_sim(cycles=2, n=120)
    ripple = float(by.max() - by.min())
    c.chk("D23 躯干起伏<10%腿长", ripple < 0.10 * LEG_L,
          "ripple=%.4f < %.4f" % (ripple, 0.10 * LEG_L))
    c.note("猫小跑 2 周期：躯干起伏 %.4f m（腿长 %.2f m），"
           "最少同时支撑足 %d" % (ripple, LEG_L, int(sup.sum(axis=1).min())))


if __name__ == "__main__":
    self_check()
