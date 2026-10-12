# 契约: proc/tools/measure
#   一句话: 测量类工具子包：有效帧率(R15)、能力可驱动性审计、动作质量指标。
#   完整契约见 tools/__init__.py
#   依据: 与「判定类」工具分开——测量的产出是数值，判定的产出是 PASS/FAIL；
#         两类混在同一层会让 tools 直接成员数超 R4 上限 20。
# -*- coding: utf-8 -*-
"""测量类工具（从 tools/ 顶层下沉，避免 tools 包成员超 R4 上限）。

  efps.py       R15 有效帧率：渲染 N 帧 ≠ 画面动了 N 帧
  capaudit.py   能力可驱动性审计（口径须走 capbridge.normalize）
  motionqual.py 动作质量指标：ZMP/抖动/自穿透/接触F1/步态与游动波长
"""

from . import capaudit, efps, motionqual          # noqa: F401
