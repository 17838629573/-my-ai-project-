"""检查域7：容纳性/居中/min_fill/centroid/探针计划。

依赖: _chk_base
被依赖: solver_check
改进措施记录: IMPROVE_solver_check.md（改前必读）
"""
from _chk_base import *
from _chk_base import _r

import numpy as np
from _solver_probe import containment_check
from _solver_probe import probe_check
from _chk_base import BASE_SPEC
from _solver_probe import probe_plan
from _solver_sheet import draw_sheet
import cv2
from _solver_chain import solve


def check(ctx=None):
    ok = True
    spec = (ctx or {}).get("spec") or BASE_SPEC

    # 34)【铁律47】容纳性：触边必须 FAIL（格内铺满 -> margin=0）
    cw_, ch_ = 120, 120
    full_cell = np.zeros((ch_, cw_, 4), np.uint8)
    full_cell[:, :, :3] = 255                      # 全前景（背景在四角）
    full_cell[0, 0, :3] = 0                        # 只把四角刷成键控色
    full_cell[0, -1, :3] = 0
    full_cell[-1, 0, :3] = 0
    full_cell[-1, -1, :3] = 0
    okc_full, det_full = containment_check(full_cell, cw_, ch_, "free")
    ok &= _r("触边(铺满格)判 FAIL", not okc_full,
             "margin=%s fill_w=%.2f" % (det_full["margin"], det_full["fill_w"]))

    # 35)【铁律47】居中留边判 PASS
    ok_cell = np.zeros((ch_, cw_, 4), np.uint8)
    ok_cell[30:90, 30:90, :3] = 255
    okc_ok, det_ok = containment_check(ok_cell, cw_, ch_, "free")
    ok &= _r("居中留边判 PASS", okc_ok,
             "margin=%s fill_area=%.2f" % (det_ok["margin"], det_ok["fill_area"]))

    # 36)【铁律47】min_fill 拦稀疏（历史 bug：前景占比 0.6% 却放行）
    sparse = np.zeros((ch_, cw_, 4), np.uint8)
    sparse[60:64, 60:64, :3] = 255
    okc_sp, det_sp = containment_check(sparse, cw_, ch_, "free")
    ok &= _r("稀疏(0.1%%面积)判 FAIL", not okc_sp,
             "fill_area=%.4f" % det_sp["fill_area"])

    # 37)【铁律31】缺 centroid_policy 必须报错，不静默默认
    r37 = False
    try:
        containment_check(ok_cell, cw_, ch_, None)
    except ValueError:
        r37 = True
    ok &= _r("缺 centroid_policy 报错", r37)

    # 38)【铁律48】探针计划：先 8 格，全量网格 >= 探针网格
    ans_p = solve(spec)
    pl = probe_plan(ans_p)
    n_probe = pl["n_probe"]
    ok &= _r("探针张数 min(8,N)",
             n_probe == min(8, ans_p["mat_frames"])
             and pl["probe_grid"][0] * pl["probe_grid"][1] >= n_probe,
             "N=%d 探针=%d 探针网格=%s 全量网格=%s"
             % (ans_p["mat_frames"], n_probe, pl["probe_grid"], pl["full_grid"]))

    # 39)【铁律47】真实骨架图集逐格容纳性（端到端，不是合成用例）
    import tempfile as _tf, os as _o3, shutil as _sh
    _d = _tf.mkdtemp()
    try:
        draw_sheet(ans_p, _o3.path.join(_d, "probe"), cw=300, ch=200,
                   cols=pl["probe_grid"][1], rows=pl["probe_grid"][0])
        sheet0 = _o3.path.join(_d, "probe1.png")
        if _o3.path.exists(sheet0):
            okp, detp = probe_check(sheet0, pl["probe_grid"][1],
                                    pl["probe_grid"][0], n_probe, "free")
            ok &= _r("骨架图集容纳性+一致性", okp,
                     "cont=%s area_spread=%s scale_spread=%s color=%s"
                     % (detp["containment_all_pass"], detp["area_spread"],
                        detp["scale_spread"], detp["color_maxdist"]))
        else:
            ok &= _r("骨架图集容纳性+一致性", False, "没产出图集")
    finally:
        _sh.rmtree(_d, ignore_errors=True)

    # 40)【铁律48】探针 FAIL 不许升级（证伪：注入一格空白）
    _d2 = _tf.mkdtemp()
    try:
        sheetp = _o3.path.join(_d2, "p1.png")
        imgp = np.zeros((200 * pl["probe_grid"][0],
                         300 * pl["probe_grid"][1], 3), np.uint8)
        cv2.imwrite(sheetp, imgp)
        okp2, _ = probe_check(sheetp, pl["probe_grid"][1],
                              pl["probe_grid"][0], n_probe, "free")
        ok &= _r("空白探针判 FAIL(不许升级)", not okp2, "全空图集")
    finally:
        _sh.rmtree(_d2, ignore_errors=True)

    return ok
