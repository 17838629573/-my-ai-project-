# -*- coding: utf-8 -*-
"""spec —— v2 场景规格唯一来源。

新逻辑（整图关键帧 + global/local 光流 + 首帧锚）：
  人物/树/旗/背景全部由生图一次性画进整图，代码不做分层合成。
  因此 spec 只描述「时间结构」，不描述「空间摆放」。

职责：
  period()    动作周期时长（秒），由 pose 步态求解给出
  keyframes() 一个周期需要几张关键帧（业界：间隔 <= 周期/2）
  interp_mul()相邻关键帧之间插几帧，补齐到目标 fps

禁止：
  - 不得出现像素坐标 / 路径 / 缩放
  - 不得描述人物摆放位置（那是生图提示词的事）
"""
from __future__ import annotations


# ---------- 常量：业界口径 ----------
# 悠闲漫步 0.8~1.1 m/s；普通 1.2~1.4；快走 1.4~1.7（多来源一致）
DEFAULT_SPEED_MPS = 0.95
DEFAULT_STRIDE_M = 0.75

# 关键帧间隔必须 <= 周期/2，否则光流推不出中间相位（业界经验值）
MAX_KEY_INTERVAL_RATIO = 0.5

# 60fps 目标
TARGET_FPS = 60


def period(speed_mps: float = DEFAULT_SPEED_MPS,
           stride_m: float = DEFAULT_STRIDE_M) -> float:
    """一个完整步态周期时长（秒）。

    周期 = 一个双步（heel-to-heel）距离 / 速度
    默认 0.75*2 / 0.95 ≈ 1.579s，落在悠闲档。
    """
    if speed_mps <= 0:
        raise ValueError("speed_mps 必须 > 0")
    if stride_m <= 0:
        raise ValueError("stride_m 必须 > 0")
    return (stride_m * 2.0) / speed_mps


# 业界行走循环常用 4~8 张关键帧覆盖一个周期
DEFAULT_KEYS_PER_CYCLE = 5


def keyframes(period_s: float,
              n: int = DEFAULT_KEYS_PER_CYCLE,
              ratio: float = MAX_KEY_INTERVAL_RATIO) -> int:
    """校验并返回关键帧数。

    硬约束：间隔 <= period * ratio（业界要求不超过半周期，
    否则相邻关键帧处于不同步态相位，光流推不出中间腿部弯曲）。
    n 不合法时返回满足约束的最小值。
    """
    if period_s <= 0:
        raise ValueError("period_s 必须 > 0")
    if not (0 < ratio <= 0.5):
        raise ValueError("ratio 必须在 (0, 0.5]，业界要求间隔不超过半周期")
    min_n = max(3, int(-(-1.0 / ratio // 1)))  # ceil(1/ratio)
    if n is None:
        return min_n
    try:
        n = int(n)
    except (TypeError, ValueError):
        return min_n
    return max(min_n, n)


def key_interval(period_s: float, n_keys: int) -> float:
    """相邻关键帧的时间间隔（秒）。"""
    if n_keys < 2:
        raise ValueError("n_keys 必须 >= 2")
    return period_s / n_keys


def interp_mul(key_interval_s: float, fps: int = TARGET_FPS) -> int:
    """相邻关键帧之间要插多少帧，才能填满到目标 fps。

    返回「总份数 - 1」。例：间隔 0.2s @60fps → 12 帧 → 插 11 帧。
    业界提示：插帧倍数取奇数更稳（3/5/7），偶数易在运动模糊方向冲突。
    """
    if key_interval_s <= 0:
        raise ValueError("key_interval_s 必须 > 0")
    if fps <= 0:
        raise ValueError("fps 必须 > 0")
    total = max(1, round(key_interval_s * fps))
    return max(1, total - 1)


def cycle_frames(period_s: float, fps: int = TARGET_FPS) -> int:
    """一个周期总共多少视频帧。"""
    return max(1, round(period_s * fps))


# ---------- 自检 ----------
def build(speed: float = None, stride: float = None,
          keys: int = None, fps: int = TARGET_FPS) -> dict:
    """统一出口：由速度/步长推出整条时序规格。"""
    sp = DEFAULT_SPEED_MPS if speed is None else speed
    st = DEFAULT_STRIDE_M if stride is None else stride
    per = period(sp, st)
    nk = keyframes(per, DEFAULT_KEYS_PER_CYCLE if keys is None else keys)
    iv = key_interval(per, nk)
    mul = interp_mul(iv, fps)
    return {
        "speed_mps": sp,
        "stride_m": st,
        "period_s": per,
        "n_keys": nk,
        "key_interval_s": iv,
        "interp_mul": mul,
        "fps": fps,
        "cycle_frames": cycle_frames(per, fps),
        "ratio": iv / per,
    }


def self_check() -> None:
    p = period()
    assert abs(p - 1.5789) < 0.01, f"默认周期应约 1.579s，实得 {p}"

    n = keyframes(p, 5)
    assert n == 5, n
    # 间隔必须 <= 半周期
    assert key_interval(p, n) <= p * MAX_KEY_INTERVAL_RATIO + 1e-9

    # 5 张关键帧时，间隔 0.3158s
    iv = key_interval(p, 5)
    assert abs(iv - 0.3158) < 0.01, iv
    assert iv <= p * 0.5 + 1e-9, "间隔超过半周期，光流推不出中间相位"

    m = interp_mul(iv, 60)
    assert m >= 1, m
    # 0.3158s * 60 = 18.9 -> 19 帧 -> 插 18
    assert m == 18, m

    cf = cycle_frames(p, 60)
    assert cf == 95, cf  # 1.5789*60 = 94.7 -> 95

    # 越界必须抛
    for bad, fn in ((0, lambda: period(0)), (1.0, lambda: keyframes(0)),
                    (1.0, lambda: key_interval(1.0, 1)),
                    (1.0, lambda: interp_mul(0, 60))):
        try:
            fn()
            raise AssertionError("应当抛 ValueError")
        except ValueError:
            pass

    print("spec self_check OK  period=%.4fs keys=%d iv=%.4fs mul=%d" % (p, n, iv, m))


if __name__ == "__main__":
    self_check()
