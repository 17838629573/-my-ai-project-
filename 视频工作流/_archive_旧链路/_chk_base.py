"""solver 自检公共层：共享 import + _r 断言器。

依赖: solver_survey / _solver_* / physics / anchor / framerate
被依赖: _chk_*.py（各检查域子模块）
改进措施记录: IMPROVE_solver_check.md（改前必读）
"""
import os
import math
import json
import tempfile
import numpy as np
import cv2
import framerate
from solver_survey import (
    DRIVE_SOURCES, EXAMPLES, HOWTO, KINDS, PART_ROLES, SLOT_TEMPLATE,
    assemble, briefing_text, inventory, survey,
)
from _solver_base import MAX_MAT_FRAMES, wind_sign
# 铁律89：自检直接依赖真实算法模块，不走 solver facade（破 solver<->selfcheck 环）
# 修复：solve 原未导入，self_check 第1项即 NameError，56 项从未真正跑通
from _solver_chain import (
    amp_over_L, chain_response, chain_response_multi,
    flag_lift_deg, frame_durations, loop_seam_ratio, solve,
    transient_envelope,
)
from _solver_probe import containment_check, probe_check, probe_plan
from _solver_reuse import additive_offset, layer_plan, reuse_plan
from _solver_run import run_spec
from _solver_sheet import draw_sheet, sheet_layout, sheet_plan
import physics
import anchor


# 共享测试 spec：各检查域自包含所需的物理输入（ctx 未传时兜底）
# 唐绢 62 g/m2、旗 0.90x0.30 m、U=12.3 m/s（AI 搜证值，勿随意改）
BASE_SPEC = {"family": "cloth",
             "geometry": {"L": 0.90, "W": 0.30, "t": 2.0e-4},
             "material": {"sigma": 0.062, "E": 5.0e9, "nu": 0.34},
             "fluid": {"U": 12.3},
             "criteria": {"regime_by": "mu",
                          "mu_stable": 0.02, "mu_chaotic": 0.30}}


def _src_of(*names):
    """读取 solver 系真实逻辑模块源码（禁扫 __file__：子模块自指会空转）。"""
    out = []
    for n in names:
        p = n if n.endswith(".py") else n + ".py"
        try:
            out.append(open(p, encoding="utf-8").read())
        except OSError:
            pass
    return "\n".join(out)


SOLVER_MODULES = (
    "_solver_base", "_solver_chain", "_solver_chain_aux", "_solver_geom",
    "_solver_probe", "_solver_reuse", "_solver_run", "_solver_sheet",
    "solver_survey", "solver",
)
SOLVER_SRC = _src_of(*SOLVER_MODULES)


def _strip_examples(src):
    """逐文件剔除全部 BEGIN/END EXAMPLES 区（拼接后跨文件错配会漏剔）。"""
    out, i = [], 0
    while True:
        lo = src.find("BEGIN EXAMPLES", i)
        if lo < 0:
            out.append(src[i:])
            break
        hi = src.find("END EXAMPLES", lo)
        if hi < 0:
            out.append(src[i:])
            break
        out.append(src[i:lo])
        i = hi + len("END EXAMPLES")
    return "".join(out)


SOLVER_LOGIC = _strip_examples(SOLVER_SRC)


def _logic_src(src):
    """剔除 BEGIN/END EXAMPLES 示例区（示例允许写死物体名）。"""
    lo = src.find("BEGIN EXAMPLES")
    hi = src.find("END EXAMPLES")
    if lo >= 0 and hi > lo:
        return src[:lo] + src[hi:]
    return src



def _r(name, cond, note=""):
    print(("PASS " if cond else "FAIL ") + name + ("  " + note if note else ""))
    return cond
