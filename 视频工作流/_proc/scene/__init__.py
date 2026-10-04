"""中模块 scene —— 背景（第三层前段）

一句话：烘焙不动的背景（天空/山/城/路），提供近处细节与元件模板。

契约: proc/scene
  输入: 场景层序（如 sky→cloud→mountain→ground→city→road）、seed、LOD 档
  输出: RGBA 背景画布 + geom{'horizon_y','vanish_x','road_far_y','road_near_y',...}
  依赖: numpy（kit 依赖 detail）
  被依赖: motion
  约束: 背景烘焙一次、全片冻结（帧间差必须为 0，否则视为闪烁 bug）;
        路必须把自己的几何写进 ctx，房子/树要避让路面（不许压在路中间）;
        散布用位置哈希而非每帧随机，否则白噪声团簇 + 闪烁
  校验: python -m scene 或 check.py

小模块:
  kit.py      元件库：天空/云/山/树/草/花/城/路           642 行【超标，待下沉】
  detail.py   近处细节：草叶/窗户/叶簇/行人                408 行
  bgpack.py   背景包：五种配方的参数表与展开                385 行
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

__all__ = ["kit", "detail", "bgpack"]
