#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
拼接式合成器 · PSOLA —— 走游戏走过的那条路
====================================================
【这一版的思路来源：搜索 + 实测，不是凭空设计】

问：游戏十几年来是怎么做语音的？是不是只能找真人录？
答：绝大多数确实是真人录。AAA 项目工会配音预算 $300K–$800K。
    但还有两条"自己搞"的路，都是有据可查的工业实践：

  ① 拼接合成 / 基元选择（Pre-neural 的业界标准）
     · 录一套语料库（5–50 小时），覆盖所有双音素(diphone)
     · 用 Viterbi 选最优单元序列，用 PSOLA 平滑拼接点
     · 代表系统：MBROLA / ProVerbe / HADIFIX / Festival
     · 关键：PSOLA 不是合成方法，它让【预录样本】能被平滑拼接，
       并精确控制音高与时长 —— 这正是"录一次、用一辈子"的技术基础

  ② 程序化语音（Nintendo 的 Animalese）
     · 文本逐字符 → 查表取短音素样本 → 按角色音高变调回放
     · 优点：无限扩展，任何文本都能"发声"，无需逐句录音
     · 代价：不可懂。任天堂是【主动接受】这个代价的
       （400+ 村民 × 数千句台词，录音不现实）

【本文件走路线 ①，用 espeak 当"录音棚"】
    录一次 = 用 espeak 把每个音节生成一遍，存成语料库
    用一辈子 = 之后所有合成都从库里取单元，用 PSOLA 改调改时长

【为什么这比上一版的自研共振峰有希望】
    上一版音色的上限卡在"共振峰合成"这个方法上。
    这一版音色仍来自 espeak（没变），但【韵律】完全由我控制：
      · 声调曲线用自己的实测值
      · 时长自己定
      · 拼接点用基元同步平滑（PSOLA 的核心价值）
    PSOLA 变调时【保持频谱包络】—— 这是它优于普通重采样的地方。
