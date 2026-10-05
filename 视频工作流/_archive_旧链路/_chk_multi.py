"""检查域6：多驱动叠加（位移域）/循环闭合。

依赖: _chk_base
被依赖: solver_check
改进措施记录: IMPROVE_solver_check.md（改前必读）
"""
from _chk_base import *
from _chk_base import _r

from _solver_chain import loop_seam_ratio
from _solver_chain import frame_durations
from _solver_chain import chain_response_multi
import math
from _solver_chain import chain_response


def check(ctx=None):
    ok = True

    # 32) 多驱动叠加（铁律42修订：位移域 additive，非振幅域 SRSS）
    lk2 = [{"L": 0.3, "m": 0.01, "EI": 5e-7, "zeta": 0.10}]
    a_one = chain_response(lk2, 2.0, 0.02)[-1]["amp_m"]
    # 退化性：additive 权重 0 -> 严格等于 base 单驱动（最本质断言）
    r_w0 = chain_response_multi(lk2, [(2.0, 0.02, "gait"), (1.7, 0.05, "wind")],
                                weights=[1.0, 0.0])[-1]
    # 相对容差 1e-4：峰值由 n_sample 离散采样求得，峰处二阶误差
    # ~A·(Δt·ω)²/2 ≈ 5e-6 相对量，属采样精度固有，非逻辑错
    ok &= _r("additive权重0退化为base(相对1e-4)",
             abs(r_w0["amp_m"] - a_one) / max(a_one, 1e-12) < 1e-4,
             "%.8f vs %.8f 相对差%.2e" % (r_w0["amp_m"], a_one,
                                        abs(r_w0["amp_m"] - a_one) / a_one))
    r_two = chain_response_multi(lk2, [(2.0, 0.02, "gait"),
                                       (1.7, 0.05, "wind")])[-1]
    comps = r_two["components"]
    s_lo = 2.0 * max(c["amp_m"] * c["weight"] for c in comps)
    s_hi = sum(2.0 * c["amp_m"] * c["weight"] for c in comps)
    ok &= _r("双驱动位移域叠加(分量数=2,峰值落在上下界内)",
             len(comps) == 2 and s_lo <= r_two["amp_pp_m"] <= s_hi + 1e-9,
             "pp=%.4f  下界%.4f 上界%.4f" % (r_two["amp_pp_m"], s_lo, s_hi))
    # 位移域而非振幅域：sqrt(ΣA²) 与逐帧求值结果必须不同（否则说明没改）
    srss = math.sqrt(sum((c["amp_m"] * c["weight"]) ** 2 for c in comps))
    ok &= _r("非振幅域SRSS(证明相位参与)",
             abs(r_two["amp_m"] - srss) > 1e-6,
             "SRSS=%.6f 位移域=%.6f" % (srss, r_two["amp_m"]))

    # 33) 循环闭合（铁律43修订：默认均匀，禁默认末帧停留）
    ds = frame_durations(12, 0.5)
    ok &= _r("默认均匀帧长(禁默认末帧停留)",
             len(ds) == 12 and abs(ds[0] - ds[-1]) < 1e-12
             and abs(sum(ds) - 0.5) < 1e-9,
             "每帧=%.4f 总=%.4fs" % (ds[0], sum(ds)))
    dh = frame_durations(12, 0.5, tail_ratio=2.0, intentional_hold=True)
    ok &= _r("intentional_hold才加长且总长守恒",
             dh[-1] > dh[0] * 1.5 and abs(sum(dh) - 0.5) < 1e-9,
             "基础=%.4f 末帧=%.4f 总=%.4fs" % (dh[0], dh[-1], sum(dh)))
    try:
        frame_durations(12, 0.5, tail_ratio=0.5, intentional_hold=True)
        r33 = False
    except ValueError:
        r33 = True
    ok &= _r("hold时tail_ratio<1报错", r33)
    ok &= _r("闭合判据:seam比>1.5判缺姿态",
             loop_seam_ratio(9.0, 4.0) > 1.5 and loop_seam_ratio(4.0, 4.0) <= 1.5,
             "9/4=%.2f 4/4=%.2f" % (loop_seam_ratio(9.0, 4.0),
                                    loop_seam_ratio(4.0, 4.0)))

    return ok
