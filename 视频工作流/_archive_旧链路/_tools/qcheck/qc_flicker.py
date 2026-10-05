#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q_b 闪烁检测。

标准依据（WCAG 一般闪光阈值 / 广播法规 / 两项专利）：
  1) 相对亮度变化 ≥ 10% 满亮度（8bit 下约 20-25 级）
  2) 较暗状态的亮度 < 80%
  3) 一对【相反的转换】（升后降 / 降后升）= 一次闪光
     —— 单次变化【不算】闪烁，这是最容易写错的地方
  4) 1 秒滑动窗口内 3 次闪光 = 失败线（WCAG 与广播同一条线）

专利补充（窄脉冲才是闪屏）：
  ΔLm 的模 > T         -> 一次跳变
  ΔLn * ΔLm < 0        -> 方向相反
  m - n < W 帧         -> 窄脉冲 = 闪屏；宽脉冲不算闪屏

亮度必须归一化：暗区同样的绝对变化，人眼更敏感。
"""
import numpy as np

# 8bit 下 10% 满亮度 ≈ 25 级；归一化后即 0.10
DEFAULT_DELTA = 0.10        # 相对亮度变化阈值
DEFAULT_DARK = 0.80         # 较暗状态上限（占两者较亮者的比例）
DEFAULT_WINDOW = 1.0        # 秒：滑动窗口
DEFAULT_FAIL_N = 3          # 窗口内 3 次 = 失败线


def _pulse_pairs(luma, delta, dark_ratio=DEFAULT_DARK):
    """检测极性反转对：返回 [(i_peak, i_trough, 变化幅度)]。

    算法：找局部极值，相邻异号极值构成一个脉冲，
    幅度 = |极值差|，且较暗一方 / 较亮一方 < dark_ratio 才算（排除整体渐变）。
    """
    n = len(luma)
    if n < 3:
        return []
    d = np.diff(luma)
    pairs = []
    i = 0
    while i < len(d) - 1:
        # 找到一个上升段或下降段的起点
        if abs(d[i]) < delta:
            i += 1
            continue
        sign = 1.0 if d[i] > 0 else -1.0
        j = i
        # 延伸同号段
        while j < len(d) and abs(d[j]) >= delta and (1.0 if d[j] > 0 else -1.0) == sign:
            j += 1
        # 段内累积变化
        amp = luma[min(j, n - 1)] - luma[i]
        # 紧接着必须出现【反向】段，才算一次闪烁
        k = j
        while k < len(d) and abs(d[k]) < delta:
            k += 1
        if k < len(d):
            s2 = 1.0 if d[k] > 0 else -1.0
            if s2 != sign:
                m = k
                while m < len(d) and abs(d[m]) >= delta and \
                        (1.0 if d[m] > 0 else -1.0) == s2:
                    m += 1
                back = luma[min(m, n - 1)] - luma[k]
                hi = max(luma[i], luma[min(j, n - 1)],
                         luma[k], luma[min(m, n - 1)])
                lo = min(luma[i], luma[min(j, n - 1)],
                         luma[k], luma[min(m, n - 1)])
                if hi > 0 and lo / hi < dark_ratio:
                    pairs.append({"t_start": i, "t_peak": min(j, n - 1),
                                  "t_end": min(m, n - 1),
                                  "amp": abs(amp), "amp_back": abs(back)})
                i = m
                continue
        i = j if j > i else i + 1
    return pairs


def detect(src, delta=DEFAULT_DELTA, fps=None,
           window=DEFAULT_WINDOW, fail_n=DEFAULT_FAIL_N):
    """src 可为 Seq，也可直接给 luma 数组。"""
    if hasattr(src, "luma_series"):
        luma = src.luma_series()
        fps = fps or src.fps
    else:
        luma = np.asarray(src, dtype=np.float64)
        fps = fps or 30.0
    pairs = _pulse_pairs(luma, delta)

    # 1 秒滑动窗口内的闪光次数
    wf = int(round(window * fps))
    worst = 0
    worst_t = None
    for t in range(len(luma)):
        c = sum(1 for p in pairs if t <= p["t_start"] < t + wf)
        if c > worst:
            worst, worst_t = c, t
    per_sec = worst / window if window > 0 else float(worst)
    return {"luma": luma.tolist(),
            "pulses": pairs,
            "pulse_count": len(pairs),
            "worst_window_count": worst,
            "worst_window_at": worst_t,
            "per_second": per_sec,
            "fail": worst >= fail_n,
            "threshold": {"delta": delta, "window_s": window, "fail_n": fail_n}}


def self_check():
    ok, bad = [], []
    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    fps = 30.0
    # 1) 稳定亮度：不应报闪烁
    stable = np.full(60, 0.5)
    r = detect(stable, fps=fps)
    add("1 稳定无闪烁", r["pulse_count"] == 0, "脉冲=%d" % r["pulse_count"])

    # 2) 整体渐变（单向）：不算闪烁（无极性反转）
    grad = np.linspace(0.2, 0.8, 60)
    r2 = detect(grad, fps=fps)
    add("2 单向渐变不算闪烁", r2["pulse_count"] == 0, "脉冲=%d" % r2["pulse_count"])

    # 3) 真闪烁：0.5 <-> 0.2 交替
    flick = np.array([0.5 if i % 2 == 0 else 0.2 for i in range(60)], float)
    r3 = detect(flick, fps=fps)
    add("3 交替闪烁被检出", r3["pulse_count"] > 0, "脉冲=%d" % r3["pulse_count"])
    add("4 高频闪烁判失败", r3["fail"], "窗口内=%d" % r3["worst_window_count"])

    # 4) 低频闪烁（1秒1次）：不应判失败
    slow = np.array([0.5 if (i // 15) % 2 == 0 else 0.2 for i in range(120)], float)
    r4 = detect(slow, fps=fps)
    add("5 低频不判失败", not r4["fail"],
        "窗口内=%d 每秒=%.1f" % (r4["worst_window_count"], r4["per_second"]))

    # 5) 微小波动（<阈值）不算
    tiny = 0.5 + 0.02 * np.sin(np.arange(60) * 0.7)
    r5 = detect(tiny, fps=fps)
    add("6 亚阈值波动不算闪烁", r5["pulse_count"] == 0, "脉冲=%d" % r5["pulse_count"])

    print("PASS:")
    for x in ok: print("  " + x)
    if bad:
        print("FAIL:")
        for x in bad: print("  " + x)
    else:
        print("FAIL: 无")
    return not bad


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
