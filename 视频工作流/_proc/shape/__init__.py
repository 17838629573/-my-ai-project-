"""中模块 shape —— 画线（第一层）

一句话：把骨架模板变成带 region 标签的胶囊形体，再出 SDF 场与线稿，全程无色。

契约: proc/shape
  输入: 躯干长 h、模板名(humanoid/quadruped)、手 LOD(0/1/2)、步态相位
  输出: {'joints':{名:(x,y)}, 'capsules':[(ja,jb,r,region)],
         'strokes':[笔画], 'order':[绘制顺序]}
  依赖: numpy
  被依赖: motion
  约束: 胶囊必带 region 标签（颜色挂胶囊不挂像素，杜绝"披帛飘出身体"）;
        手分 L0 单胶囊 / L1 掌+5指 / L2 全指节，默认 L0;
        未知模板报错，不静默跳过
  校验: python -m shape 或 check.py

小模块:
  line.py        骨架模板、胶囊形体、SDF、轮廓线与细节线    213 行
  character.py   【超标 1044 行，已冻结封存，待下沉拆分】旧人物实现
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

__all__ = ["line"]
