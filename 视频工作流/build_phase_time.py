#!/usr/bin/env python3
"""出片前置：周期与步态时间参数。
依赖: wind_response _common
被依赖: build_video
改前必读: IMPROVE_build_video.md
铁律: T29 帧数 = 周期×fps，禁手填 / 禁 0.585 硬编码兜底
"""
from wind_response import wind_response as _wr


def flag_period_s(spec):
    """旗帜周期：优先 solver 输出；缺失由数值层按族+特征长度+风速算出。
    禁 0.585 硬编码兜底（旧兜底=1.71Hz 实为 6 级风，套 3 级风即"抖成一片"）。"""
    solver_out = spec.get("solver", {})
    U = float(spec["wind"]["U"])
    if "period_s" not in solver_out:
        _Lf = 2.5
        for _o in spec.get("objects", []):
            if (_o.get("family") or _o.get("族")) == "cloth":
                _Lf = float(_o.get("real_m") or _o.get("长m") or 2.5)
                break
        _wf = _wr("flag", _Lf, U)
        solver_out["period_s"] = _wf["period_s"]
        print("[4c] 旗帜周期由数值层给出: %.3fs (L=%.2fm, U=%.1f) —— 非硬编码"
              % (_wf["period_s"], _Lf, U))
    return float(solver_out["period_s"])


def gait_time(spec):
    """步态：speed = stride / cycle（业界公式），cadence=120/cycle 步/分。"""
    speed = float(spec.get("gait", {}).get("speed_mps", 1.5))
    stride = float(spec.get("gait", {}).get("stride_m", 1.5))
    cycle = stride / speed
    return {"speed": speed, "stride": stride, "cycle": cycle}


def durations(period_flag, cycle, n_flag=35, n_man=30):
    """逐帧时长：均匀切分周期。帧数由采样率决定，禁硬编码帧数。"""
    return [period_flag / n_flag] * n_flag, [cycle / n_man] * n_man
