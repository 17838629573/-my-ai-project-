"""中模块 motion —— 跑起来（第三层后段）

一句话：把形体和背景放进相机与时间线，逐帧渲染出片。

契约: proc/motion
  输入: shape 的形体、color 的着色、scene 的烘焙背景、镜头脚本（beat 列表）
  输出: 帧序列与 mp4
  依赖: shape, color, scene
  被依赖: （入口层，无上层）
  约束: 人物与路必须共用同一台相机（px_per_m(Z)），否则"人走的和路不匹配";
        步长由骨架反推并与 0.414×身高 交叉校验，两条独立来源必须吻合;
        支撑脚世界坐标 CV 必须接近 0，否则视为打滑;
        边界帧不许淡入淡出同时为 0（会出现空档）
  校验: python -m motion 或 check.py

小模块:
  camera.py   相机：视高/焦距/px_per_m(Z)/反投影            182 行
  run.py      时间线与出片                                  236 行
  stage.py    场景合成：烘焙 + 人物 + 出片                   299 行
  beat.py     节拍时间线：prep→stroke→relax 串多段动作       355 行
  wind.py     风场：主弯曲 + 细节弯曲（Crysis 式）           134 行
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

__all__ = ["camera", "run", "stage", "beat", "wind"]
