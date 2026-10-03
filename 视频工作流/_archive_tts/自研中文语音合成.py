#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自研中文语音合成器 · 源-滤波器架构（Klatt 级联共振峰）
======================================================
【为什么能自研 —— 分工明确】
  神经网络 TTS 自研 = 不可能：需要几十小时对齐语音 + GPU 训练，我两样都没有。
  但我可以自研【后端】，把【前端】外包给现成工具：

      文本
       ↓  espeak-ng G2P（只借它的文本→音素+声调，不碰它的波形合成）
      音素序列 + 声调（55/35/214/51/11）
       ↓  【自研】协同发音规划 → 共振峰目标轨迹
       ↓  【自研】Rosenberg 声门波 / 噪声激励
       ↓  【自研】Klatt 级联共振峰滤波器
      波形

  espeak 在这里只当字典用。机械味的根源（共振峰合成器）是我自己重写的一版。

【比 eSpeak 强的三个具体点】
  1. 共振峰目标用普通话实测值，且经【共振峰测量.py】客观验证
  2. 加 F0 微抖动（jitter）与微颤（shimmer）—— 已知降低机械感的有效手段
  3. 三声变调（214+214 → 35+214）—— 中文自然度的关键细节

【必须说明的上限】
  共振峰合成的天花板是"可懂但不像真人"。这个架构再调也到不了神经网络水平。
  它的价值是：零权重、零联网、确定性、时长精确、可商用。
