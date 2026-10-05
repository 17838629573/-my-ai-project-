#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自然语音生成（上一版的错误做法已废弃）
======================================
【上一版错在哪】
  用户诊断正确：不要规定时间、不要平均化。
  上一版用二分搜索把 rate 强行推到 206/262 wpm 去凑预设时长，
  再硬截断/补零对齐 —— 后果：
    · 一字一顿（语速被推离自然区）
    · 咔哒噪音（波形在任意相位被切断，产生不连续）

【这一版的做法】业界叫 audio-first / prelay
  1. 固定自然语速生成（中文 160-180 字/分钟最自然，取 165）
  2. 接受 TTS 的真实时长作为权威 —— 音频说了算
  3. 画面帧数由真实时长反推，而不是反过来逼音频
  4. 只在 ±10% 内用 atempo 微调（WSOLA，保持音高）
  5. 淡入淡出 + 段间交叉淡化，消除拼接爆音

【为什么不再二分搜索 rate】
  改 rate = 改变发音节奏本身，业界明确指出"机械加速会让辅音粘连"。
  正确工具是时间伸缩（atempo / rubberband），它只改时长不改音高和节奏比例。
"""
import os, sys, wave, struct, subprocess, json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from 成熟TTS_espeak import EspeakNG, write_wav, duration_ms

D = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(D, "audio")
os.makedirs(OUT, exist_ok=True)

# 自然语速（业界：中文 160-180 字/分钟最自然）
NATURAL_RATE = 165
# atempo 安全区（业界：0.75-1.5 透明，>20% 应改画面而非压音频）
ATEMPO_MIN, ATEMPO_MAX = 0.90, 1.10

FADE_IN_MS = 10        # 淡入（业界：10ms 足够消除起始咔哒）
FADE_OUT_MS = 60       # 淡出更长，避免尾巴突然断掉
XFADE_MS = 12          # 段间交叉淡化（业界：5-10ms 即可消除爆音）


def fade_edges(y, sr, fin_ms=FADE_IN_MS, fout_ms=FADE_OUT_MS):
    """首尾淡入淡出：消除波形突然起止造成的咔哒声"""
    y = y.astype(np.float64).copy()
    n = len(y)
    a = min(int(fin_ms / 1000 * sr), n // 4)
    b = min(int(fout_ms / 1000 * sr), n // 4)
    if a > 1:
        y[:a] *= np.linspace(0.0, 1.0, a)
    if b > 1:
        y[n - b:] *= np.linspace(1.0, 0.0, b)
    return y


def atempo_file(src, dst, ratio):
    """ffmpeg atempo：保持音高只改时长（WSOLA）"""
    subprocess.run(["ffmpeg", "-y", "-i", src,
                    "-filter:a", f"atempo={ratio:.4f}",
                    "-ar", "22050", dst],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return duration_ms(dst)


def load_wav(path):
    with wave.open(path) as w:
        sr = w.getframerate()
        n = w.getnframes()
        raw = w.readframes(n)
    return np.frombuffer(raw, dtype=np.int16).astype(np.float64), sr


def crossfade_concat(segs, sr, xf_ms=XFADE_MS):
    """
    交叉淡化拼接：在两段重叠区，前段淡出、后段淡入。
    业界：即便只有 5-10ms 也能完全消除咔哒。
    """
    if not segs:
        return np.zeros(0)
    out = segs[0].copy()
    xf = int(xf_ms / 1000 * sr)
    for nxt in segs[1:]:
        xf = min(xf, len(out), len(nxt))
        if xf > 1:
            w = np.linspace(1.0, 0.0, xf)
            out[-xf:] = out[-xf:] * w + nxt[:xf] * (1.0 - w)
            out = np.concatenate([out, nxt[xf:]])
        else:
            out = np.concatenate([out, nxt])
    return out


def discontinuity_count(y, thresh=0.25):
    """
    检测爆音：相邻样本跳变超过满量程 thresh 的比例。
    波形被任意切断时会出现这种跳变。
    """
    if len(y) < 2:
        return 0
    d = np.abs(np.diff(y))
    return int((d > thresh * 32768).sum())


# 台词表。target_ms=None 表示"不规定时间，用自然时长"
LINES = [
    ("V0", "动手打人可以治安拘留", "A", None),
    ("V1", "没出事的时候",          "B", None),
    ("V2", "安全员都是坏人",        "A", None),
    ("V3", "",                     "",  600),    # 静音段，保留
    ("V4", "出了事呢",              "C", None),
]

if __name__ == "__main__":
    tt = EspeakNG(voice="cmn", rate=NATURAL_RATE)

    print("=" * 66)
    print("自然语音生成  ·  不规定时间  ·  音频说了算")
    print("=" * 66)
    print(f"\n自然语速 {NATURAL_RATE} wpm（业界中文自然区 160-180）")
    print(f"atempo 安全区 {ATEMPO_MIN}-{ATEMPO_MAX}（超出就改画面，不压音频）\n")

    segs = []
    rows = []
    print(f"{'ID':<5}{'台词':<18}{'自然ms':>8}{'微调':>7}{'最终ms':>8}{'帧数':>7}{'爆音':>6}")
    for vid, text, actor, target in LINES:
        if not text:
            y = np.zeros(int(600 / 1000 * tt.sr))
            segs.append(y)
            rows.append((vid, "", actor, 0, 1.0, 600.0, 36))
            print(f"{vid:<5}{'（停顿）':<18}{0:>8}{'-':>7}{600:>8.0f}{36:>7}{0:>6}")
            continue

        # 1. 自然生成（不做任何时长干预）
        y_raw = tt.synth(text).astype(np.float64)
        nat_ms = len(y_raw) / tt.sr * 1000.0

        # 2. 仅在有目标且差距在安全区内时才微调
        ratio = 1.0
        tmp = os.path.join(OUT, f"_tmp_{vid}.wav")
        if target is not None:
            need = target / nat_ms
            if ATEMPO_MIN <= need <= ATEMPO_MAX:
                ratio = need
                write_wav(tmp, y_raw.astype(np.int16), tt.sr)
                atempo_file(tmp, tmp, ratio)
                y_raw, sr2 = load_wav(tmp)
            elif need < ATEMPO_MIN or need > ATEMPO_MAX:
                print(f"  [warn] {vid} 需 {need:.2f}x 超出安全区，"
                      f"保留自然时长（画面去匹配，不是压音频）")

        # 3. 淡入淡出消除起止咔哒
        y = fade_edges(y_raw, tt.sr)
        fin_ms = len(y) / tt.sr * 1000.0

        # 4. 归一化到 -1dBFS（业界标准）
        # 注意：0.891 是 -1dB 的线性幅度比，必须乘回 int16 满量程 32767，
        # 否则归一化结果落在 0~1，转 int16 后整段变静音（第一版就踩了这个坑）
        peak = np.abs(y).max()
        if peak > 0:
            y = y / peak * (0.891 * 32767)

        pops = discontinuity_count(y)
        segs.append(y)
        nframes = int(round(fin_ms / 1000 * 60))
        rows.append((vid, text, actor, nat_ms, ratio, fin_ms, nframes))
        print(f"{vid:<5}{text:<18}{nat_ms:>8.0f}{ratio:>7.2f}"
              f"{fin_ms:>8.0f}{nframes:>7}{pops:>6}")

        if os.path.exists(tmp):
            os.remove(tmp)

    # 5. 交叉淡化拼接
    full = crossfade_concat(segs, tt.sr)
    full = np.clip(full, -32768, 32767).astype(np.int16)

    wav_path = os.path.join(OUT, "自然语音.wav")
    write_wav(wav_path, full, tt.sr)
    tot = duration_ms(wav_path)

    mp3 = os.path.join(OUT, "自然语音.mp3")
    subprocess.run(["ffmpeg", "-y", "-i", wav_path,
                    "-codec:a", "libmp3lame", "-b:a", "128k", mp3],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    y_all, _ = load_wav(wav_path)
    pops_all = discontinuity_count(y_all)

    print(f"\n全片 {tot:.0f}ms = {tot/1000:.2f}s = "
          f"{round(tot/1000*60)} 帧 @60fps")
    print(f"自然语速下比原预设(6.3s)长 {tot/1000-6.3:.2f}s "
          f"—— 这是真实语速，画面应去匹配它")
    print(f"\n拼接后爆音检测: {pops_all} 处跳变"
          f"（{'PASS 无可闻爆音' if pops_all < 5 else '仍有跳变'}）")
    print(f"\n输出: {mp3}")

    # 6. 导出真实时长，供编码表更新
    table = {r[0]: {"text": r[1], "actor": r[2],
                    "dur": int(round(r[5])), "frames": r[6]}
             for r in rows}
    tp = os.path.join(D, "音频真实时长.json")
    with open(tp, "w", encoding="utf-8") as f:
        json.dump(table, f, ensure_ascii=False, indent=1)
    print(f"时长表: {tp}")
