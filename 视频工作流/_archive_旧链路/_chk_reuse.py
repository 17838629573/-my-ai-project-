"""检查域8：复用规划/镜像/layer_plan/overlay/additive_offset。

依赖: _chk_base
被依赖: solver_check
改进措施记录: IMPROVE_solver_check.md（改前必读）
"""
from _chk_base import *
from _chk_base import _r

from _solver_reuse import reuse_plan
from _solver_reuse import additive_offset
from _solver_reuse import layer_plan


def check(ctx=None):
    ok = True
    off = (ctx or {}).get("off")

    # ---- 复用规划（铁律49-53，契约 contracts/reuse.md）----
    import math as _m

    # 41)【铁律51】缺镜像锚点必须报错
    r51 = False
    try:
        reuse_plan([0.0, 1.0, 0.0, -1.0])
    except ValueError:
        r51 = True
    ok &= _r("缺镜像锚点报错(铁律51)", r51)

    # 42)【铁律49】半周期镜像：正弦 N=8 -> 生成 4 张
    sin8 = [_m.sin(2 * _m.pi * i / 8) for i in range(8)]
    rp = reuse_plan(sin8, anchor=[0.5, 0.5])
    ok &= _r("半周期镜像 play8->gen4",
             rp["play_n"] == 8 and rp["gen_n"] == 4
             and rp["strategy"] == "half_mirror",
             "gen=%d ratio=%.4g" % (rp["gen_n"],
                                    rp["mirror"]["residual_ratio"]))

    # 43) reuse_map 覆盖全部播放帧且不越界
    cover = set(j for j, _ in rp["reuse_map"])
    ok &= _r("reuse_map 全覆盖不越界",
             len(rp["reuse_map"]) == 8 and max(cover) < rp["gen_n"]
             and len(cover) == rp["gen_n"],
             "映射%d帧 用%d张" % (len(rp["reuse_map"]), len(cover)))

    # 44)【铁律50】反对称被破坏时拒绝镜像（注入二次谐波，恒定偏置补偿不掉）
    harm = [_m.sin(2 * _m.pi * i / 8) + 0.3 * _m.sin(4 * _m.pi * i / 8)
            for i in range(8)]
    rp2 = reuse_plan(harm, criteria={"mirror_residual_max": 0.05},
                     anchor=[0.5, 0.5])
    ok &= _r("反对称破坏拒绝镜像(铁律50)",
             rp2["strategy"] == "none" and rp2["gen_n"] == 8,
             "ratio=%.4g > thr=%.2g" % (rp2["mirror"]["residual_ratio"],
                                        rp2["mirror"]["threshold"]))

    # 45) 恒定偏置可被 offset 完整补偿（x(t)+x(t+T/2)=2·offset）
    off = reuse_plan([x + 0.20 for x in sin8], anchor=[0.5, 0.5])
    ok &= _r("offset 补偿算对",
             abs(off["mirror"]["offset_m"] - 0.20) < 1e-9
             and off["mirror"]["allowed"],
             "offset=%.4g 期望0.20" % off["mirror"]["offset_m"])

    # 46)【铁律31/53】layer_plan 缺 base 报错
    r53 = False
    try:
        layer_plan({"layers": {"overlays": []}})
    except ValueError:
        r53 = True
    ok &= _r("layer_plan缺base报错", r53)

    # 47) overlay 缺 anchor 报错
    r53b = False
    try:
        layer_plan({"layers": {"base": {"name": "b"},
                               "overlays": [{"name": "hair"}]}})
    except ValueError:
        r53b = True
    ok &= _r("overlay缺anchor报错", r53b)

    # 48) additive_offset：长度校验 + 叠加正确
    radd = False
    try:
        additive_offset([0.0, 1.0], [0.0])
    except ValueError:
        radd = True
    s = additive_offset([0.0, 1.0, 2.0], [0.5, 0.5, 0.5], weight=2.0)
    ok &= _r("additive_offset校验+叠加",
             radd and abs(s[1] - 2.0) < 1e-12, "1.0+2*0.5=%.3g" % s[1])

    # 49) 证伪：阈值真在驱动策略（同一序列，宽松放行 / 收紧拒绝）
    a_hi = reuse_plan(harm, criteria={"mirror_residual_max": 0.5},
                      anchor=[0.5, 0.5])
    a_lo = reuse_plan(harm, criteria={"mirror_residual_max": 0.1},
                      anchor=[0.5, 0.5])
    ok &= _r("阈值真驱动策略(证伪)",
             a_hi["mirror"]["allowed"] and not a_lo["mirror"]["allowed"],
             "thr0.5->%s thr0.1->%s"
             % (a_hi["strategy"], a_lo["strategy"]))

    # 50)【铁律49】gen_n <= play_n，防省了个寂寞（历史 bug：素材 16 张却要生 17）
    gn_ok = all(
        reuse_plan([_m.sin(2 * _m.pi * i / n) for i in range(n)],
                   anchor=[0.5, 0.5])["gen_n"] <= n
        for n in (4, 8, 16, 34))
    ok &= _r("gen_n<=play_n(复用必省张数)", gn_ok,
             "各N下生成张数均不超过播放张数")

    if ctx is not None:
        ctx["s"] = s
    return ok
