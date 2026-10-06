# -*- coding: utf-8 -*-
# 契约: G 组用例体（ADDITIVE 叠加层污染检测）。
#   完整契约见 tests/__init__.py
#   依据: 用例体与驱动分离，避免 run_all 单文件超纲（R2 >500）；
#         自 cases_base.py 迁出（其 509 行超红线），判据与实现同处一文件便于核对。
from .common import *          # noqa: F401,F403  常量


def _g36_series(name, kw, N, gait, gesture, layer):
    """单个 additive 能力的 base/over 两条序列（N 帧 gait + 上层叠加）。"""
    fn = getattr(gesture, name)
    base = [gait.gait(i / (N - 1), "natural") for i in range(N)]
    over = [layer.blend(base[i], fn(i / (N - 1), kw),
                        region="upper", mode="additive", layer_w=1.0)
            for i in range(N)]
    return base, over


def _g36_lower_pollution(base, over, N, layer):
    """下半身污染量：additive 只作用上半身，LOWER 区必须逐帧零偏差。"""
    worst = 0.0
    for i in range(N):
        for jn in layer.LOWER:
            if jn in base[i] and jn in over[i]:
                dv = max(abs(over[i][jn][k] - base[i][jn][k]) for k in range(3))
                worst = max(worst, dv)
    return worst


def _g36_upper_delta(base, over, N, layer):
    """上半身叠加生效量：over 相对 base 的最大位移（必须 > 0 才算真的叠加）。"""
    pairs = [(i, jn) for i in range(N) for jn in layer.UPPER
             if jn in base[i] and jn in over[i]]
    return max(max(abs(over[i][jn][k] - base[i][jn][k]) for k in range(3))
               for i, jn in pairs)


def _g36_jump_ratio(base, over, N, layer):
    """帧间一致性比值：叠加后帧间步长 / 叠加前帧间步长（应 ≈1，不引入跳变）。"""
    b_d = max(max(abs(base[i + 1][jn][k] - base[i][jn][k]) for k in range(3))
              for i in range(N - 1) for jn in layer.UPPER if jn in base[i])
    pairs = [(i, jn) for i in range(N - 1) for jn in layer.UPPER
             if jn in base[i] and jn in over[i]]
    o_d = max(max(abs(over[i + 1][jn][k] - over[i][jn][k]) for k in range(3))
              for i, jn in pairs)
    return o_d / max(b_d, 1e-12)


def case_G36():
    """ADDITIVE 三能力接线：gaze_shift / finger_tap / page_flip 叠加到 gait

    接线依据: UE Layered Blend per Bone — additive 层只作用于 mask 覆盖的骨骼，
    下半身必须零污染；分界点选腰部(waist)，选骨盆太靠下手臂混合不彻底。
    """
    import importlib
    gait = importlib.import_module("motion.character.body.gait")
    gesture = importlib.import_module("motion.character.gesture")
    from motion import layer
    from tests import harness as H

    ADDS = (("gaze_shift", {"yaw": 1.0}),
            ("finger_tap", {"side": "right", "reps": 2}),
            ("page_flip", {"side": "right"}))
    N = 48
    worst_lower = 0.0
    worst_ratio = 0.0
    for name, kw in ADDS:
        base, over = _g36_series(name, kw, N, gait, gesture, layer)
        worst_lower = max(worst_lower,
                          _g36_lower_pollution(base, over, N, layer))
        moved = _g36_upper_delta(base, over, N, layer)
        assert moved > 1e-4, f"{name}: additive 未生效 (上半身位移 {moved})"
        worst_ratio = max(worst_ratio, _g36_jump_ratio(base, over, N, layer))
    return [
        ("lower_pollution", worst_lower),
        ("frame_jump_ratio", worst_ratio),
    ], {"能力数": len(ADDS), "帧数": N}
