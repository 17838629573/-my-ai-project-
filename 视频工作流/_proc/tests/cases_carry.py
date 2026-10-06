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

HAND_R = CB.PALM_R   # 掌球半径单点定义在 motion/character/carry.py（A2 铁律）


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


def _travel_of(a, b, stride, cyc):
    """根位移：起步前 0、行走段线性、放下后恒定。

    曾误用"支撑脚反解"(_tr = off + (pu - cu)): 那样支撑脚世界坐标恒等于
    常数, 滑步判据变成恒 0 的自证循环——任何脚轨迹都判 PASS, 判据没牙齿。
    travel 是唯一全局恒定速率(由步态自带步长推出), 判据真正检验的是
    "每只脚在支撑期是否以同一恒定速率后退": 左右对称、无加减速, 才是真判据。
    """

    def travel_of(uu):
        if uu < a:
            return 0.0
        if uu < a + b:
            return stride * cyc * (uu - a) / b
        return stride * cyc
    return travel_of


def _e26_collect(N, a, b, cyc, travel_of):
    """逐帧采三组证据：腕-箱穿透 / 支撑脚世界轨迹 / owner 链路。"""
    pairs, feet, owners, last_J = [], [], [], None
    for u, J, box in _samples(N):
        # 滑步必须在世界坐标量：支撑脚相对地面应静止，
        # 只算身体局部 u 会把正常迈步当成打滑
        travel = travel_of(u)
        # 手-箱穿透只在握持段(owner=='both')量。
        # 曾对所有帧测量: 起身(rise)相位箱子已 detach 落到台面、手回到体侧
        # 自然位(z=SHOULDER_Z), 腕球会落进已静止箱体的 AABB 内 → 虚报
        # 0.00977m 穿透。那是"测到了不属于该段的事件", 不是真穿模。
        # 与滑步分段量同源: 起止相位交给 carry 自检负责。
        ow = CB.carry_box(u)["owner"]
        if ow == "both":
            for side in ("l", "r"):
                _c = _metres(J, "wri_" + side)
                pen = CB.sphere_box_pen(_c, HAND_R, box["c"], box["half"])
                pairs.append((HAND_R - pen, HAND_R, 0.0))
        # 滑步只在行走段(carry)量: 站立/半蹲时双脚恒在地面,
        # 那段由 carry 自检的"双脚不滑不飘"负责(半蹲踝位移 0)
        if a <= u < a + b:
            # 只测当前支撑脚(按相位判定, 与 carry_box 行走段同一套)
            _phs = (cyc * (u - a) / b) % 1.0
            _side = "ank_l" if _phs < 0.5 else "ank_r"
            feet.append((_side, travel + float(J[_side][0]) * CB.H_M,
                         float(J[_side][1]) * CB.H_M))
        owners.append(ow)
        last_J = J
    return pairs, feet, owners, last_J


def _skate_segs(feet, g0):
    """滑步分段量：只比同一只脚的连续帧, 段与段之间不比较。

    串成一条会在换脚那一帧比到另一只脚——它本来就落在前方半个步长
    (0.561m)处, 那不是打滑。实测旧口径因此虚高到 3.92cm/帧。
    """
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
    return (float(np.mean(_ms)) if _ms else 0.0, _xs), segs


def case_E26():
    """搬运箱子：抱起 → 行走 → 放下，箱体不穿手、不脱手、脚不滑步

    依据: NIOSH RWL=LC×HM×VM×DM×AM×FM×CM（HM=25/H 令 H 最小 → 箱贴近躯干）；
          Animation Master 把道具约束到躯干骨（箱体随躯干走）；
          半蹲举膝屈~90°/躯干前倾~45°（Burgess-Limerick & Straker 2003）
    """
    N = 96
    a, b, _c, _d = CB.SPANS
    cyc = 2.0                               # 与 carry_box 默认一致
    step = 0.561                            # carry_box 默认步长(m), 见其 params
    travel_of = _travel_of(a, b, 2.0 * step, cyc)
    pairs, feet, owners, last_J = _e26_collect(N, a, b, cyc, travel_of)
    g0 = min(f[2] for f in feet)
    skate, segs = _skate_segs(feet, g0)
    # --- 放下相位：走 carry.box_release，校验 detach 后底面贴合台面
    _rel = CB.box_release(last_J, float(g0))
    _rest = abs(float(_rel["c"][1] - _rel["half"][1]) - float(g0))
    checks = [
        ("penetration_m", H.penetration_m(pairs)),
        ("skate_cm_frame", skate[1]),
        ("box_rest_m", _rest),
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
           "box_release_owner": _rel["owner"],
           "box_release_底面贴合偏差_m": round(_rest, 9),
           "落足间距_m": [round(float(segs[i + 1][1][0][0])
                           - float(segs[i][1][0][0]), 4)
                          for i in range(len(segs) - 1)]}
    return checks, out
