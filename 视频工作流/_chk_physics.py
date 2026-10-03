"""检查域1：缺槽报错/物性换算/帧数/St/固定端/相位均匀性。

依赖: _chk_base
被依赖: solver_check
改进措施记录: IMPROVE_solver_check.md（改前必读）
"""
from _chk_base import *
from _chk_base import _r


def check(ctx=None):
    ok = True

    # 1) 缺槽必须报错（铁律31：禁静默填默认）
    raised = False
    try:
        solve({"family": "cloth", "geometry": {"L": 0.9, "W": 0.3}})
    except ValueError:
        raised = True
    ok &= _r("缺槽报错(禁静默)", raised)

    # 2) 物性换算：唐绢 62 g/m2（AI 搜证值）
    spec = {"family": "cloth",
            "geometry": {"L": 0.90, "W": 0.30, "t": 2.0e-4},
            "material": {"sigma": 0.062, "E": 5.0e9, "nu": 0.34},
            "fluid": {"U": 12.3},
            "criteria": {"regime_by": "mu",
                         "mu_stable": 0.02, "mu_chaotic": 0.30}}
    a = solve(spec)
    m_exp = 0.062 * 0.90 * 0.30
    ok &= _r("质量=σ·L·W", abs(a["derived"]["mass_kg"] - m_exp) < 1e-9,
             "%.5f kg" % a["derived"]["mass_kg"])

    # 3) 帧数 = round(T*FPS)（铁律29）
    exp_n = round(a["period_s"] * framerate.FPS)
    ok &= _r("帧数N=round(T·FPS)", a["frames"] == exp_n,
             "N=%d T=%.3fs" % (a["frames"], a["period_s"]))

    # 4) St 定义自洽（铁律20）
    A_single = a["tip_pp_amp_m"] / 2.0
    st = 2 * A_single * a["freq_hz"] / 12.3
    ok &= _r("St=2Af/U 自洽≈0.2", abs(st - 0.2) < 1e-6, "St=%.4f" % st)

    # 4b)【铁律41】素材张数/排布/相位必须能发给 AI
    mf = a["mat_frames"]
    ly = sheet_layout(a)
    ok &= _r("mat_frames 存在且<=frames",
             isinstance(mf, int) and 0 < mf <= a["frames"],
             "mat=%d frames=%d" % (mf, a["frames"]))
    ok &= _r("网格装得下素材", ly["rows"] * ly["cols"] >= ly["count"],
             "%d行x%d列 装 %d" % (ly["rows"], ly["cols"], ly["count"]))
    ok &= _r("phase_map 长度=素材张数",
             len(ly["phase_map"]) == ly["count"],
             "n=%d" % len(ly["phase_map"]))
    ok &= _r("playrate=frames/mat_frames",
             abs(ly["playrate"] - a["frames"] / float(mf)) < 1e-3,
             "playrate=%.3f" % ly["playrate"])

    # 5) 固定端位移恒 0
    mx = max(abs(c[0][0]) for c in a["phase_geometry"])
    ok &= _r("固定端位移=0", mx < 1e-9, "max=%.2e" % mx)

    # 6) 相位均匀性（等相位正弦理论 max/mean=1.5703）
    #    摆动须沿"垂旗方向 n"测量：水平旗(lift=90°)时摆动全在竖直方向，
    #    只看 x 会得到常数而误判（自检自身假 PASS，第4次）
    lr = math.radians(a["lift_deg"])
    sg = wind_sign(a["wind_dir_deg"])
    nx, ny = sg * math.cos(lr), -math.sin(lr)
    tips = [c[-1][0] * nx + c[-1][1] * ny for c in a["phase_geometry"]]
    d = [abs(tips[(i + 1) % len(tips)] - tips[i]) for i in range(len(tips))]
    ratio = max(d) / (sum(d) / len(d)) if sum(d) > 1e-12 else float("inf")
    ok &= _r("相位均匀", ratio < 1.75,
             "max/mean=%.3f (理论1.5703) 沿n=(%.2f,%.2f)" % (ratio, nx, ny))

    if ctx is not None:
        ctx["spec"] = spec
        ctx["a"] = a
    return ok
