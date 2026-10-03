#!/usr/bin/env python
"""_loopspec.py — 循环资产规范（游戏业界 cycle animation 标准）

依赖: math
被依赖: build_util, rain_layer, pose_prompt
铁律113: 循环动画帧数下限 = 覆盖完整周期的一秒（业界 24-32 帧/cycle）
铁律114: 序列禁止 duplicate_endpoint（末帧=首帧会造成播放停顿一帧）
铁律115: 循环闭合判据 = 末帧→首帧的跳变 == 单帧增量（不是"末帧==首帧"）
铁律116: 雨/粒子不逐帧生图，走 N 张 tileable 贴图 + 程序化动画（业界天气系统）

改前必读: IMPROVE_loopspec.md
"""
import math

# 业界 cycle animation 帧数区间（来源: 2D 游戏动画通行规范）
MIN_FRAMES_PER_CYCLE = 24   # 下限：低于此值动作割裂/机械
MAX_FRAMES_PER_CYCLE = 32   # 上限：超出后每帧差异过小，性价比骤降


def frames_for_cycle(cycle_s, fps=None):
    """覆盖完整周期的帧数，且不含重复端点（铁律114）。

    业界：walking cycle 24-32 帧 @24-30fps = 一秒一步。
    返回 N，使得 N 帧以 playrate=N/cycle_s 播放时正好一秒走完一步。
    """
    fps = int(fps) if fps else _default_fps(cycle_s)
    n = int(round(cycle_s * fps))
    n = max(MIN_FRAMES_PER_CYCLE, min(MAX_FRAMES_PER_CYCLE, n))
    return n


def _default_fps(cycle_s):
    """默认帧率：让一秒周期的帧数落在业界区间内。"""
    return 30 if cycle_s >= 0.8 else 60


def playrate_for(n_frames, cycle_s):
    """播放帧率 = 帧数 / 周期秒数。N 帧播完正好一个周期（铁律113）。"""
    if cycle_s <= 0:
        raise ValueError("cycle_s 必须 > 0，收到 %r" % (cycle_s,))
    return round(float(n_frames) / float(cycle_s), 3)


def phase_map(n, include_endpoint=False):
    """每帧相位（弧度）。include_endpoint=False 保证循环闭合（铁律114）。"""
    if include_endpoint:
        raise ValueError(
            "铁律114: 循环序列禁止含重复端点（末帧=首帧会停顿一帧）。"
            "若要取 N+1 点作图，请自行 append 首点，不要改本函数。")
    return [2.0 * math.pi * i / float(n) for i in range(n)]


def loop_closure_error(seq, tol=None):
    """循环闭合误差：末帧→首帧的跳变 与 典型单帧增量 的比值。

    铁律115：正确判据是「末帧→首帧的跳变 == 单帧增量」，
    不是「末帧 == 首帧」（后者是 duplicate_endpoint 的错判据）。
    返回 (error_ratio, 是否闭合)。ratio≈1.0 表示均匀闭合。
    """
    n = len(seq)
    if n < 3:
        raise ValueError("序列至少 3 帧，收到 %d" % n)
    diffs = [abs(seq[i + 1] - seq[i]) for i in range(n - 1)]
    wrap = abs(seq[0] - seq[-1])          # 末帧绕回首帧
    # 参照=末帧局部增量（支撑贴地等常量段局部增量≈0，此时 wrap≈0 才是正确闭合）
    k = min(4, len(diffs))
    local = sum(diffs[-k:]) / float(k)
    eps = max((max(seq) - min(seq)) * 1e-3, 1e-9)
    # 常量段（支撑贴地）：local≈0 且 wrap≈0 是自然接续，不是断裂
    if local < eps and wrap < eps:
        return 0.0, True
    ref = max(local, eps)
    ratio = wrap / ref
    lo, hi = (0.1, 3.0) if tol is None else (1.0 / tol, tol)
    return ratio, (lo <= ratio <= hi)


def rain_tile_sheets(n_layers=4, tiles_per_layer=6):
    """雨的循环贴图规范（铁律116）。

    业界天气系统：不逐帧生雨，而是生成少量可平铺(tileable)的雨贴图，
    靠多层叠加 + 不同速度的程序化滚动产生无限变化。
    返回每层的张数与排布，交给生图模块。
    """
    if not 2 <= n_layers <= 6:
        raise ValueError("雨层数 2-6，收到 %r" % (n_layers,))
    if not 3 <= tiles_per_layer <= 8:
        raise ValueError("每层贴图 3-8 张，收到 %r" % (tiles_per_layer,))
    return {
        "layers": n_layers,
        "tiles_per_layer": tiles_per_layer,
        "total_tiles": n_layers * tiles_per_layer,
        "kind": "tileable",
        "bg": "transparent",          # 透明底，直接叠加
        "animation": "programmatic",  # 程序化滚动，非逐帧生图
        "note": "每层用不同速度/方向滚动，叠加后产生无限变化（业界天气系统标准）",
    }


def self_check():
    n = frames_for_cycle(1.0)
    assert 24 <= n <= 32, n
    pr = playrate_for(n, 1.0)
    assert abs(pr - n) < 1e-6

    ph = phase_map(n)
    assert len(ph) == n
    assert abs(ph[0]) < 1e-12
    assert ph[-1] < 2.0 * math.pi, "末帧不得等于 2π（重复端点）"

    # 闭合：正弦序列末→首跳变 == 单帧增量
    s = [math.sin(p) for p in ph]
    ratio, ok = loop_closure_error(s)
    assert ok and ratio < 2.0, (ratio, ok)

    # 证伪1：duplicate_endpoint 末==首，跳变=0 -> 应判不闭合（停顿）
    bad = [math.sin(2 * math.pi * i / (n - 1)) for i in range(n)]
    r2, ok2 = loop_closure_error(bad)
    assert not ok2, "重复端点序列应判不闭合"
    # 证伪2：断裂序列（末帧远离首帧）-> 应判不闭合
    brk = [math.sin(p) for p in ph[:-1]] + [5.0]
    r3, ok3 = loop_closure_error(brk)
    assert not ok3, "断裂序列应判不闭合"
    print("  cycle=1.0s -> frames=%d playrate=%.1f  闭合ratio=%.2f" % (n, pr, ratio))
    print("  证伪(重复端点): ratio=%.2f closed=%s" % (r2, ok2))
    print("  证伪(断裂):     ratio=%.2f closed=%s" % (r3, ok3))

    rt = rain_tile_sheets()
    assert rt["kind"] == "tileable" and rt["animation"] == "programmatic"
    assert rt["total_tiles"] == 24
    print("  雨循环贴图: %d层 x %d张 = %d" % (
        rt["layers"], rt["tiles_per_layer"], rt["total_tiles"]))
    print("_loopspec OK")


if __name__ == "__main__":
    self_check()