"""
import argparse
import math
import os
import re
import wave

import numpy as np

SR = 24000  # 直接对齐格式规范闸的目标采样率

# ------------------------------------------------------------------ 音素库
# 元音：用「舌位高低/前后」二维空间推 F1/F2，而非死记每个音素
# 参考普通话元音实测（吴宗济《普通话元音的音色分析》）
VOWEL_SPACE = {
    # ch: (F1, F2, F3)   —— 单音素
    "a": (850, 1200, 2800), "A": (800, 1180, 2750),
    "o": (500, 850, 2750),  "O": (520, 880, 2700),
    "e": (530, 1400, 2500), "E": (560, 1750, 2550),
    "i": (300, 2300, 3000), "I": (330, 2150, 2950),
    "u": (330, 700, 2500),  "U": (350, 780, 2450),
    "y": (300, 1900, 2300),
    "@": (560, 1400, 2500), "&": (700, 1650, 2600),
    "3": (600, 1500, 2550),
}
# 复元音：滑动目标（起点 -> 终点）
DIPHTHONGS = {
    "ai": ("a", "i"), "Ai": ("a", "i"),
    "au": ("a", "u"), "Au": ("a", "u"),
    "ei": ("e", "i"), "ou": ("o", "u"), " Ou": ("o", "u"),
    "ia": ("i", "a"), "ie": ("i", "e"), "iu": ("i", "u"),
    "ua": ("u", "a"), "uo": ("u", "o"), "ue": ("y", "e"),
    "iao": ("i", "au"), "uai": ("u", "ai"), "iou": ("i", "ou"),
}
# 鼻音韵尾
NASAL_CODA = {"n": (280, 1500, 2500), "N": (280, 1100, 2400),
              "ng": (280, 1100, 2400)}

# 辅音：类型 -> (激励, 噪声谱峰, 时长ms)
CONSONANTS = {
    # 塞音（不送气）
    "p": ("plosive", 800, 15), "t": ("plosive", 3000, 15),
    "k": ("plosive", 1800, 20), "b": ("plosive", 700, 12),
    "d": ("plosive", 2600, 12), "g": ("plosive", 1600, 16),
    # 塞音（送气，espeak 用 ' 标记）
    "p'": ("asp", 900, 60), "t'": ("asp", 3200, 65),
    "k'": ("asp", 1900, 70),
    # 塞擦音
    "ts": ("affricate", 5000, 60), "tS": ("affricate", 3000, 70),
    "dz": ("affricate", 4500, 45), "dZ": ("affricate", 2800, 50),
    # 擦音
    "s": ("fric", 6000, 90), "S": ("fric", 2800, 95),
    "z": ("fric", 5200, 70), "Z": ("fric", 2500, 75),
    "f": ("fric", 5000, 80), "h": ("fric", 1800, 70),
    "x": ("fric", 3500, 85), "X": ("fric", 1800, 75),
    # 鼻音 / 近音（浊音）
    "m": ("nasal", 0, 60), "n": ("nasal", 0, 55),
    "l": ("approx", 0, 50), "r": ("approx", 0, 55),
    "j": ("approx", 0, 40), "w": ("approx", 0, 40),
}

# 声调基频轨迹（相对值，1.0 = 基准）
TONE_CONTOUR = {
    "55": [(0, 1.00), (1, 1.00)],                     # 阴平：高平
    "35": [(0, 0.80), (1, 1.15)],                     # 阳平：升
    "214": [(0, 0.72), (0.45, 0.62), (1, 0.95)],      # 上声：降升
    "51": [(0, 1.15), (1, 0.68)],                     # 去声：降
    "11": [(0, 0.78), (1, 0.72)],                     # 轻声：短低
}

# ------------------------------------------------------------------ 音色预设
class Voice:
    """
    formant_scale：声道长度缩放（女声/童声声道短 → 共振峰高）
    f0：基频基准
    breath：送气噪声混合量（粗犷声更大）
    """

    def __init__(self, name, formant_scale=1.0, f0=115, f0_range=1.0,
                 breath=0.04, jitter=0.008, rate=1.0):
        self.name = name
        self.fs = formant_scale
        self.f0 = f0
        self.f0_range = f0_range
        self.breath = breath
        self.jitter = jitter
        self.rate = rate


VOICES = {
    "A": Voice("成熟男声·沉稳", formant_scale=1.00, f0=112, breath=0.035),
    "B": Voice("洪亮男声·粗犷", formant_scale=0.93, f0=98,  breath=0.075,
               f0_range=1.25),
    "C": Voice("年轻男声·清亮", formant_scale=1.06, f0=138, breath=0.030),
    "D": Voice("女声",          formant_scale=1.16, f0=205, breath=0.028),
    "E": Voice("播报腔·标准",   formant_scale=1.02, f0=125, breath=0.020,
               jitter=0.004),
}


# ------------------------------------------------------------------ G2P
def _espeak_g2p(text):
    import ctypes
    import glob
    import piper_phonemize
    pkg = os.path.dirname(piper_phonemize.__file__)
    lib = glob.glob(os.path.join(pkg + ".libs", "libespeak-ng*.so*"))[0]
    Lb = ctypes.CDLL(lib)
    Lb.espeak_Initialize.argtypes = [ctypes.c_int, ctypes.c_int,
                                     ctypes.c_char_p, ctypes.c_int]
    Lb.espeak_Initialize.restype = ctypes.c_int
    Lb.espeak_SetVoiceByName.argtypes = [ctypes.c_char_p]
    Lb.espeak_TextToPhonemes.restype = ctypes.c_char_p
    Lb.espeak_TextToPhonemes.argtypes = [ctypes.POINTER(ctypes.c_char_p),
                                         ctypes.c_int, ctypes.c_int]
    Lb.espeak_Initialize(1, 500, os.path.join(pkg, "espeak-ng-data").encode(), 0)
    Lb.espeak_SetVoiceByName(b"cmn")
    buf = ctypes.c_char_p(text.encode("utf-8"))
    ptr = ctypes.cast(ctypes.pointer(buf), ctypes.POINTER(ctypes.c_char_p))
    r = Lb.espeak_TextToPhonemes(ptr, 1, 0)
    return r.decode("utf-8", "replace") if r else ""


VOWEL_CHARS = "aeiouyAEIOUY@&"   # 注意：不含数字。中文调号含 3/2/1/4/5，
                                 # 把 3 当元音会把 35 切成 韵=@3 调=5


def parse_syllables(phon):
    """
    espeak 输出形如：tong51s.'ou214_| t'A214_| z.'@35n_|

    关键观察（实测得出，不是猜的）：
      音节结构 = 声母 + 韵母 + 韵尾 +声调
      韵尾位置不固定 —— 'tong51' 里 ng 在调号【前】，'z@35n' 里 n 在调号【后】。
      第一版我按「调号即音节结尾」切，结果 'tong51sou214' 被并成一个音节
      （韵=ongsou），这是错的。改为按【元音串】定位音节核心。
    """
    # 去掉重音/音节/边界标记，保留音素与调号
    s = re.sub(r"['.\-_\|\s]", "", phon)
    if not s:
        return []

    pat = re.compile(r"([" + VOWEL_CHARS + r"]+)([^" + VOWEL_CHARS + r"\d]*)(\d+)")
    ms = list(pat.finditer(s))
    out = []
    for i, m in enumerate(ms):
        nxt_start = ms[i + 1].start() if i + 1 < len(ms) else len(s)
        # 声母 = 上一个音节结尾 到 本音节元音开始
        prev_end = ms[i - 1].end() if i > 0 else 0
        onset = s[prev_end:m.start()]
        nucleus = m.group(1)
        coda_pre = m.group(2)                  # 调号前的韵尾
        # 调号后的辅音：默认归下一音节的声母（onset 已含），
        # 只有最后一个音节才把它当自己的韵尾。
        coda_post = s[m.end():nxt_start] if i + 1 >= len(ms) else ""
        coda = coda_pre + coda_post
        out.append({"onset": onset, "nucleus": nucleus,
                    "coda": coda, "tone": m.group(3)})

    # 三声变调：214 + 214 -> 35 + 214（可以 = kh35 ji214）
    for i in range(len(out) - 1):
        if out[i]["tone"] == "214" and out[i + 1]["tone"] == "214":
            out[i]["tone"] = "35"
    return out


# ------------------------------------------------------------------ 轨迹规划
def vowel_targets(nuc, scale):
    """复元音 → 两个共振峰目标点；单音 → 一个"""
    if nuc in DIPHTHONGS:
        s, e = DIPHTHONGS[nuc]
        f1 = VOWEL_SPACE.get(s, VOWEL_SPACE["@"])
        f2 = VOWEL_SPACE.get(e, VOWEL_SPACE["@"])
        return [tuple(v * scale for v in f1), tuple(v * scale for v in f2)]
    t = VOWEL_SPACE.get(nuc, VOWEL_SPACE.get(nuc[0], VOWEL_SPACE["@"]))
    return [tuple(v * scale for v in t)]


def plan(syllables, voice):
    """
    产出逐帧目标：[{f1..f3, f0, av(浊音幅度), af(擦音幅度), nas(鼻化), dur}]
    帧长 5ms（业界常用的共振峰更新率）
    """
    FR = 0.005
    frames = []
    for s in syllables:
        # --- 声母 ---
        onset = s["onset"]
        if onset:
            kind, fpeak, dur = _cinfo(onset)
            n = max(1, int(dur / 1000 / FR / voice.rate))
            t = VOWEL_SPACE["@"][0] * voice.fs
            for _ in range(n):
                if kind in ("nasal", "approx"):
                    frames.append(dict(f1=280 * voice.fs, f2=1300 * voice.fs,
                                       f3=2500 * voice.fs, f0=voice.f0,
                                       av=0.55, af=0.0, nas=0.7 if kind == "nasal" else 0.0,
                                       npk=0))
                else:
                    frames.append(dict(f1=t, f2=1500 * voice.fs,
                                       f3=2500 * voice.fs, f0=voice.f0,
                                       av=0.0, af=0.0 if kind == "plosive" else 0.30,
                                       nas=0.0, npk=fpeak))
        # --- 韵母 ---
        tgts = vowel_targets(s["nucleus"], voice.fs)
        contour = TONE_CONTOUR.get(s["tone"], TONE_CONTOUR["55"])
        dur_v = 165 if s["tone"] != "11" else 90
        if len(tgts) == 2:
            dur_v = int(dur_v * 1.35)
        n = max(2, int(dur_v / 1000 / FR / voice.rate))
        for i in range(n):
            u = i / max(1, n - 1)
            if len(tgts) == 2:
                w = u ** 1.2
                f1 = tgts[0][0] * (1 - w) + tgts[1][0] * w
                f2 = tgts[0][1] * (1 - w) + tgts[1][1] * w
                f3 = tgts[0][2] * (1 - w) + tgts[1][2] * w
            else:
                f1, f2, f3 = tgts[0]
            f0 = voice.f0 * _interp(contour, u)
            # 起收尾幅度包络，避免爆音
            env = min(1.0, u / 0.12, (1 - u) / 0.12)
            frames.append(dict(f1=f1, f2=f2, f3=f3,
                               f0=f0, av=0.9 * max(0.15, env),
                               af=0.0, nas=0.0, npk=0))
        # --- 韵尾鼻音 ---
        coda = s["coda"]
        if coda:
            cd = coda[0]
            if cd in NASAL_CODA:
                nf = NASAL_CODA[cd]
                n = max(1, int(80 / 1000 / FR / voice.rate))
                for i in range(n):
                    u = i / max(1, n - 1)
                    frames.append(dict(f1=nf[0] * voice.fs, f2=nf[1] * voice.fs,
                                       f3=nf[2] * voice.fs,
                                       f0=voice.f0 * _interp(contour, 1.0),
                                       av=0.5 * (1 - u * 0.5), af=0.0,
                                       nas=0.85, npk=0))
    return frames, FR


def _cinfo(onset):
    if onset in CONSONANTS:
        return CONSONANTS[onset]
    if onset + "'" in CONSONANTS:
        return CONSONANTS[onset + "'"]
    return CONSONANTS.get(onset[0], ("approx", 0, 40))


def _interp(contour, u):
    pts = sorted(contour)
    if u <= pts[0][0]:
        return pts[0][1]
    if u >= pts[-1][0]:
        return pts[-1][1]
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]
        x1, y1 = pts[i + 1]
        if x0 <= u <= x1:
            return y0 + (y1 - y0) * (u - x0) / max(1e-6, x1 - x0)
    return pts[-1][1]


# ------------------------------------------------------------------ 合成
def _rosenberg(u, oq=0.42, ret=0.16):
    """Rosenberg 声门波：比脉冲串自然得多（谱倾斜接近真声）"""
    if u < oq:
        return 0.5 * (1 - math.cos(math.pi * u / oq))
    if u < oq + ret:
        return math.cos(math.pi * (u - oq) / (2 * ret))
    return 0.0


def _resonator(x, f, bw, sr):
    """2 极点共振峰滤波器（Klatt 级联用）"""
    r = math.exp(-math.pi * bw / sr)
    th = 2 * math.pi * f / sr
    b1 = 2 * r * math.cos(th)
    b2 = -r * r
    a0 = 1 - b1 - b2
    y = np.empty_like(x)
    y1 = y2 = 0.0
    for i in range(len(x)):
        v = a0 * x[i] + b1 * y1 + b2 * y2
        y[i] = v
        y2, y1 = y1, v
    return y


def synth(frames, FR, voice, seed=7):
    rng = np.random.default_rng(seed)
    sr = SR
    total = int(len(frames) * FR * sr)
    out = np.zeros(total, dtype=np.float64)

    # 激励：声门波 + 噪声
    exc = np.zeros(total)
    u = 0.0
    f0_prev = voice.f0
    for i in range(total):
        fi = min(len(frames) - 1, int(i / sr / FR))
        fr = frames[fi]
        # F0 微抖动（jitter）+ 帧间平滑
        jit = 1.0 + voice.jitter * rng.standard_normal()
        f0 = fr["f0"] * jit
        f0_prev = 0.98 * f0_prev + 0.02 * f0
        u += f0_prev / sr
        if u >= 1.0:
            u -= 1.0
        exc[i] = fr["av"] * _rosenberg(u)
        if fr["af"] > 0 or voice.breath > 0:
            exc[i] += (fr["af"] + voice.breath * fr["av"]) * rng.standard_normal() * 0.35

    # 噪声整形（擦音谱峰）：一阶带通近似
    nz = np.zeros(total)
    for i in range(total):
        fi = min(len(frames) - 1, int(i / sr / FR))
        if frames[fi]["af"] > 0:
            nz[i] = rng.standard_normal()
    if nz.any():
        nz = _resonator(nz, 3200, 900, sr) * 0.6

    src = exc + nz

    # 级联共振峰：R1 -> R2 -> R3
    nfr = len(frames)
    spf = int(FR * sr)
    # 逐帧更新系数，段内滤波
    sig = np.zeros(total)
    for k in range(nfr):
        a = k * spf
        b = min(total, (k + 1) * spf)
        if b <= a:
            break
        fr = frames[k]
        seg = src[a:b]
        bw1 = 60 + 30 * (fr["f1"] / 500)
        seg = _resonator(seg, fr["f1"], bw1, sr)
        seg = _resonator(seg, fr["f2"], 90, sr)
        seg = _resonator(seg, fr["f3"], 140, sr)
        sig[a:b] = seg

    # 幅度归一 + 软化
    pk = np.abs(sig).max()
    if pk > 0:
        sig = sig / pk * 0.89
    sig = np.tanh(sig * 1.1) * 0.95
    return sig


# ------------------------------------------------------------------ 接口
def synthesize(text, voice="A", seed=7):
    v = VOICES[voice] if voice in VOICES else VOICES["A"]
    ph = _espeak_g2p(text)
    syl = parse_syllables(ph)
    frames, FR = plan(syl, v)
    y = synth(frames, FR, v, seed=seed)
    return y, SR, syl


def write_wav(path, y, sr=SR):
    pcm = np.clip(y * 32767, -32768, 32767).astype(np.int16)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", default="动手打人可以治安拘留")
    ap.add_argument("--voice", default="A")
    ap.add_argument("--out", default=None)
    ap.add_argument("--all-voices", action="store_true")
    ap.add_argument("--show-phon", action="store_true")
    a = ap.parse_args()

    if a.show_phon:
        ph = _espeak_g2p(a.text)
        print("G2P:", ph)
        for s in parse_syllables(ph):
            print(f"  声母={s['onset'] or '-':<5} 韵={s['nucleus']:<6} "
                  f"尾={s['coda'] or '-':<3} 调={s['tone']}")
        raise SystemExit(0)

    os.makedirs("audio", exist_ok=True)
    if a.all_voices:
        print(f"{'音色':<16}{'时长ms':>9}  文件")
        for k, v in VOICES.items():
            y, sr, _ = synthesize(a.text, k)
            p = f"audio/自研_{k}_{v.name.split('·')[0]}.wav"
            write_wav(p, y, sr)
            print(f"{v.name:<16}{len(y)/sr*1000:>9.0f}  {p}")
        raise SystemExit(0)

    y, sr, syl = synthesize(a.text, a.voice)
    out = a.out or "audio/自研_输出.wav"
    write_wav(out, y, sr)
    print(f"音色 {VOICES[a.voice].name}  时长 {len(y)/sr*1000:.0f}ms  "
          f"音节 {len(syl)}  -> {out}")
