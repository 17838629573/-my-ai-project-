"""把 scene/kit.py (646行) 下沉拆成 scene/kit/ 包下的小模块。"""
import os, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "scene", "kit.py")
lines = open(SRC, encoding="utf-8").read().splitlines()
N = len(lines)

PLAN = [
    ("canvas.py", 28, 94,
     "Canvas 画布 + 噪声基元（value noise / fBm / smoothstep）", []),
    ("sky.py", 96, 172,
     "天空：Perez 天光模型、地平线色、色带 ramp", ["canvas"]),
    ("cloud.py", 174, 194,
     "云：分层 fBm + smoothstep 阈值，coverage 控云量", ["canvas"]),
    ("terrain.py", 197, 257,
     "地形：山脊 midpoint displacement、地面、色带", ["canvas"]),
    ("tree.py", 260, 343,
     "树：Honda 1971 三参数分形（分叉角/长度比/深度）", ["canvas"]),
    ("city.py", 346, 396,
     "城：多排矩形坡顶房屋，越近越大越暗", ["canvas"]),
    ("road.py", 399, 472,
     "路：路面半宽、禁用区间、路面绘制与避让裁剪", ["canvas"]),
    ("place.py", 474, 492,
     "散布占位：草/花/行人（真实实现在 scene.detail）", []),
    ("compose.py", 494, N - 60,
     "场景组合：元件注册表、配方表、compose 总入口", ["canvas", "sky", "cloud",
                                                    "terrain", "tree", "city",
                                                    "road", "place"]),
]
PKG = "scene/kit"
DST = os.path.join(ROOT, "scene", "kit")


def head(fn, one, deps):
    mod = fn[:-3]
    h = [f"# 契约: proc/{PKG}/{mod}", f"#   一句话: {one}",
         f"#   完整契约见 {PKG}/__init__.py", ""]
    h += ["import math", "import numpy as np", "from PIL import Image, ImageDraw"]
    for d in deps:
        h.append(f"from .{d} import *")
    h += ["", ""]
    return "\n".join(h)


os.makedirs(DST, exist_ok=True)
for fn, a, b, one, deps in PLAN:
    body = lines[a - 1:b]
    txt = head(fn, one, deps) + "\n".join(body) + "\n"
    open(os.path.join(DST, fn), "w", encoding="utf-8").write(txt)
    print(f"  {fn:<14} {len(body):>4} 行   ({a}-{b})")

# 自检拆出为独立脚本
sc = lines[587 - 1:N]
open(os.path.join(DST, "selfcheck.py"), "w", encoding="utf-8").write(
    head("selfcheck.py", "自检：python -m kit.selfcheck", []) + "\n".join(sc) + "\n")
print(f"  {'selfcheck.py':<14} {len(sc):>4} 行   (587-{N})")

init = '''"""中模块 scene/kit —— 背景元件库

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
  cloud.py      分层 fBm 云，coverage 控量
  terrain.py    山脊 midpoint displacement、地面
  tree.py       Honda 1971 三参数分形树
  city.py       多排坡顶房屋
  road.py       路面几何与避让裁剪
  place.py      草/花/行人散布占位（实现在 scene.detail）
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
from .cloud import *
from .terrain import *
from .tree import *
from .city import *
from .road import *
from .place import *
from .compose import *

__all__ = [n for n in dir() if not n.startswith("__")]
'''
open(os.path.join(DST, "__init__.py"), "w", encoding="utf-8").write(init)
shutil.move(SRC, os.path.join(ROOT, "_bak", "kit_原646行.py"))
print("\n原文件已归档至 _bak/kit_原646行.py")
