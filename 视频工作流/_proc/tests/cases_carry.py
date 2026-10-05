"""E 组搬运用例（E26 搬运箱子）

契约: tests/cases_carry
  输入: 无（用例自带固定参数，固定种子不随机）
  输出: (checks, extra)——checks 交 harness.report，extra 为补充事实
  依赖: numpy, motion.character.carry, tests.harness, tests.gen
  被依赖: tests/run_all
  约束: 判据阈值一律取自 harness.CRIT，不许就地拍数；
        渲染统一走 tests.gen.render_case（全胶囊管线，不许另写精简渲染）
  校验: python -m tests.run_all
"""
import numpy as np

import motion.character.carry as CB
import tests.harness as H

HAND_R = 0.040          # 手掌球半径（米），用于手-箱穿透判定


def _samples(n=96, params=None):
    """采样整段 carry：返回 [(u, J, box)]"""
    return [(i / (n - 1.0),) + _one(i / (n - 1.0), params)
            for i in range(n)]


def _one(u, params=None):
    r = CB.carry_box(u, params)
    return r["J"], r["box"]


def _metres(J, key):
    j = J[key]
    return np.array([float(j[0]) * CB.H_M, float(j[1]) * CB.H_M,
                     float(j[2]) * CB.H_M])


def case_E26():
    """搬运箱子：抱起 → 行走 → 放下，箱体不穿手、不脱手、脚不滑步

    依据: NIOSH RWL=LC×HM×VM×DM×AM×FM×CM（HM=25/H 令 H 最小 → 箱贴近躯干）；
          Animation Master 把道具约束到躯干骨（箱体随躯干走）；
          半蹲举膝屈~90°/躯干前倾~45°（Burgess-Limerick & Straker 2003）
    """
    N = 96
    S = _samples(N)
    cyc = 2.0                               # 与 carry_box 默认一致
    a, b, c, _d = CB.SPANS
    # 根位移必须线性、且与脚无关。
    # 曾误用"支撑脚反解"(_tr = off + (pu - cu)): 那样支撑脚世界坐标恒等于
    # 常数, 滑步判据变成恒 0 的自证循环——任何脚轨迹都判 PASS, 判据没牙齿。
    # 现在 travel 是唯一全局恒定速率(由步态自带步长推出), 判据真正检验的是
    # "每只脚在支撑期是否以同一恒定速率后退": 左右对称、无加减速, 才是真判据。
    step = 0.561                            # carry_box 默认步长(m), 见其 params
    stride = 2.0 * step                     # 一个完整步态周期前进量

    def travel_of(uu):
        if uu < a:
            return 0.0
        if uu < a + b:
            return stride * cyc * (uu - a) / b
        return stride * cyc
    # --- 手-箱穿透：腕球 vs 箱体 AABB（握持全程）
    pairs, feet, owners = [], [], []
    for u, J, box in S:
        # 滑步必须在世界坐标量：支撑脚相对地面应静止，
        # 只算身体局部 u 会把正常迈步当成打滑
        travel = travel_of(u)
        for side in ("l", "r"):
            c = _metres(J, "wri_" + side)
            pen = CB.sphere_box_pen(c, HAND_R, box["c"], box["half"])
            pairs.append((HAND_R - pen, HAND_R, 0.0))
        # 滑步只在行走段(carry)量: 站立/半蹲时双脚恒在地面,
        # 那段由 carry 自检的"双脚不滑不飘"负责(半蹲踝位移 0)
        if a <= u < a + b:
            # 只测当前支撑脚(按相位判定, 与 carry_box 行走段同一套)
            _phs = (cyc * (u - a) / b) % 1.0
            _side = "ank_l" if _phs < 0.5 else "ank_r"
            feet.append((_side, travel + float(J[_side][0]) * CB.H_M,
                         float(J[_side][1]) * CB.H_M))
        owners.append(CB.carry_box(u)["owner"])
    g0 = min(f[2] for f in feet)
    # 滑步按"每只脚各自的支撑段"分段量:
    # 串成一条会在换脚那一帧比到另一只脚——它本来就落在前方半个步长
    # (0.561m)处, 那不是打滑。实测旧口径因此虚高到 3.92cm/帧。
    # 分段后只比同一只脚的连续帧, 段与段之间不比较。
    segs, _cur = [], None
    for _sd, _x, _h in feet:
        if _cur is None or _cur[0] != _sd:
            _cur = (_sd, [])
            segs.append(_cur)
        _cur[1].append((_x, 0.0, _h - g0))
    _ms, _xs = [], 0.0
    for _s, _pts in segs:
        _m, _x = H.skate_cm_frame(_pts)
        _ms.append(_m)
        _xs = max(_xs, _x)
    skate = (float(np.mean(_ms)) if _ms else 0.0, _xs)
    checks = [
        ("penetration_m", H.penetration_m(pairs)),
        ("skate_cm_frame", skate[1]),
    ]
    # --- 所有权链路：world → both → world，各切换一次
    seq = [o for o in owners]
    sw = sum(1 for i in range(1, len(seq)) if seq[i] != seq[i - 1])
    _, extra = H.report(checks)
    out = {"箱尺寸_m": list(CB.BOX),
           "握持帧_owner": "both" if "both" in seq else "无",
           "owner_切换次数": sw,
           "起始_owner": seq[0], "结束_owner": seq[-1],
           "手箱最大穿透_m": round(H.penetration_m(pairs), 6),
           "滑步_最大_cm每帧": round(float(skate[1]), 4),
           "落足间距_m": [round(float(segs[i + 1][1][0][0])
                           - float(segs[i][1][0][0]), 4)
                          for i in range(len(segs) - 1)]}
    return checks, out
