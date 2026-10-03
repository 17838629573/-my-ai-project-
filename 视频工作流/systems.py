"""systems：常量与编排。已拆出 systems_selfcheck / systems_phys / systems_view（见 IMPROVE_systems.md）"""
"""
可启停系统集合 —— 配合 LoopEngine 按需调度
==================================================
每个系统实现 init/update 两个函数：
  init(ctx)          首次启用时才调用（惰性初始化，省启动开销）
  update(ctx, i, t)  每帧调用；未启用则不进入

【实测耗时（540x960）】
  动画     0.01 ms
  物理     3.09 ms
  合成     4.01 ms
  字幕     0.58 ms（有文字）/ 0.01 ms（无文字，提前返回）
"""
import math
import os
import sys
import cv2
import numpy as np
from skeleton_runtime import Skeleton, apply_animation, mat_apply
import physics as ph
import physics_rules as pr
import framerate
from framerate import FPS
class Ctx:
    """渲染上下文：系统之间共享状态"""

    def __init__(self, W, H):
        self.W, self.H = W, H
        self.canvas = None
        self.bg = None
        self.skeleton = None
        self.anim = None
        self.parts = {}
        self.subtitle_text = ""
        self.subtitle_px = None
        self.bg_speed = 0.0
        self.frame_out = None
from systems_phys import init_physics, update_physics, update_movables
from systems_view import update_composite, update_subtitle, _make_subtitle_rgba
def init_skeleton(ctx):
    """惰性初始化骨架 —— 只有需要动画的镜头才付这个成本"""
    # 【关键】落点由 photo_rules 反算，不再写死居中 + 0.94H
    root_x = getattr(ctx, "char_x", None)
    if root_x is None:
        root_x = ctx.W // 2
    else:
        root_x = root_x + getattr(ctx, "char_w", int(ctx.H * 0.42)) // 2
    root_y = getattr(ctx, "ground_y", None) or int(ctx.H * 0.94)
    data = {
        "bones": [
            {"name": "root", "x": int(root_x), "y": int(root_y)},
            {"name": "hip", "parent": "root", "x": 0, "y": -170},
            {"name": "torso", "parent": "hip", "x": 0, "y": -10},
            {"name": "head", "parent": "torso", "x": 0, "y": -80},
            {"name": "legL", "parent": "hip", "x": -16, "y": 0},
            {"name": "legR", "parent": "hip", "x": 16, "y": 0},
            {"name": "armL", "parent": "torso", "x": -34, "y": -60},
            {"name": "armR", "parent": "torso", "x": 34, "y": -60},
        ],
        "slots": [
            # 槽位序遵循契约: leg→arm→torso→head，索引大者在上
            # （躯干盖肩根，头在最上）。初版 armR 排在 torso 之后，
            #  导致右臂盖住躯干 —— 与契约不一致
            {"name": "legL", "bone": "legL"},
            {"name": "legR", "bone": "legR"},
            {"name": "armL", "bone": "armL"},
            {"name": "armR", "bone": "armR"},
            {"name": "torso", "bone": "torso"},
            {"name": "head", "bone": "head"},
        ],
        "skins": {"default": {
            "legL": {"legL": {"x": 0, "y": 85, "path": "legL"}},
            "legR": {"legR": {"x": 0, "y": 85, "path": "legR"}},
            "armL": {"armL": {"x": 0, "y": 60, "path": "armL"}},
            "armR": {"armR": {"x": 0, "y": 60, "path": "armR"}},
            "torso": {"torso": {"x": 0, "y": -80, "path": "torso"}},
            "head": {"head": {"x": 0, "y": -30, "path": "head"}},
        }},
    }
    ctx.skeleton = Skeleton(data, img_loader=lambda p: ctx.parts.get(p))
REAL_HEIGHT_M = 1.70
STRIDE_RATIO = 0.45
STEP_LENGTH_M = REAL_HEIGHT_M * STRIDE_RATIO
CADENCE_SPM = 120
STEPS_PER_SEC = CADENCE_SPM / 60.0
WALK_PERIOD = 2.0 / STEPS_PER_SEC
PLAYRATE_CLAMP = (0.85, 1.15)
def step_px(char_px):
    """由人物像素高反算步距像素 —— 步距与人物大小必须同源"""
    return STEP_LENGTH_M * (char_px / REAL_HEIGHT_M)
def scroll_per_frame(char_px, fps=None):
    """
    每帧背景位移 = 步距像素 × 步频 / 输出帧率
    一循环走 2 步，故每秒位移 = 步距 × STEPS_PER_SEC。

    铁律28：fps 必须显式传入或取 framerate.FPS，禁止默认 60（会形成第二帧率源）。
    """
    if fps is None:
        import framerate as fr
        fps = fr.FPS
    return step_px(char_px) * STEPS_PER_SEC / fps
def matched_playrate(actual_speed_px_s, char_px, clamp=PLAYRATE_CLAMP):
    """
    【Distance Matching 业界实现】
    目标播放速率 = 实际位移速度 / 动画自带速度。
    结果必须钳制在 ±15-20%；超出说明动画与移动速度根本不匹配，
    此时业界建议【容忍少量打滑】，而不是把播放速率拉爆。
    返回 (playrate, clamped:bool)
    """
    authored = step_px(char_px) * STEPS_PER_SEC      # 动画自带位移速度
    if authored <= 1e-9:
        return 1.0, False
    raw = actual_speed_px_s / authored
    lo, hi = clamp
    pr = max(lo, min(hi, raw))
    return pr, abs(pr - raw) > 1e-6
