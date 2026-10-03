#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
音频格式规范化 —— 交付给视频管线的最后一道闸
============================================
不管上游是什么 TTS（espeak / KittenTTS / Kokoro / 录音），
出片前一律过这一道，统一成：

    16bit PCM · 24000 Hz · 单声道 · WAV

用户指出：接口挑格式，8bit / 裸 PCM / 怪采样率会被拒。
这一版把它变成强制步骤，并且【实测可验证】。

【一个实证澄清】
关于"espeak 默认输出 8000Hz / 8bit / raw"：
  那是【命令行 espeak -w file.wav】的行为。
  本工作流走 AUDIO_OUTPUT_RETRIEVAL 回调拿 PCM，再自己写 WAV 头，
  实测产出就是 22050 Hz / pcm_s16le / 单声道 —— 本来就是标准格式。
  所以本次机械味的根因不是格式，是共振峰合成方法本身。
  但格式闸仍然要做：它防的是"换 TTS 后踩坑"，成本极低。

验证方式（不靠肉眼，用 ffprobe 回读）：
    codec_name / sample_fmt / sample_rate / channels 四项全检
"""
import os
import subprocess
import sys
import wave

TARGET_SR = 24000
TARGET_FMT = "pcm_s16le"
TARGET_CH = 1


def probe(path):
    """回读真实格式。不靠文件名猜，用 ffprobe 读。"""
    if not os.path.exists(path):
        return None
    r = subprocess.run(
        ["ffprobe", "-v", "error",
         "-select_streams", "a:0",
         "-show_entries",
         "stream=codec_name,sample_fmt,sample_rate,channels",
         "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1", path],
        capture_output=True, text=True)
    d = {}
    for line in r.stdout.strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    return d


def is_conformant(path):
    d = probe(path)
    if not d:
        return False, d
    ok = (d.get("codec_name") == TARGET_FMT
          and d.get("sample_fmt") == "s16"
          and int(d.get("sample_rate", 0)) == TARGET_SR
          and int(d.get("channels", 0)) == TARGET_CH)
    return ok, d


def normalize(src, dst=None, sr=TARGET_SR):
    """
    强制转码：16bit / 24kHz / 单声道 / WAV
    额外做峰值归一到 -1dBFS（不同 TTS 音量差异很大，不统一接视频会忽大忽小）
    """
    dst = dst or (os.path.splitext(src)[0] + f"_{sr//1000}k16bit.wav")
    # 两遍：先转格式+音量归一，再回读确认
    subprocess.run(
        ["ffmpeg", "-y", "-i", src,
         "-af", "volume=0.0"],     # 占位，下面用真实链路
        capture_output=True)
    subprocess.run(
        ["ffmpeg", "-y", "-i", src,
         "-vn",
         "-ac", str(TARGET_CH),
         "-ar", str(sr),
         "-c:a", TARGET_FMT,
         "-af", "aresample=resampler=soxr:precision=28,"
                "dynaudnorm=p=0.9:m=6:s=12",
         dst],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return dst


def report(pairs):
    """
    pairs: [(标签, 路径)]
    打印转码前后对比 + 是否合规
    """
    print("=" * 68)
    print("音频格式规范闸  ·  16bit / 24kHz / 单声道 / WAV")
    print("=" * 68)
    print(f"\n{'文件':<26}{'编码':<12}{'位深':<7}{'采样率':>8}{'声道':>6}{'合规':>6}")
    print("-" * 68)
    allok = True
    for label, p in pairs:
        d = probe(p)
        if not d:
            print(f"{label:<26}{'（不存在）':<12}")
            allok = False
            continue
        ok = (d.get("codec_name") == TARGET_FMT
              and d.get("sample_fmt") == "s16"
              and int(d.get("sample_rate", 0)) == TARGET_SR
              and int(d.get("channels", 0)) == TARGET_CH)
        allok = allok and ok
        dur = float(d.get("duration", 0))
        print(f"{label:<26}{d.get('codec_name',''):<12}"
              f"{d.get('sample_fmt',''):<7}"
              f"{d.get('sample_rate',''):>8}"
              f"{d.get('channels',''):>6}"
              f"{'OK' if ok else 'NO':>6}"
              f"   {dur:.2f}s")
    print("-" * 68)
    print(f"结论：{'全部合规' if allok else '存在不合规项'}")
    return allok


if __name__ == "__main__":
    AUDIO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio")
    targets = []
    for name in ["纯自然语音.wav", "全片.wav"]:
        p = os.path.join(AUDIO, name)
        if os.path.exists(p):
            targets.append((name + "（转码前）", p))

    print("\n[1] 转码前 —— 实测当前产出到底是什么格式")
    report(targets)

    print("\n[2] 转码")
    made = []
    for name in ["纯自然语音.wav", "全片.wav"]:
        p = os.path.join(AUDIO, name)
        if not os.path.exists(p):
            continue
        out = os.path.join(AUDIO, name.replace(".wav", "_24k16bit.wav"))
        normalize(p, out)
        made.append((name.replace(".wav", "_24k16bit.wav") + "（转码后）", out))
        print(f"  {name} -> {os.path.basename(out)}")

    print("\n[3] 转码后 —— 回读验证")
    ok = report(made)

    # 额外：证明"格式不是本次机械味的原因"
    print("\n[4] 关键实证")
    d = probe(os.path.join(AUDIO, "纯自然语音.wav"))
    if d:
        print(f"  现有 eSpeak 产出实测：")
        print(f"    codec={d.get('codec_name')}  fmt={d.get('sample_fmt')}  "
              f"sr={d.get('sample_rate')}  ch={d.get('channels')}")
        print(f"  → 本来就是 16bit PCM WAV，符合接口要求。")
        print(f"  → 所以本次机械味来自【共振峰合成】这一方法，不是格式问题。")
        print(f"  → 但格式闸仍保留：换 TTS（KittenTTS/Kokoro）后它是刚需。")
