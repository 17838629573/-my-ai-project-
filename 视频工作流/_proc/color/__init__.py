"""中模块 color —— 填色（第二层）

一句话：按胶囊的 region 标签查色卡，配合 SDF 法线做明暗着色。

契约: proc/color
  输入: shape 输出的 capsules（每根带 region）、SDF 距离场、光照方向
  输出: 着色后的 RGBA 画布
  依赖: numpy
  被依赖: motion
  约束: 颜色挂 region 不挂像素（骨架动则颜色跟着动）;
        每档色至少 3~5 级 ramp（暗面→基色→高光），单色会抹平 SDF 立体感;
        色值必须有出处（Fitzpatrick / 传统色），禁止凭记忆硬编码
  校验: python -m color 或 check.py

小模块:
  paint.py   色卡查表与按 region 着色                     139 行
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

__all__ = ["paint"]
