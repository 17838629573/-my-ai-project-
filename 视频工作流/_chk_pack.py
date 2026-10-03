"""检查域9：16帧封顶/mat_frames/图集规划/strip。

依赖: _chk_base
被依赖: solver_check
改进措施记录: IMPROVE_solver_check.md（改前必读）
"""
from _chk_base import *
from _chk_base import _r


def check(ctx=None):
    ok = True
    spec = (ctx or {}).get("spec") or BASE_SPEC
    a = (ctx or {}).get("a") or solve(BASE_SPEC)
    sp = (ctx or {}).get("sp")
    s = (ctx or {}).get("s")

    # 51)【铁律54】源码逻辑区不得出现 16 帧封顶（那是游戏值）
    lg = SOLVER_LOGIC   # 扫 solver 系真实逻辑模块，禁 __file__ 自指
    ok &= _r("源码无16帧封顶", "MAX_MAT_FRAMES)" not in lg and
             "min(N, MAX_MAT_FRAMES)" not in lg,
             "逻辑区禁用 min(N,MAX_MAT_FRAMES)")

    # 52)【铁律54】功能验：mat_frames 必须等于物理帧数，不被截
    mf_a, fr_a = int(a["mat_frames"]), int(a["frames"])
    ok &= _r("mat_frames==frames(视频不封顶)",
             mf_a == fr_a and abs(a["playrate"] - 1.0) < 1e-9,
             "mat=%d frames=%d playrate=%s" % (mf_a, fr_a, a["playrate"]))

    # 53)【铁律55/56】图集规划：多张合图、格数受限、尺寸不超 2048
    sp = sheet_plan(a, spec, max_cells=16, aspect=1.0)
    tot = sum(s["cells"] for s in sp["sheets"])
    ok &= _r("图集格数覆盖生成张数", tot >= sp["gen_frames"],
             "%d张图集 共%d格 >= %d" % (sp["n_sheets"], tot, sp["gen_frames"]))
    ok &= _r("单张格数<=max_cells",
             all(s["cells"] <= 16 for s in sp["sheets"]),
             "max_cells=%d" % sp["max_cells"])
    ok &= _r("单张图集<=2048",
             all(max(s["sheet_px"]) <= 2048 for s in sp["sheets"]),
             "最大边长=%d" % max(max(s["sheet_px"]) for s in sp["sheets"]))
    # 格不能被压成糊：每格至少 128x128
    ok &= _r("每格不小于128(防压糊)",
             all(min(s["cell_px"]) >= 128 for s in sp["sheets"]),
             "最小格=%s" % min(min(s["cell_px"]) for s in sp["sheets"]))

    # 54)【铁律57】长条物体走 strip
    sp_strip = sheet_plan(a, spec, max_cells=16, aspect=3.0)
    ok &= _r("长条物体用strip(1行)",
             sp_strip["layout"] == "strip"
             and all(s["rows"] == 1 for s in sp_strip["sheets"]),
             "aspect=3.0 -> %s" % sp_strip["layout"])

    return ok
