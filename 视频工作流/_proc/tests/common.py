#   契约: 测试公共层 —— 常量、世界坐标换算、节拍对齐，供 cases_base/run_all 共享。
#   完整契约见 tests/__init__.py
#   依据: 几何量统一世界坐标米制（避免归一化单位与米混用导致的判据错配）；
#         摘自检讨记录：run_all 超纲 609>500 后按「公共辅助 / 用例体 / 驱动」三层拆分。
# -*- coding: utf-8 -*-
"""35 项用例门检与执行（测试第三步：跑）

契约: tests/run_all
  输入: tests/cases.CASES、beat.CAP
  输出: 每项状态 STUB / READY / PASS / FAIL + 实测值
  依赖: tests/cases  tests/harness  motion.beat  motion.character.*
  被依赖: 无（终端入口）
  约束: 需求能力不在 CAP → 一律 STUB 并附 search_hint，绝不降级成 walk；
        每条判据阈值来自 harness.CRIT（有出处），不许就地拍数
"""
import os
import sys
import json

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

import numpy as np
import harness as H
from cases import CASES

import motion.beat as B
import motion.rigid
import motion.rigid2d  # noqa: F401  (注册 stack / ramp / pendulum)
from tests.cases_phys import (  # noqa: F401
    case_C16, case_C17, case_C18, case_C19, case_C20,
)
from tests.cases_crowd import case_D21, case_D24  # noqa: F401
from tests.cases_throw import case_B10, case_B11  # noqa: F401
from tests.cases_carry import case_E26  # noqa: F401
from tests.cases_pass import case_D22  # noqa: F401
for _m in ("gait", "gesture", "prop", "sit", "turn", "jump", "crouch", "run", "carry", "hand", "kick", "ball", "pass_ball", "climb"):
    try:
        __import__("motion.character." + _m)
    except Exception:
        pass

OUT = ROOT
H_M = 1.70          # 身高（米），归一化单位 → 米
CYCLE = 1.122       # 一个完整周期行程（米）= 2 × step_len 0.561


def _world(J, ph, gv=0.0):
    """关节归一化 (u,v,w) → 世界 (x, h, z) 米。u 前向 + 周期推进

    地面标定: gait 的 v=0 不是地面, 脚跟着地点在 v=GROUND_V(实测 0.0282)。
    不减去则"最低关节离地"恒 ≈4.8cm, 浮空判据必误报
    (ReinDiffuse 判据: 脚接触地面时垂直位移应≈0)。
    """
    out = {}
    adv = CYCLE * ph          # 本周期内已推进的世界距离
    for k, a in J.items():
        u, v, w = float(a[0]), float(a[1]), float(a[2])
        out[k] = (adv + u * H_M, (v - gv) * H_M, w * H_M)
    return out



def _align_n(t_total, bounds, fps=60.0):
    """取帧数使相位边界恰落在整数帧上（消除顶点测量的离散化偏移）"""
    n0 = int(round(t_total * fps))
    for n in range(max(8, n0 - 4), n0 + 400):
        if all(abs((b / t_total) * n - round((b / t_total) * n)) < 1e-9
               for b in bounds):
            return n + 1
    return n0 + 1