WALK_POSE_TABLE = [
    # phase,  leg_amp, body_lift,  姿态
    (0.000,  0.00,  0.0),    # F1  Contact A  接触·中位
    (0.125, -0.55, -1.0),    # F2  Down    A  下沉·最低
    (0.250,  0.00,  0.3),    # F3  Passing A  过渡·回升
    (0.375,  0.55,  1.0),    # F4  Up      A  上升·最高
    (0.500,  0.00,  0.0),    # F5  Contact B（F1 镜像）
    (0.625,  0.55, -1.0),    # F6  Down    B（F2 镜像）
    (0.750,  0.00,  0.3),    # F7  Passing B（F3 镜像）
    (0.875, -0.55,  1.0),    # F8  Up      B（F4 镜像）
]
POSE_NAMES = ["Contact", "Down", "Passing", "Up",
              "Contact'", "Down'", "Passing'", "Up'"]
def _walk_pose(phase01):
    """
    按相位在姿态表间线性插值 -> (腿摆系数, 身体升降)
    经搜索: 业界明确要求腿部用【线性】插值, 在每个关键姿态加缓动会让脚"犹豫"
    (hyperPad/ArtStudio 走路教程原文: Begin with Linear interpolation for the leg
     movement; strong easing at every contact makes the character hesitate)
    """
    tbl = WALK_POSE_TABLE
    for i in range(len(tbl)):
        a = tbl[i]
        b = tbl[(i + 1) % len(tbl)]
        hi = b[0] if b[0] > a[0] else b[0] + 1.0
        if a[0] <= phase01 < hi:
            u = (phase01 - a[0]) / max(1e-9, hi - a[0])
            return a[1] + (b[1] - a[1]) * u, a[2] + (b[2] - a[2]) * u
    return 0.0, 0.0
COM_V_RATIO = 0.012
HEAD_STEADY = 0.35
def com_vertical_amp(char_px):
    """重心垂直单侧振幅(像素) = 人物像素高 × 1.8%"""
    return char_px * COM_V_RATIO
def update_animation(ctx, i, t):
    """
    走路动画：8 帧标准循环 + 步距锁相 + 双腿反相。
    【关键】左右脚都动（legL/legR 反相），不是只动一只脚。
    """
    if ctx.skeleton is None:
        return

    phase01 = (t % WALK_PERIOD) / WALK_PERIOD
    leg_amp, body_lift = _walk_pose(phase01)

    pose = {}
    amp = 24.0
    # 双腿反相：一条前摆时另一条后摆
    pose["legL"] = {"rot": leg_amp * amp, "x": 0, "y": 0}
    pose["legR"] = {"rot": -leg_amp * amp, "x": 0, "y": 0}
    # 手臂与腿反向摆动（行业标准）
    pose["armL"] = {"rot": -leg_amp * amp * 0.6, "x": 0, "y": 0}
    pose["armR"] = {"rot": leg_amp * amp * 0.6, "x": 0, "y": 0}
    # 身体上下起伏：按身高比例，非固定像素（修正"一蹦一蹦"）
    v_amp = com_vertical_amp(getattr(ctx, "char_px", 480))
    pose["hip"] = {"rot": 0.0, "x": 0.0, "y": body_lift * v_amp}
    # 头部反向补偿，保持相对稳定（业界: keep the head comparatively steady）
    if "head" in getattr(ctx.skeleton, "bones", {}):
        pose["head"] = {"rot": 0.0, "x": 0.0,
                        "y": -body_lift * v_amp * HEAD_STEADY}

    ctx.skeleton.pose.clear()
    ctx.skeleton.pose.update(pose)

    # 锁相：背景滚动由步距反算，不再用硬编码 bg_speed
    if getattr(ctx, "walk_locked", False):
        ctx.bg_scroll_accum = getattr(ctx, "bg_scroll_accum", 0.0) + \
            scroll_per_frame(getattr(ctx, "char_px", 480), getattr(ctx, "fps", 60))
CLOTH_ROWS, CLOTH_COLS = 8, 6
import re as _re
_INLINE_PAT = [
    (r"0\.5\s*\*\s*\w*\s*\*\s*\w*\s*\*\s*\w*\s*\*\s*(v|mag|speed)\s*\*\*\s*2", "内联 F=0.5*rho*Cd*A*v^2"),
    (r"\*\*\s*\(?\s*2\.0?\s*/\s*3\.0?", "内联 A=k*V^(2/3)"),
    (r"=\s*9\.8\b", "内联重力常量 9.8"),
    (r"1\.225", "内联空气密度 1.225"),
]
_MAGIC_PAT = r"\*\s*(1e-[0-9]|0\.00[0-9])\b"
if __name__ == "__main__":
    _ok, _ = self_check()
    sys.exit(0 if _ok else 1)


def self_check(verbose=True):
    from systems_selfcheck import self_check as _f
    return _f()
