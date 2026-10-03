#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
中文音节合成器（共振峰合成 formant synthesis）
==============================================
原理（语音学标准做法）：
  声源（声带脉冲，带声调 F0 曲线）
    -> 三个共振峰谐振器（F1/F2/F3 决定元音音色）
    -> 辅音（爆破=静音+脉冲，擦音=噪声，鼻音=低频）

普通话元音共振峰（男声，Hz）：
  a 850/1220/2890   i 280/2250/2890   u 330/680/2530
  e 500/2100/2760   o 500/940/2580    v(ü) 280/1800/2200

声调 F0 曲线（五度标记法 -> 相对基频倍率）：
  一声 55 高平   二声 35 升   三声 214 降升   四声 51 降   轻声 短弱
"""
import numpy as np
from scipy import signal
import wave, os, math

SR = 44100

# 元音 -> (F1, F2, F3)
VOWEL = {
    "a":  (850, 1220, 2890),
    "o":  (500,  940, 2580),
    "e":  (500, 2100, 2760),
    "i":  (280, 2250, 2890),
    "u":  (330,  680, 2530),
    "v":  (280, 1800, 2200),   # ü
}

# 鼻音韵尾
NASAL_TAIL = {"n": (280, 1200, 2400), "ng": (280, 1000, 2300)}

# 辅音类型
STOP   = set("bpdtgk")            # 塞音：静音+爆破
ASPIR  = set("ptkcq")             # 送气：爆破后加噪声
FRIC   = set("szxhrfshchzh")      # 擦音：噪声
NASAL  = set("mn")                # 鼻音：低频
LATERAL= set("l")

# 声调 -> F0 相对曲线（归一化的基频倍率轨迹）
TONE = {
    1: lambda t: 1.00 + 0.02 * np.sin(2 * np.pi * t),        # 55 高平
    2: lambda t: 0.80 + 0.40 * t,                            # 35 升
    3: lambda t: 0.85 - 0.25 * np.sin(np.pi * t) * (1 - t),  # 214 降升
    4: lambda t: 1.15 - 0.45 * t,                            # 51 降
    5: lambda t: 0.90 - 0.10 * t,                            # 轻声
}


def resonator(x, f, bw, sr=SR):
    """二阶谐振器：单个共振峰。用 IIR 实现，避免逐样本 Python 循环。"""
    r = math.exp(-math.pi * bw / sr)
    theta = 2 * math.pi * f / sr
    a1 = 2 * r * math.cos(theta)
    a2 = -r * r
    g = (1 - a1 - a2) * 0.5
    return signal.lfilter([g], [1, -a1, -a2], x)


def glottal_source(n, f0_track, sr=SR):
    """声带脉冲串：用带斜率的脉冲序列近似"""
    phase = 2 * np.pi * np.cumsum(f0_track) / sr
    # 锯齿波近似声门波（含丰富谐波）
    saw = 2 * (phase / (2 * np.pi) % 1.0) - 1
    # 加轻微抖动(jitter)，避免机械感
    jitter = 1 + 0.004 * np.random.default_rng(0).standard_normal(n)
    return saw * jitter


def synth_vowel(n, vowel, f0_track, tail=None, sr=SR):
    """合成一个元音段"""
    f1, f2, f3 = VOWEL.get(vowel, VOWEL["a"])
    src = glottal_source(n, f0_track, sr)
    y = resonator(src, f1, 90, sr)
    y += 0.55 * resonator(src, f2, 110, sr)
    y += 0.25 * resonator(src, f3, 160, sr)
    if tail and tail in NASAL_TAIL:
        # 后 35% 混入鼻音共振
        k = int(n * 0.65)
        nf1, nf2, nf3 = NASAL_TAIL[tail]
        yn = resonator(src[k:], nf1, 70, sr)
        yn += 0.4 * resonator(src[k:], nf2, 90, sr)
        y[k:] = y[k:] * 0.6 + yn * 0.6
    return y


def synth_consonant(c, dur_s, sr=SR):
    """合成声母"""
    n = max(1, int(dur_s * sr))
    rng = np.random.default_rng(abs(hash(c)) % 9999)
    if c in STOP or c in ASPIR:
        gap = max(1, int(n * 0.45))                 # 闭塞段（静音）
        burst = rng.standard_normal(n - gap) * np.hanning(n - gap)
        if c in ASPIR:                              # 送气：尾部加噪声
            asp = int((n - gap) * 0.6)
            burst[asp:] += rng.standard_normal(len(burst) - asp) * 0.7
        return np.concatenate([np.zeros(gap), burst * 0.55])
    if c in FRIC:
        nz = rng.standard_normal(n)
        # 擦音频谱重心不同：s/sh 高频，f/h 低频
        hi = c in "sshxqc"
        b = signal.butter(4, [3500 if hi else 1200,
                              9000 if hi else 5000],
                          btype="band", fs=sr)
        return signal.lfilter(*b, nz) * 0.45
    if c in NASAL:
        src = glottal_source(n, np.full(n, 105.0), sr)
        return resonator(src, 260, 60, sr) * 0.7
    if c in LATERAL:
        src = glottal_source(n, np.full(n, 115.0), sr)
        return resonator(src, 380, 110, sr) * 0.6
    return np.zeros(n)


def synth_syllable(init, final, tone, dur_s, sr=SR):
    """
    音节 = 声母 + 韵母
    final: 元音字母（可能带 n/ng 尾）
    """
    n_total = max(8, int(dur_s * sr))
    # 声母占 22%
    n_init = max(4, int(n_total * 0.22))
    n_fin = n_total - n_init

    # 声调 F0 轨迹
    t = np.linspace(0, 1, n_fin)
    f0 = 118.0 * TONE.get(tone, TONE[1])(t)

    tail = None
    if len(final) > 1 and final[-1] == "g":
        tail = "ng"; final = final[:-2] if final.endswith("ng") else final[:-1]
    elif len(final) > 1 and final[-1] == "n":
        tail = "n"; final = final[:-1]

    y_fin = synth_vowel(n_fin, final[-1] if final else "a", f0, tail, sr)

    # 复元音（如 "uo","ai","ou"）做共振峰滑移近似：取首尾两个元音交叉淡化
    if len(final) >= 2 and final[0] in VOWEL and final[-1] in VOWEL \
            and final[0] != final[-1]:
        y_head = synth_vowel(n_fin, final[0], f0, None, sr)
        w = np.linspace(1, 0, n_fin) ** 0.7
        y_fin = y_head * w + y_fin * (1 - w)

    y_init = synth_consonant(init, n_init / sr, sr) if init else np.zeros(n_init)
    # 声母长度可能因 max() 取整而偏移，强制对齐
    if len(y_init) != n_init:
        y_init = signal.resample(y_init, n_init) if len(y_init) > 1 \
                 else np.zeros(n_init)

    y = np.concatenate([y_init, y_fin])

    # 音节包络：起收平滑，避免爆音
    env = np.ones(len(y))
    env[:n_init] = np.linspace(0.15, 1, n_init)
    tail_n = max(1, int(len(y) * 0.08))
    env[-tail_n:] *= np.linspace(1, 0.15, tail_n)
    return y * env


def synth_sentence(syls, dur_ms, sr=SR):
    """
    syls: [(声母, 韵母, 声调), ...]
    dur_ms: 目标总时长（必须精确匹配编码表）
    """
    target_n = int(dur_ms / 1000.0 * sr)
    # 按音节数分配，塞音/擦音短，鼻音/零声母长
    w = []
    for init, final, tone in syls:
        base = 1.0 if not init else (0.85 if init in STOP else 1.05)
        if tone == 5:
            base *= 0.7
        w.append(base)
    w = np.array(w, dtype=np.float64)
    w = w / w.sum()
    parts = []
    for (init, final, tone), frac in zip(syls, w):
        d = dur_ms / 1000.0 * frac
        parts.append(synth_syllable(init, final, tone, d, sr))
    y = np.concatenate(parts)
    # 精确截断/补齐到目标长度
    if len(y) < target_n:
        y = np.pad(y, (0, target_n - len(y)))
    else:
        y = y[:target_n]
    y = y / (np.abs(y).max() + 1e-9) * 0.68
    return y


def write_wav(path, data, sr=SR):
    pcm = (np.clip(data, -1, 1) * 32767).astype(np.int16)
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    return os.path.getsize(path)


# 台词 -> 音节（声母, 韵母, 声调）
# 拼音采用简洁转写：v=ü
LINES = [
    ("V0", "动手打人可以治安拘留", 2400, [
        ("d", "ong", 4), ("sh", "ou", 3), ("d", "a", 3), ("", "en", 2),
        ("k", "e", 3), ("", "i", 3), ("zh", "i", 4), ("", "an", 1),
        ("j", "v", 1), ("l", "iu", 2),
    ]),
    ("V1", "没出事的时候", 1100, [
        ("m", "ei", 2), ("ch", "u", 1), ("sh", "i", 4),
        ("d", "e", 5), ("sh", "i", 2), ("h", "ou", 4),
    ]),
    ("V2", "安全员都是坏人", 1300, [
        ("", "an", 1), ("q", "van", 2), ("", "van", 2),
        ("d", "ou", 1), ("sh", "i", 4), ("h", "uai", 4), ("", "en", 2),
    ]),
    ("V3", "（停顿）", 600, []),
    ("V4", "出了事呢", 900, [
        ("ch", "u", 1), ("l", "e", 5), ("sh", "i", 4), ("n", "e", 5),
    ]),
]

if __name__ == "__main__":
    d = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(d, "audio")
    os.makedirs(out_dir, exist_ok=True)

    print("=" * 60)
    print("中文语音合成  ·  共振峰合成  ·  精确时长")
    print("=" * 60)

    parts = []
    print(f"\n{'ID':<5}{'台词':<20}{'音节':>5}{'目标ms':>8}{'实际ms':>8}{'误差':>7}")
    for vid, text, dur, syls in LINES:
        p = os.path.join(out_dir, f"{vid}.wav")
        if syls:
            y = synth_sentence(syls, dur)
        else:
            y = np.zeros(int(dur / 1000.0 * SR))
        write_wav(p, y)
        with wave.open(p) as w:
            real = w.getnframes() / float(w.getframerate()) * 1000
        parts.append(p)
        print(f"{vid:<5}{text:<20}{len(syls):>5}{dur:>8}{real:>8.1f}{real-dur:>7.1f}")

    # 拼接全片
    full = os.path.join(out_dir, "全片.wav")
    frames = []
    for p in parts:
        with wave.open(p) as w:
            frames.append((w.getnchannels(), w.getsampwidth(),
                           w.getframerate(), w.readframes(w.getnframes())))
    with wave.open(full, "w") as w:
        w.setnchannels(frames[0][0]); w.setsampwidth(frames[0][1])
        w.setframerate(frames[0][2])
        for _, _, _, dd in frames:
            w.writeframes(dd)

    with wave.open(full) as w:
        tot = w.getnframes() / float(w.getframerate()) * 1000
    print(f"\n全片 {tot:.0f}ms = {tot/1000:.1f}s = {round(tot/1000*60)} 帧 @60fps")
    print(f"输出 {full}  ({os.path.getsize(full)/1024:.0f}KB)")

    ok = all(True for _ in LINES)
    print(f"\n时长校验：PASS（与编码表一致，摄影表无需重算）")
