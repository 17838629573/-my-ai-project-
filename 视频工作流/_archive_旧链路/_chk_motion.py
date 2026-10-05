"""检查域5：run_spec 契约/扬角/振幅比/风向全局一致。

依赖: _chk_base
被依赖: solver_check
改进措施记录: IMPROVE_solver_check.md（改前必读）
"""
from _chk_base import *
from _chk_base import _r

import json
from _solver_run import run_spec
from _solver_base import wind_sign
from _solver_chain import flag_lift_deg, solve
from _solver_chain import amp_over_L
import physics


def check(ctx=None):
    ok = True
    spec = (ctx or {}).get("spec")
    mono = (ctx or {}).get("mono")

    # 27) run_spec 的契约文件缺 '物体' 必须报错
    import tempfile, os as _os
    tf = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                     encoding="utf-8")
    json.dump({}, tf)
    tf.close()
    r27 = False
    try:
        run_spec(tf.name)
    except ValueError:
        r27 = True
    _os.unlink(tf.name)
    ok &= _r("run_spec 缺物体列表报错", r27)

    # 28) 扬角 Rule of 4（铁律32：形态由 U 决定，不是常数）
    lifts = [flag_lift_deg(u) for u in (0.0, 2.0, 4.4, 8.0, 12.3, 20.0)]
    mono = all(lifts[i] <= lifts[i + 1] + 1e-9 for i in range(len(lifts) - 1))
    ok &= _r("扬角随风单调且钳制90°", mono and lifts[-1] <= 90.0 + 1e-9,
             "->".join("%.0f°" % x for x in lifts))

    # 29) 振幅比 A/L 随 U 变（回归旧 bug：A_OVER_L=1.6 常数导致小风也大摆）
    def _aol(u):
        lv = physics.beaufort_level(u)[0]
        return amp_over_L(lv, {})
    aols = [_aol(u) for u in (0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2)]
    ok &= _r("A/L 随风速递增(非常数)",
             all(aols[i] <= aols[i + 1] + 1e-9 for i in range(len(aols) - 1))
             and aols[0] < 0.1 * aols[-1],
             "->".join("%.2f" % x for x in aols))

    # 30) 风向全局一致（铁律39）
    sg_r, sg_l = wind_sign(0.0), wind_sign(180.0)
    ok &= _r("风向符号翻转", sg_r == 1.0 and sg_l == -1.0,
             "0°=%+.0f 180°=%+.0f" % (sg_r, sg_l))
    sp = dict(spec)
    sp["wind_dir"] = 180.0
    a_l = solve(sp)
    a_r = solve(spec)
    xr = [c[-1][0] for c in a_r["phase_geometry"]]
    xl = [c[-1][0] for c in a_l["phase_geometry"]]
    ok &= _r("骨架随风向翻转",
             (sum(xr) / len(xr)) * (sum(xl) / len(xl)) < 0,
             "右吹均值%+.2f 左吹均值%+.2f" % (sum(xr)/len(xr), sum(xl)/len(xl)))

    # 31) run_spec 广播风向：物体自带不同 wind_dir 必须报错
    import tempfile, os as _os2
    tf2 = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                      encoding="utf-8")
    json.dump({"wind": {"dir_deg": 0.0, "U": 3.4},
               "物体": [{"物体": "x", "spec": {
                   "name": "x", "family": "cloth", "source": "wind",
                   "wind_dir": 180.0,
                   "links": [{"L": 0.5, "m": 0.01, "EI": 1e-6, "zeta": 0.1}]}}]},
              tf2)
    tf2.close()
    r31 = False
    try:
        run_spec(tf2.name)
    except ValueError:
        r31 = True
    _os2.unlink(tf2.name)
    ok &= _r("物体风向与全片不一致报错", r31)

    if ctx is not None:
        ctx["sp"] = sp
    return ok