"""
import ctypes
import glob
import os
import re
import wave

import numpy as np

SR_RAW = 22050          # espeak 输出
OUT_SR = 24000          # 对齐格式规范闸

# ---------------------------------------------------------------- 声调
# 相对基频曲线（1.0 = 该音色基准）
TONE = {
    "55": [(0.0, 1.00), (1.0, 1.00)],                    # 阴平 高平
    "35": [(0.0, 0.78), (1.0, 1.18)],                    # 阳平 升
    "214": [(0.0, 0.74), (0.42, 0.60), (1.0, 0.98)],     # 上声 降升
    "51": [(0.0, 1.18), (1.0, 0.66)],                    # 去声 降
    "11": [(0.0, 0.80), (1.0, 0.72)],                    # 轻声 短低
}
# 各声调时长系数（上声最长、轻声最短，符合普通话实测）
TONE_DUR = {"55": 1.00, "35": 1.05, "214": 1.30, "51": 0.95, "11": 0.60}
BASE_DUR = 0.230        # 基准音节时长（秒）


class Voice:
    def __init__(self, name, f0=115, f0_span=1.0, rate=1.0,
                 pitch_shift=1.0):
        self.name = name
        self.f0 = f0
        self.f0_span = f0_span      # 声调起伏幅度
        self.rate = rate
        self.ps = pitch_shift       # 整体变调（女声>1）


VOICES = {
    "A": Voice("成熟男声·沉稳", f0=112, f0_span=1.00, rate=1.00),
    "B": Voice("洪亮男声·粗犷", f0=96,  f0_span=1.25, rate=0.92),
    "C": Voice("年轻男声·清亮", f0=140, f0_span=1.10, rate=1.08),
    "D": Voice("女声",          f0=205, f0_span=1.05, rate=1.00, pitch_shift=1.12),
    "E": Voice("播报腔·标准",   f0=125, f0_span=0.85, rate=1.05),
}


# ---------------------------------------------------------------- espeak
def _load_espeak():
    import piper_phonemize
    pkg = os.path.dirname(piper_phonemize.__file__)
    lib = glob.glob(os.path.join(pkg + ".libs", "libespeak-ng*.so*"))[0]
    L = ctypes.CDLL(lib)
    L.espeak_Initialize.argtypes = [ctypes.c_int, ctypes.c_int,
                                    ctypes.c_char_p, ctypes.c_int]
    L.espeak_Initialize.restype = ctypes.c_int
    L.espeak_SetVoiceByName.argtypes = [ctypes.c_char_p]
    L.espeak_TextToPhonemes.restype = ctypes.c_char_p
    L.espeak_TextToPhonemes.argtypes = [ctypes.POINTER(ctypes.c_char_p),
                                        ctypes.c_int, ctypes.c_int]
    sr = L.espeak_Initialize(1, 500, os.path.join(pkg, "espeak-ng-data").encode(), 0)
    L.espeak_SetVoiceByName(b"cmn")
    return L, sr


def g2p(text, L):
    buf = ctypes.c_char_p(text.encode("utf-8"))
    ptr = ctypes.cast(ctypes.pointer(buf), ctypes.POINTER(ctypes.c_char_p))
    r = L.espeak_TextToPhonemes(ptr, 1, 0)
    return r.decode("utf-8", "replace") if r else ""


def tones_of(text, L):
    """
    返回逐字声调列表（与文本汉字一一对应）

    【实测 bug】第一版用 lookahead `(\\d+)(?=[^a-zA-Z]*_|\\||\\s|$)`，
    结果 10 个字只认出 6 个调：
      · 'a55n_ 的 55 后面跟字母 n → lookahead 失败
      · kho-214j'i214 前一个 214 后面跟字母 j → 失败
    不能靠音节边界切 —— espeak 会把多个字并进一个 _| 组
    （实测 'tong51s.\\'ou214_|' 里就挤了「动」「手」两个字）。

    正确做法：直接抓调号本身。cmn 的调号是 55/35/214/51/11 这几个固定值。
    """
    ph = g2p(text, L)
    return re.findall(r"(214|55|35|51|11)", ph)


# ---------------------------------------------------------------- PSOLA
def _autocorr_period(seg, sr, fmin=60, fmax=500):
    seg = seg - np.mean(seg)
    if np.sqrt((seg ** 2).mean()) < 1e-6:
        return 0
    c = np.correlate(seg, seg, "full")[len(seg) - 1:]
    lo, hi = max(1, int(sr / fmax)), min(len(c) - 1, int(sr / fmin))
    if hi <= lo:
        return 0
    k = lo + int(np.argmax(c[lo:hi]))
    return k


def pitch_marks(y, sr, win=0.030, hop=0.015):
    """
    基音标记：在每个分析窗内估周期，然后在信号上按周期推进打点。
    这是 TD-PSOLA 的第一步，也是最容易出错的一步 ——
    窗长必须 >= 2 个周期，否则估不准。
    """
    W = int(win * sr)
    H = int(hop * sr)
    periods = []
    for i in range(0, max(1, len(y) - W), H):
        p = _autocorr_period(y[i:i + W], sr)
        periods.append(p)
    # 用中位数填掉估错的窗（清音/过渡段）
    pv = np.array(periods, dtype=float)
    good = pv[pv > 0]
    if len(good) == 0:
        return np.array([]), 0
    med = np.median(good)
    pv[pv <= 0] = med
    pv = np.maximum(pv, 1.0)

    marks = []
    t = 0.0
    idx = 0
    while t < len(y) - 1:
        marks.append(int(t))
        wi = min(len(pv) - 1, int(t / H))
        t += pv[wi]
        idx += 1
        if idx > 20000:
            break
    return np.array(marks, dtype=int), med


def psola(y, sr, f0_contour, target_dur):
    """
    TD-PSOLA：按目标基频曲线与时长重合成。
      f0_contour: (N,2) 或 callable(u)->Hz
      target_dur: 秒
    变调保持频谱包络 —— 这是 PSOLA 相对普通重采样的核心价值。
    """
    y = np.asarray(y, dtype=np.float64)
    marks, med_p = pitch_marks(y, sr)
    if len(marks) < 4:
        # 基音标记不可靠 -> 退化为线性重采样（至少时长对）
        n_out = max(1, int(target_dur * sr))
        idx = np.linspace(0, len(y) - 1, n_out)
        return np.interp(idx, np.arange(len(y)), y)

    # 目标基音标记：按目标 F0 推进
    tmarks = []
    t = 0.0
    n_target = int(target_dur * sr)
    while t < n_target:
        tmarks.append(t)
        u = t / max(1.0, n_target)
        f = f0_contour(u)
        t += sr / max(40.0, f)
        if len(tmarks) > 20000:
            break
    tmarks = np.array(tmarks)

    if len(tmarks) < 2:
        return np.zeros(n_target)

    out = np.zeros(n_target + int(sr * 0.05))
    W = 2.0                       # 窗 = 2 个周期（文献推荐 2–4）
    # 源段循环取用：目标比源长就循环，短就跳过 —— 这是时长修改的机制
    for k, tm in enumerate(tmarks):
        si = marks[k % len(marks)]
        # 当前分析窗的周期
        cur_p = marks[(k + 1) % len(marks)] - marks[k % len(marks)]
        if k + 1 >= len(marks):
            cur_p = med_p
        if cur_p <= 1:
            cur_p = med_p
        wl = max(8, int(W * cur_p))
        a = si - wl // 2
        b = si + wl // 2
        seg = np.zeros(wl)
        sa, sb = max(0, a), min(len(y), b)
        if sb > sa:
            seg[sa - a:sa - a + (sb - sa)] = y[sa:sb]
        win = np.hanning(wl)
        seg = seg * win
        # 放到目标位置
        oa = int(tm) - wl // 2
        ob = oa + wl
        if oa < 0:
            seg = seg[-oa:]
            oa = 0
        if ob > len(out):
            seg = seg[:len(out) - oa]
            ob = len(out)
        if ob > oa and len(seg) == ob - oa:
            out[oa:ob] += seg
    return out[:n_target]


def contour_fn(tone, voice):
    pts = TONE.get(tone, TONE["55"])
    f0 = voice.f0 * voice.ps

    def f(u):
        # 线性插值声调曲线
        if u <= pts[0][0]:
            r = pts[0][1]
        elif u >= pts[-1][0]:
            r = pts[-1][1]
        else:
            r = pts[-1][1]
            for i in range(len(pts) - 1):
                x0, y0 = pts[i]
                x1, y1 = pts[i + 1]
                if x0 <= u <= x1:
                    r = y0 + (y1 - y0) * (u - x0) / max(1e-6, x1 - x0)
                    break
        return f0 * (1.0 + (r - 1.0) * voice.f0_span)

    return f


# ---------------------------------------------------------------- 语料库
class Corpus:
    """音节语料库 —— 对应游戏"录一次"的那一步"""

    def __init__(self):
        from 成熟TTS_espeak import EspeakNG
        self.tt = EspeakNG(voice="cmn", rate=None)
        # 【实测 bug】不要自己再 espeak_Initialize 一次：
        # 二次初始化会污染状态 —— 实测「打」返回 0ms，而单独调用时是 5939 样本。
        # 正确做法：复用 EspeakNG 已建好的同一个 lib handle。
        self.L = self.tt.L
        self.L.espeak_TextToPhonemes.restype = ctypes.c_char_p
        self.L.espeak_TextToPhonemes.argtypes = [ctypes.POINTER(ctypes.c_char_p),
                                                 ctypes.c_int, ctypes.c_int]
        self.sr = self.tt.sr
        self.cache = {}

    def get(self, ch):
        if ch in self.cache:
            return self.cache[ch]
        y = np.asarray(self.tt.synth(ch), dtype=np.float64)
        self.cache[ch] = y
        return y


# ---------------------------------------------------------------- 合成
def _resample(x, sr0, sr1):
    n = int(len(x) * sr1 / sr0)
    return np.interp(np.linspace(0, len(x) - 1, n), np.arange(len(x)), x)


def synth_line(text, voice="A", corpus=None, gap_ms=45):
    """
    逐字：取语料库单元 -> PSOLA 套声调曲线与时长 -> 拼接
    """
    v = VOICES.get(voice, VOICES["A"])
    c = corpus or Corpus()
    sr = c.sr
    tones = tones_of(text, c.L)

    chars = [ch for ch in text if "\u4e00" <= ch <= "\u9fff"]
    if len(tones) < len(chars):
        tones = tones + ["55"] * (len(chars) - len(tones))
    tones = tones[:len(chars)]

    # 三声变调 214+214 -> 35+214
    for i in range(len(tones) - 1):
        if tones[i] == "214" and tones[i + 1] == "214":
            tones[i] = "35"

    segs = []
    for ch, tn in zip(chars, tones):
        unit = c.get(ch)
        dur = BASE_DUR * TONE_DUR.get(tn, 1.0) / max(0.3, v.rate)
        y = psola(unit, sr, contour_fn(tn, v), dur)
        # 首尾软化，避免拼接爆音
        n = max(1, int(0.012 * sr))
        if len(y) > 2 * n:
            env = np.ones(len(y))
            env[:n] = np.linspace(0, 1, n)
            env[-n:] = np.linspace(1, 0, n)
            y = y * env
        segs.append(y)
        segs.append(np.zeros(int(gap_ms / 1000 * sr)))

    out = np.concatenate(segs) if segs else np.zeros(1)
    out = _resample(out, sr, OUT_SR)
    pk = np.abs(out).max()
    if pk > 0:
        out = out / pk * 0.89
    return out, OUT_SR, list(zip(chars, tones))


def write_wav(path, y, sr=OUT_SR):
    pcm = np.clip(y * 32767, -32768, 32767).astype(np.int16)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


# ---------------------------------------------------------------- 度量
def f0_track(y, sr, win=0.030, hop=0.010):
    """
    自相关 F0 跟踪 —— 实测对纯音 100/150/220Hz 完全准确。

    【实测 bug】第一版用绝对阈值 300 判静音，但合成输出是归一化到
    [-0.89, 0.89] 的浮点数（RMS ≈ 0.16），全部低于 300 →
    每一帧都被判成静音 → F0 全测成 0，误以为"PSOLA 输出是空音频"。
    实际 PSOLA 输出正常（RMS 4546 vs 源 5607，衰减来自加窗，合理）。
    改为相对阈值：以全片 RMS 的 15% 为门限。
    """
    y = np.asarray(y, dtype=np.float64)
    W = int(win * sr)
    H = int(hop * sr)
    grms = np.sqrt((y ** 2).mean()) if len(y) else 0.0
    thr = max(1e-9, grms * 0.15)
    out = []
    for i in range(0, max(1, len(y) - W), H):
        s = y[i:i + W] - np.mean(y[i:i + W])
        if np.sqrt((s ** 2).mean()) < thr:
            out.append(0.0)
            continue
        cc = np.correlate(s, s, "full")[W - 1:]
        lo, hi = int(sr / 500), int(sr / 60)
        seg = cc[lo:hi]
        if len(seg) == 0:
            out.append(0.0)
            continue
        k = lo + int(np.argmax(seg))
        out.append(sr / k if k > 0 else 0.0)
    raw = np.array(out)

    # 【实测发现】自相关 argmax 会出倍频/半频错误：
    # 143 帧里有 30 帧落在 250–600Hz（真值 112 的 2×/4×），
    # 把 F0 跨度从 ~56Hz 夸大到 341Hz，看着像"韵律失控"。
    # 修法：以全片中位为锚，把偏离超过 1.5 倍的值折半/折三归位。
    v = raw[raw > 0]
    if len(v) == 0:
        return raw
    med = np.median(v)
    fixed = raw.copy()
    for i, f in enumerate(raw):
        if f <= 0:
            continue
        g = f
        while g > med * 1.5 and g > 60:
            g /= 2.0
        while g < med * 0.6:
            g *= 2.0
        fixed[i] = g
    return fixed


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="动手打人可以治安拘留")
    ap.add_argument("--voice", default="A")
    ap.add_argument("--out", default=None)
    ap.add_argument("--all-voices", action="store_true")
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()

    if a.verify:
        c = Corpus()
        print(f"=== 单元时长（语料库）===")
        for ch in a.text:
            if "\u4e00" <= ch <= "\u9fff":
                y = c.get(ch)
                print(f"  {ch}  {len(y)/c.sr*1000:>6.0f}ms")
        print(f"\n=== 声调识别 ===")
        tn = tones_of(a.text, c.L)
        print(" ", a.text, "->", tn)
        raise SystemExit(0)

    os.makedirs("audio", exist_ok=True)
    if a.all_voices:
        c = Corpus()
        print(f"{'ID':<4}{'音色':<18}{'时长ms':>8}{'F0中位':>8}{'F0跨度':>8}")
        print("-" * 48)
        for k, v in VOICES.items():
            y, sr, pairs = synth_line(a.text, k, corpus=c)
            p = f"audio/PSOLA_{k}.wav"
            write_wav(p, y, sr)
            tr = f0_track(y, sr)
            vv = tr[tr > 0]
            f0m = np.median(vv) if len(vv) else 0
            span = np.percentile(vv, 90) - np.percentile(vv, 10) if len(vv) > 10 else 0
            print(f"{k:<4}{v.name:<18}{len(y)/sr*1000:>8.0f}{f0m:>8.0f}{span:>8.0f}")
        raise SystemExit(0)

    c = Corpus()
    y, sr, pairs = synth_line(a.text, a.voice, corpus=c)
    out = a.out or "audio/PSOLA_输出.wav"
    write_wav(out, y, sr)
    print(f"音色 {VOICES[a.voice].name}  时长 {len(y)/sr*1000:.0f}ms -> {out}")
    print("字-调:", " ".join(f"{c}/{t}" for c, t in pairs))
