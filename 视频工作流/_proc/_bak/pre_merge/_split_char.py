"""把 motion/character.py (1048行) 下沉拆成 motion/character/ 包下的 8 个小模块。"""
import os, shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "motion", "character.py")
lines = open(SRC, encoding="utf-8").read().splitlines()

# (文件名, 起行, 止行, 一句话职责, 内部依赖列表)  行号 1-based 闭区间
PLAN = [
    ("sdf.py", 28, 67,
     "SDF 场原语：胶囊/圆/椭圆/平滑并集，形体的数学底座", []),
    ("proportions.py", 69, 133,
     "人体比例常数（Drillis&Contini 1966）与步频/步态常量", []),
    ("joints.py", 135, 248,
     "关节表、躯干摆动常量、步态预设与 gait_params", ["proportions"]),
    ("leg.py", 249, 392,
     "腿：两骨 IK、踝高曲线、脚掌俯仰与脚部关键点", ["proportions", "joints"]),
    ("gait.py", 393, 560,
     "步态主函数：臂摆、膝屈曲线、相位推进与 BODY_SPEC", ["proportions", "joints", "leg"]),
    ("render.py", 561, 726,
     "渲染：相机投影、SDF 场栅格化、法线明暗着色", ["sdf", "proportions", "joints", "leg", "gait"]),
    ("cloth.py", 727, 857,
     "布料：Verlet 链、披帛/衣摆、draw_character 总入口", ["render"]),
    ("selfcheck.py", 858, len(lines),
     "自检脚本：python -m character.selfcheck", ["sdf", "proportions", "joints",
                                                 "leg", "gait", "render", "cloth"]),
]
PKG = "motion/character"
DST = os.path.join(ROOT, "motion", "character")

COMMON = ["import math", "import numpy as np"]
PIL = ["from PIL import Image, ImageDraw"]


def head(fn, one, deps):
    mod = fn[:-3]
    h = [f"# 契约: proc/{PKG}/{mod}", f"#   一句话: {one}",
         f"#   完整契约见 {PKG}/__init__.py", ""]
    h += COMMON
    for d in deps:
        h.append(f"from .{d} import *")
    if fn in ("render.py", "cloth.py", "selfcheck.py"):
        h += PIL
    if fn == "render.py":
        h.append("from motion import camera")
    h += ["", ""]
    return "\n".join(h)


os.makedirs(DST, exist_ok=True)
for fn, a, b, one, deps in PLAN:
    body = lines[a - 1:b]
    txt = head(fn, one, deps) + "\n".join(body) + "\n"
    with open(os.path.join(DST, fn), "w", encoding="utf-8") as fh:
        fh.write(txt)
    print(f"  {fn:<16} {len(body):>4} 行   ({a}-{b})")

# __init__.py：薄壳 re-export，保证 `import character as C` 旧写法仍可用
init = '''"""中模块 motion/character —— 人物（L-C 每帧全算层）

一句话：用 SDF 场构造人物形体（不做部件拼接）+ 步态驱动 + 布料二级运动。

契约: proc/motion/character
  输入: 画布、镜头参数、身高像素、步态相位、风矢量、dt
  输出: 绘制好的人物；gait() 返回关节字典
  依赖: motion.camera, scene.kit(仅自检用)
  被依赖: motion.run, motion.stage, motion.beat
  约束: 步长必须与 0.414×身高 交叉校验（两条独立来源）;
        支撑脚世界坐标 CV≈0（打滑即 bug）; 脚掌角由实测关键点插值，禁止对称正弦;
        披帛根必须抓在肩关节上，禁止固定像素偏移（否则飘出身体）
  校验: python -m character.selfcheck

小模块（依赖单向，自上而下）:
  sdf.py          SDF 场原语：胶囊/圆/椭圆/平滑并集
  proportions.py  人体比例常数与步频常量
  joints.py       关节表、躯干摆动、步态预设
  leg.py          腿：两骨 IK、踝高、脚掌俯仰
  gait.py         步态主函数与 BODY_SPEC
  render.py       投影、场栅格化、法线着色
  cloth.py        Verlet 链与 draw_character 入口
  selfcheck.py    自检脚本
"""
from .sdf import *
from .proportions import *
from .joints import *
from .leg import *
from .gait import *
from .render import *
from .cloth import *

__all__ = [n for n in dir() if not n.startswith("_")]
'''
with open(os.path.join(DST, "__init__.py"), "w", encoding="utf-8") as fh:
    fh.write(init)

shutil.move(SRC, os.path.join(ROOT, "_bak", "character_原1048行.py"))
print("\n原文件已归档至 _bak/character_原1048行.py")
