#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
纯自然语音 —— 只选音色，其余一律不改
======================================
【本版撤回的东西】（上一版改过的，全部回退）
  ✗ 不设 rate        —— 用 eSpeak 默认语速，改 rate 会改发音节奏
  ✗ 不二分搜索时长   —— 不再逼音频去凑预设数字
  ✗ 不做 atempo      —— 不再时间伸缩
  ✗ 不截断 / 不补零  —— 波形完整保留，不在任意相位切断
  ✗ 不做归一化缩放   —— 各音色保持自身音量关系

【本版唯一可改的东西】
  ✓ 音色变体（voice variant）：粗犷 / 细腻 / 男声 / 女声 / 年龄
    实测：换变体只改音色，时长基本不变（2652-2861ms），
    说明它没有动"说话的步骤"，正是用户要的那种改法。

【保留的工程处理】（不改说话，只修拼接）
  ✓ 首尾淡入淡出、段间交叉淡化 —— 业界标准，消除起止咔哒
"""
import os, sys, subprocess, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from 成熟TTS_espeak import EspeakNG, write_wav, duration_ms

D = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(D, "audio")
os.makedirs(OUT, exist_ok=True)

FADE_IN_MS = 8
FADE_OUT_MS = 50
XFADE_MS = 12

# ---- 音色表：唯一允许调整的部分 ----
# eSpeak 变体实测（同一句"动手打人可以治安拘留"，默认语速）：
#   m1 2688ms  m2 2790  m3 2652  m4 2769  m5 2672  m6 2680  m7 2672
#   f1 2700    f2 2819  f3 2756  f4 2861  croak 2683  whisper 2673
# 时长差异 <8%，说明变体只改音色不改节奏。
VOICE_TABLE = {
    "A": ("cmn+m3", "成熟男声·沉稳"),     # 劝阻者：中间，伸手拦人，需要稳
    "B": ("cmn+m7", "洪亮男声·粗犷"),     # 被劝者：左侧，情绪激动
    "C": ("cmn+m2", "年轻男声·清亮"),     # 拉架者：右侧
}

# 台词。（空串=静音段）
LINES = [
    ("V0", "动手打人可以治安拘留", "A"),
    ("V1", "没出事的时候",          "B"),
    ("V2", "安全员都是坏人",        "A"),
    ("V3", "",                     ""),    # 停顿
    ("V4", "出了事呢",              "C"),
]
PAUSE_MS = 600


def fade_edges(y, sr, fin_ms=FADE_IN_MS, fout_ms=FADE_OUT_MS):
    y = y.astype(np.float64).copy()
    n = len(y)
    a = min(int(fin_ms / 1000 * sr), n // 4)
    b = min(int(fout_ms / 1000 * sr), n // 4)
    if a > 1:
        y[:a] *= np.linspace(0.0, 1.0, a)
    if b > 1:
        y[n - b:] *= np.linspace(1.0, 0.0, b)
    return y


def crossfade_concat(segs, sr, xf_ms=XFADE_MS):
    if not segs:
        return np.zeros(0)
    out = segs[0].copy()
    for nxt in segs[1:]:
        xf = min(int(xf_ms / 1000 * sr), len(out), len(nxt))
        if xf > 1:
            w = np.linspace(1.0, 0.0, xf)
            out[-xf:] = out[-xf:] * w + nxt[:xf] * (1.0 - w)
            out = np.concatenate([out, nxt[xf:]])
        else:
            out = np.concatenate([out, nxt])
    return out


if __name__ == "__main__":
    # rate=None —— 关键：完全不碰语速
    tt = EspeakNG(voice="cmn", rate=None)

    print("=" * 66)
    print("纯自然语音  ·  只选音色  ·  其余一律不改")
    print("=" * 66)
    print(f"\n语速: eSpeak 默认（未调用 set_rate）")
    print(f"时间伸缩: 无    截断补零: 无    归一化: 无\n")

    print(f"{'ID':<5}{'台词':<18}{'说话者':<7}{'音色':<11}{'时长ms':>8}{'帧数':>7}")
    print("-" * 62)

    segs, rows = [], []
    for vid, text, actor in LINES:
        if not text:
            y = np.zeros(int(PAUSE_MS / 1000 * tt.sr), dtype=np.float64)
            segs.append(y)
            rows.append((vid, "", "", "", PAUSE_MS,
                         int(round(PAUSE_MS / 1000 * 60))))
            print(f"{vid:<5}{'（停顿）':<18}{'-':<7}{'-':<11}{PAUSE_MS:>8}"
                  f"{int(round(PAUSE_MS/1000*60)):>7}")
            continue

        voice, desc = VOICE_TABLE.get(actor, ("cmn", "默认"))
        tt.set_voice(voice)

        y = tt.synth(text).astype(np.float64)      # 原样输出，不做任何时长干预
        y = fade_edges(y, tt.sr)                   # 只修起止咔哒
        ms = len(y) / tt.sr * 1000.0
        frames = int(round(ms / 1000 * 60))

        segs.append(y)
        rows.append((vid, text, actor, voice, ms, frames))
        print(f"{vid:<5}{text:<18}{actor:<7}{voice:<11}{ms:>8.0f}{frames:>7}")

    full = crossfade_concat(segs, tt.sr)
    full = np.clip(full, -32768, 32767).astype(np.int16)

    wav = os.path.join(OUT, "纯自然语音.wav")
    write_wav(wav, full, tt.sr)
    tot = duration_ms(wav)

    mp3 = os.path.join(OUT, "纯自然语音.mp3")
    subprocess.run(["ffmpeg", "-y", "-i", wav, "-codec:a", "libmp3lame",
                    "-b:a", "128k", mp3],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    print("-" * 62)
    print(f"全片 {tot:.0f}ms = {tot/1000:.2f}s = "
          f"{round(tot/1000*60)} 帧 @60fps")
    print(f"\n时长全部来自 eSpeak 自然输出，未经任何压缩/拉伸。")
    print(f"画面应去匹配这个时长，不是反过来。\n")
    print(f"输出 {mp3}")

    tbl = {r[0]: {"text": r[1], "actor": r[2], "voice": r[3],
                  "dur": int(round(r[4])), "frames": r[5]}
           for r in rows}
    tp = os.path.join(D, "音频真实时长.json")
    with open(tp, "w", encoding="utf-8") as f:
        json.dump(tbl, f, ensure_ascii=False, indent=1)
    print(f"时长表 {tp}")
