#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
共振峰测量器 —— 用来客观判断"像不像人声"，不靠耳朵猜
======================================================
方法：LPC 求根法（业界标准，Praat 的 Formant(burg) 同族）

为什么需要它：
  前面几轮我全靠"我觉得机械"来判断，这是不可靠的。
  共振峰位置是可测量的：把合成音的 F1/F2 和
  Peterson & Barney (1952) 的实测元音数据对比，
  差多少赫兹是算得出来的。
"""
import wave

import numpy as np

# Peterson & Barney 1952 —— 男声元音共振峰实测均值（Hz）
PB_MALE = {
    "a": [730, 1090, 2440],   # 啊
    "i": [270, 2290, 3010],   # 衣
    "u": [300, 870, 2240],    # 乌
    "e": [530, 1840, 2480],   # 诶
    "o": [570, 840, 2410],    # 哦
}
PB_FEMALE = {
    "a": [850, 1220, 2810],
    "i": [310, 2790, 3310],
    "u": [370, 950, 2670],
    "e": [610, 2330, 2990],
    "o": [660, 1020, 2870],
}


def lpc_formants(y, sr, order=16, fmax=5000):
    """LPC + 求根 -> 共振峰频率列表"""
    y = np.asarray(y, dtype=np.float64)
    if len(y) < order + 2:
        return []
    # 预加重（补偿声门波谱倾斜，标准做法）
    y = np.append(y[0], y[1:] - 0.97 * y[:-1])
    # 加汉明窗，减少帧边缘不连续
    y = y * np.hamming(len(y))
    N = len(y)
    r = np.correlate(y, y, "full")[N - 1:N + order]
    if r[0] <= 0:
        return []
    # Levinson-Durbin 递推
    a = np.zeros(order + 1)
    a[0] = 1.0
    e = r[0]
    for i in range(1, order + 1):
        num = r[i] + np.dot(a[1:i], r[i - 1:0:-1])
        k = -num / e if e != 0 else 0.0
        a[i] = k
        a[1:i] = a[1:i] + k * a[i - 1:0:-1]
        e *= (1 - k * k)
        if e <= 0:
            break
    roots = np.roots(a)
    out = []
    for z in roots:
        if np.imag(z) > 0.01:
            f = np.arctan2(np.imag(z), np.real(z)) * sr / (2 * np.pi)
            if 90 < f < fmax:
                out.append(f)
    return sorted(out)


def analyze_file(path, frame_ms=30, hop_ms=10, voiced_rms=200):
    """扫全片，返回有声音帧的共振峰轨迹"""
    with wave.open(path) as w:
        sr = w.getframerate()
        y = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    y = y.astype(np.float64)
    fl = int(frame_ms / 1000 * sr)
    hl = int(hop_ms / 1000 * sr)
    tracks = []
    for i in range(0, max(1, len(y) - fl), hl):
        seg = y[i:i + fl]
        if np.sqrt((seg ** 2).mean()) < voiced_rms:
            continue
        fs = lpc_formants(seg, sr)
        if len(fs) >= 2:
            tracks.append((i / sr, fs[:3]))
    return sr, tracks


def compare_to_vowel(fs, vowel, gender="male"):
    """算出与参考值的偏差（Hz 与百分比）"""
    ref = (PB_MALE if gender == "male" else PB_FEMALE).get(vowel)
    if not ref or not fs:
        return None
    out = []
    for j in range(min(3, len(fs))):
        d = fs[j] - ref[j]
        out.append((round(fs[j]), ref[j], round(d), round(d / ref[j] * 100, 1)))
    return out


if __name__ == "__main__":
    import os
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else "audio/纯自然语音.wav"
    if not os.path.exists(p):
        print("找不到", p)
        raise SystemExit(1)
    sr, tracks = analyze_file(p)
    print(f"文件 {p}  sr={sr}  有声帧 {len(tracks)}")
    if not tracks:
        print("  没测到共振峰（可能全是静音，或 LPC 阶数不合适）")
        raise SystemExit(0)

    print(f"\n{'时刻':>7}{'F1':>8}{'F2':>8}{'F3':>8}")
    print("-" * 34)
    for t, fs in tracks[:14]:
        row = "".join(f"{f:>8.0f}" for f in fs)
        print(f"{t:>7.2f}{row}")

    F1s = [f[0] for _, f in tracks if f]
    F2s = [f[1] for _, f in tracks if len(f) > 1]
    print("-" * 34)
    print(f"F1 范围 {min(F1s):.0f}–{max(F1s):.0f} Hz "
          f"  （男声元音 F1 典型 270–850）")
    if F2s:
        print(f"F2 范围 {min(F2s):.0f}–{max(F2s):.0f} Hz "
              f"  （男声元音 F2 典型 840–2290）")
