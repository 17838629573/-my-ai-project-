#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
占位音轨生成器（业界称 scratch track / prelay）
================================================
作用：在最终配音到位前，先造一条"时长正确"的临时音轨，
      让画面去匹配它。画面时长由声音反推，不是拍脑袋。

占位音轨只需要一件事是对的：**时长**。
音色不重要 —— 后续整体替换即可，帧数不用改。

生成方式：按台词的音节结构造包络，不做真实语音合成。
"""
import wave
import struct
import math
import os
import numpy as np
from typing import List

SR = 44100


def synth_line(dur_ms: int, seed: int = 0, syl: int = 6) -> np.ndarray:
    """
    造一条时长精确、有明显音节起伏的占位音轨。
    不是语音，是"节奏骨架" —— 用来看清口型切换点在哪。
    """
    n = int(dur_ms / 1000.0 * SR)
    t = np.arange(n, dtype=np.float32) / SR
    rng = np.random.default_rng(seed)

    # 基频（男声量级）
    f0 = 110 + rng.uniform(-15, 15)
    # 音节包络：syl 个峰
    env = np.zeros(n, dtype=np.float32)
    seg = n / syl
    for i in range(syl):
        s, e = int(i * seg), int((i + 1) * seg)
        x = np.linspace(0, math.pi, max(1, e - s))
        env[s:e] = np.sin(x) ** 0.6
    # 句尾收束
    tail = max(1, n // 12)
    env[n - tail:] *= np.linspace(1, 0, tail)

    # 谐波叠加，听感接近人声
    sig = np.zeros(n, dtype=np.float32)
    for h, amp in [(1, 1.0), (2, 0.42), (3, 0.22), (5, 0.10)]:
        sig += amp * np.sin(2 * math.pi * f0 * h * t)
    sig = sig / (np.abs(sig).max() + 1e-9)

    # 爆破音：在音节起点加短脉冲（对应 M5 闭合）
    for i in range(syl):
        p = int(i * seg)
        L = min(int(0.012 * SR), n - p)
        if L > 0:
            sig[p:p + L] += 0.5 * np.random.default_rng(seed + i).standard_normal(L) \
                            * np.linspace(1, 0, L)

    out = sig * env
    out = out / (np.abs(out).max() + 1e-9) * 0.72
    return out


def write_wav(path: str, data: np.ndarray, sr: int = SR):
    pcm = (np.clip(data, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return os.path.getsize(path)


def concat_wav(paths: List[str], out: str):
    frames = []
    for p in paths:
        with wave.open(p) as w:
            frames.append((w.getnchannels(), w.getsampwidth(),
                           w.getframerate(), w.readframes(w.getnframes())))
    with wave.open(out, "w") as w:
        w.setnchannels(frames[0][0])
        w.setsampwidth(frames[0][1])
        w.setframerate(frames[0][2])
        for _, _, _, d in frames:
            w.writeframes(d)
    return os.path.getsize(out)


def duration_ms(path: str) -> float:
    with wave.open(path) as w:
        return w.getnframes() / float(w.getframerate()) * 1000.0


# 台词表：由短ID编码表 V0-V4 驱动
LINES = [
    ("V0", "动手打人可以治安拘留", 2400, 11),
    ("V1", "没出事的时候",         1100, 6),
    ("V2", "安全员都是坏人",       1300, 7),
    ("V3", "（停顿）",             600,  0),
    ("V4", "出了事呢",             900,  4),
]

if __name__ == "__main__":
    from typing import List
    d = os.path.dirname(os.path.abspath(__file__))
    os.makedirs(os.path.join(d, "audio"), exist_ok=True)

    print("=" * 58)
    print("占位音轨生成  ·  scratch track")
    print("=" * 58)

    parts = []
    total_ms = 0.0
    print(f"\n{'ID':<5}{'台词':<22}{'目标ms':>8}{'实际ms':>9}{'误差':>7}")
    for vid, text, dur, syl in LINES:
        p = os.path.join(d, "audio", f"{vid}.wav")
        sig = synth_line(dur, seed=hash(vid) % 1000, syl=max(1, syl))
        write_wav(p, sig)
        real = duration_ms(p)
        total_ms += real
        parts.append(p)
        err = real - dur
        print(f"{vid:<5}{text:<22}{dur:>8}{real:>9.1f}{err:>7.1f}")

    full = os.path.join(d, "audio", "全片.wav")
    sz = concat_wav(parts, full)
    real_total = duration_ms(full)
    print(f"\n合计 {real_total:.0f}ms = {real_total/1000:.1f}s "
          f"= {round(real_total/1000*60)} 帧 @60fps")
    print(f"输出 {full}  ({sz/1024:.0f}KB)")

    # 校验：时长必须与编码表一致（否则摄影表全错）
    ok = all(abs(duration_ms(os.path.join(d, "audio", f"{v}.wav")) - dur) < 5
             for v, _, dur, _ in LINES)
    print(f"\n时长校验：{'PASS（误差<5ms，摄影表可信）' if ok else 'FAIL'}")
