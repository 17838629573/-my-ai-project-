"""中模块 scene/kit —— 背景元件库

一句话：把天空/云/山/树/城/路等背景元件烘焙成一张冻结的背景画布，并输出 geom 供人物对齐。

契约: proc/scene/kit
  输入: 场景层序（sky→cloud→mountain→ground→city→road）、seed、LOD 档、画布尺寸
  输出: RGBA 画布 + geom{'horizon_y','vanish_x','road_far_y','road_near_y','road_half_near',...}
  依赖: numpy, PIL
  被依赖: motion.camera, motion.stage, motion.character(自检)
  约束: 背景烘焙一次全片冻结，帧间差必须为 0（非 0 即闪烁 bug）;
        路必须把半宽写进 ctx，房子/树用 road_ban 避让，不许压在路中间;
        散布用位置哈希而非每帧随机，否则白噪声团簇 + 闪烁;
        pivot 必须在元件底部中心，否则物体浮在地面上方半个身位
  校验: python -m kit.selfcheck

小模块（依赖单向，自上而下）:
  canvas.py     画布与噪声基元（value noise / fBm / smoothstep）
  sky.py        Perez 天光、地平线色、色带 ramp
  terrain.py    山脊 midpoint displacement、地面
  tree.py       Honda 1971 三参数分形树
  city.py       多排坡顶房屋
  road.py       路面几何与避让裁剪
  compose.py    元件注册表、配方表、compose 总入口
  selfcheck.py  自检脚本
"""
import os
import sys
_P = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _P not in sys.path:
    sys.path.insert(0, _P)

from .canvas import *
from .sky import *
from .terrain import *
from .tree import *
from .road import *
from .city import *
from .compose import *

__all__ = [n for n in dir() if not n.startswith("__")]
