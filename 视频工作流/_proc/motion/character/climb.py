# 契约: proc/motion/character/climb
#   一句话: 爬梯：五效应器三态循环上升，肘膝由两骨IK反解保证骨长守恒
#   完整契约见 motion/__init__.py
"""爬梯 (climb)。

依据（搜索先行，非凭记忆）：
- 五效应器系统 RIGHT_HAND / LEFT_HAND / RIGHT_FOOT / LEFT_FOOT / ROOT，
  各带 LAST / CURRENT / NEXT 三位置状态 + EaseLerp 平滑过渡，避免跳帧。
- 两阶段循环：阶段一 手上伸（脚保持）；阶段二 脚上跨一阶（手保持抓握）。
- 根位置（ROOT/pelvis）由手/脚抓握点共同推导，全周期连续上升。

骨长（Drillis & Contini 1966 / Winter，占身高比例）：
    上臂 0.186  前臂 0.146  大腿 0.245  小腿 0.246
    → 臂全长 0.332，腿全长 0.491
肘/膝一律由 two_bone_ik（余弦定理解析解）反解，保证骨长守恒。

相位模型（本项目推导，已验证闭合）：
  sep = 梯距/身高。阶段一(ph<0.5)：手上升 sep·ease，脚不动，
  身体小幅上提（腿长 0.44→0.46）；阶段二：手保持世界高度，
  脚上跨 sep·ease，身体上引（腿长 0.46→0.44）。
  手相对肩的伸展在 [0.156, 0.312] 之间，恒小于臂全长 0.332（不超伸）；
  腿长恒在 [0.44, 0.46]，恒小于腿全长 0.491（不超伸）。
  周期末与下一周期初的 hand/foot/pelvis 三点逐位相等 → 无跳变。

坐标：x 前后（+ 为面向梯子），y 高度（0 地面，1 身高），z 侧向（+ 左）。
"""
import math

import numpy as np

from ..beat import capability
from .leg import two_bone_ik

LEG_BASE = 0.44     # 周期初 pelvis 相对脚的高度
LEG_SWING = 0.02    # 腿长在周期内的摆动幅度
ARM_UP = 0.462      # 周期初 手相对 pelvis 的高度（含 x 前伸后 3D 距 <= 0.332）
SWAY = 0.012        # 躯干侧向摆动幅度

UPPER_ARM = 0.186
FOREARM = 0.146
THIGH = 0.245
SHANK = 0.246
ARM_FULL = UPPER_ARM + FOREARM      # 0.332
LEG_FULL = THIGH + SHANK            # 0.491
SHOULDER_UP = 0.32                  # 肩相对 pelvis 的高度


def _ease(u):
    """EaseLerp: 平滑过渡（smoothstep），一阶导在端点为 0。"""
    u = 0.0 if u < 0.0 else (1.0 if u > 1.0 else u)
    return u * u * (3.0 - 2.0 * u)


def _mid(root, target, L1, L2, bend):
    """两骨 IK 求中间关节（肘/膝），兼容 tuple/ndarray 返回。"""
    r = two_bone_ik(np.asarray(root, float), np.asarray(target, float),
                    L1, L2, bend=bend)
    m = r[0] if isinstance(r, (tuple, list)) else r
    return tuple(float(c) for c in np.asarray(m, float).reshape(-1)[:3])


@capability("climb", "爬梯: 五效应器(RH/LH/RF/LF/ROOT)三态+ease平滑; 两阶段(手上伸→脚上跨); 根由手脚抓握点共同推导")
def climb(t, rung_sep=0.30, body_h=1.70, cycle=1.4, base=0.0):
    """爬梯姿态。

    t        秒（连续）
    rung_sep 梯距（米）
    body_h   身高（米）
    cycle    每阶耗时（秒）
    base     最低横杆高度（米）
    返回 21 关节字典，值 (x, y, z) 归一化身高。
    """
    u = 1.0 / body_h
    sep = rung_sep * u
    b = base * u

    r = t / cycle
    idx = int(math.floor(r))
    ph = r - idx

    if ph < 0.5:
        e1 = _ease(ph / 0.5)
        f = float(idx)
        leg = LEG_BASE + LEG_SWING * e1
        s = sep * e1                      # 手额外上升量
    else:
        e2 = _ease((ph - 0.5) / 0.5)
        f = idx + e2
        leg = LEG_BASE + LEG_SWING * (1.0 - e2)
        s = sep

    foot_y = b + f * sep
    pel_y = foot_y + leg
    h = b + float(idx) * sep + LEG_BASE + ARM_UP + s

    sway = SWAY * math.sin(2.0 * math.pi * (idx + ph))

    J = {}
    J["pelvis"] = (0.0, pel_y, sway)
    J["waist"] = (0.0, pel_y + 0.10, sway * 0.8)
    J["chest"] = (0.0, pel_y + 0.24, sway * 0.6)
    J["neck"] = (0.0, pel_y + 0.34, sway * 0.4)
    J["head"] = (0.0, pel_y + 0.44, sway * 0.3)

    J["sh_l"] = (0.0, pel_y + SHOULDER_UP, +0.10)
    J["sh_r"] = (0.0, pel_y + SHOULDER_UP, -0.10)

    # 腕（前伸抓握横杆）
    J["wri_l"] = (0.13, h, +0.085)
    J["wri_r"] = (0.13, h, -0.085)

    # 肘：两骨 IK 反解，肘朝前（+x），骨长守恒
    J["elb_l"] = _mid(J["sh_l"], J["wri_l"], UPPER_ARM, FOREARM, (1.0, 0.0, 0.0))
    J["elb_r"] = _mid(J["sh_r"], J["wri_r"], UPPER_ARM, FOREARM, (1.0, 0.0, 0.0))

    J["hip_l"] = (0.0, pel_y, +0.080)
    J["hip_r"] = (0.0, pel_y, -0.080)

    for side, z in (("l", +0.075), ("r", -0.075)):
        J["ank_" + side] = (0.02, foot_y, z)
        J["heel_" + side] = (-0.035, foot_y, z)
        J["toe_" + side] = (0.085, foot_y, z)

    # 膝：两骨 IK 反解，膝朝前（+x），骨长守恒
    J["knee_l"] = _mid(J["hip_l"], J["ank_l"], THIGH, SHANK, (1.0, 0.0, 0.0))
    J["knee_r"] = _mid(J["hip_r"], J["ank_r"], THIGH, SHANK, (1.0, 0.0, 0.0))

    return J


def _d(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def _jump_y(Js, key):
    return max(abs(Js[i + 1][key][1] - Js[i][key][1])
               for i in range(len(Js) - 1))


def _chk_basic(c, Js, keys):
    """基本：关节数、无 NaN、上升单调、末端不跳。"""
    c.chk("关节数=21", len(keys) == 21, str(len(keys)))
    bad = [k for J in Js for k, v in J.items()
           if any(math.isnan(x) or math.isinf(x) for x in v)]
    c.chk("无NaN/Inf", not bad, str(bad[:3]))
    dy = [Js[i + 1]["pelvis"][1] - Js[i]["pelvis"][1]
          for i in range(len(Js) - 1)]
    c.chk("pelvis单调上升", all(d >= -1e-12 for d in dy), "min=%g" % min(dy))
    c.chk("腕跳变<0.02", _jump_y(Js, "wri_l") < 0.02, "%.5f" % _jump_y(Js, "wri_l"))
    c.chk("踝跳变<0.02", _jump_y(Js, "ank_l") < 0.02, "%.5f" % _jump_y(Js, "ank_l"))


def _chk_bone(c, Js):
    """骨长守恒 + 不超伸 + 不折叠。"""
    e1 = max(abs(_d(J["sh_l"], J["elb_l"]) - UPPER_ARM) for J in Js)
    e2 = max(abs(_d(J["elb_l"], J["wri_l"]) - FOREARM) for J in Js)
    e3 = max(abs(_d(J["hip_l"], J["knee_l"]) - THIGH) for J in Js)
    e4 = max(abs(_d(J["knee_l"], J["ank_l"]) - SHANK) for J in Js)
    c.chk("上臂长守恒", e1 < 1e-6, "%.2e" % e1)
    c.chk("前臂长守恒", e2 < 1e-6, "%.2e" % e2)
    c.chk("大腿长守恒", e3 < 1e-6, "%.2e" % e3)
    c.chk("小腿长守恒", e4 < 1e-6, "%.2e" % e4)
    arm = max(_d(J["sh_l"], J["wri_l"]) for J in Js)
    c.chk("臂不超伸<=0.332", arm <= ARM_FULL + 1e-6, "max=%.4f" % arm)
    legn = max(_d(J["hip_l"], J["ank_l"]) for J in Js)
    c.chk("腿不超伸<=0.491", legn <= LEG_FULL + 1e-6, "max=%.4f" % legn)
    # 不折叠（末端不得短于 |L1-L2|）
    amin = min(_d(J["sh_l"], J["wri_l"]) for J in Js)
    c.chk("臂不折叠>=0.041", amin >= abs(UPPER_ARM - FOREARM) - 1e-6,
          "min=%.4f" % amin)


def _chk_shape(c, Js, keys):
    """形态：肘不反折、脚不穿地、周期边界闭合。"""
    forw = [J["elb_l"][0] - min(J["sh_l"][0], J["wri_l"][0]) for J in Js]
    c.chk("肘前向(不反折)", all(f >= -1e-9 for f in forw), "min=%g" % min(forw))
    c.chk("脚不穿地", min(J["ank_l"][1] for J in Js) >= -1e-9,
          "min=%g" % min(J["ank_l"][1] for J in Js))
    a, b2 = climb(1.4 - 1e-9), climb(1.4 + 1e-9)
    d = max(abs(a[k][1] - b2[k][1]) for k in keys)
    c.chk("周期边界连续", d < 1e-6, "%.2e" % d)


def self_check():
    """爬梯自检：连续性、骨长守恒、不超伸、无 NaN、周期闭合。"""
    from base.assertrun import Checker
    c = Checker("climb")
    ts = [i / 240.0 for i in range(0, 2400)]
    Js = [climb(t) for t in ts]
    keys = sorted(Js[0].keys())
    _chk_basic(c, Js, keys)
    _chk_bone(c, Js)
    _chk_shape(c, Js, keys)
    return c.report()


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
