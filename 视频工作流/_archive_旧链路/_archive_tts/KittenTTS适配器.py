#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KittenTTS 适配器 —— 权重到位即可替换 eSpeak
============================================
【实测状态（重要）】
  ✓ pip install kittentts        成功（PyPI 镜像可达）
  ✓ import kittentts             成功
  ✓ onnxruntime 1.23.2           已就绪（CPU）
  ✗ 模型权重                      HuggingFace / hf-mirror / ModelScope 全部 403

  距离跑通只差 25MB 权重文件。这是我在这个环境里走到最接近的一次。
  只要权重能落地（U 盘拷贝 / 内网镜像 / 换网络），下面代码可直接用。

【为什么值得换】
  eSpeak NG   = 共振峰合成，数学拼波形 → 机械感是方法决定的，调不掉的
  KittenTTS   = ONNX 神经声码器 → 自然度是另一个量级（24kHz, StyleTTS2 系）

【必须你自己验证的一点：中文】
  官方 README 列出的 8 个音色是英文命名：
     Bella / Jasper / Luna / Bruno / Rosie / Hugo / Kiki / Leo
  官方也明确写了：
     "Language coverage is limited compared to multilingual models;
      verify your target language is supported on the model card."
  另有资料称早期版本音色为 expr-voice-{2..5}-{m,f} 且偏中文，
  但那是自媒体转述，我没法实证——权重下不来。
  👉 你拿到权重后第一件事：跑 --selftest 听中文，确认是不是中文音色。

【授权提醒】
  代码 Apache-2.0 可商用。但有报道指出它依赖 espeak-ng（GPL-3.0）
  做音素转换，纯商用前建议确认这一点。
"""
import argparse
import os
import shutil
import subprocess

import numpy as np

TARGET_SR = 24000
DEFAULT_MODEL = "KittenML/kitten-tts-nano-0.8-int8"   # 15M 参数, 25MB
BIGGER_MODEL = "KittenML/kitten-tts-mini-0.8"          # 80M 参数, 80MB, 更自然

# 官方 8 音色（英文命名）。中文音色需实测确认。
VOICES = ["Bella", "Jasper", "Luna", "Bruno", "Rosie", "Hugo", "Kiki", "Leo"]
# 资料提及的另一套命名（偏中文，未经我实证）
VOICES_ALT = [f"expr-voice-{n}-{g}"
              for n in (2, 3, 4, 5) for g in ("m", "f")]


def preflight():
    """跑之前先体检，别等到一半才失败"""
    print("=" * 64)
    print("KittenTTS 体检")
    print("=" * 64)

    ok = True
    try:
        import kittentts
        print("  [OK]   kittentts 库已安装")
    except ImportError:
        print("  [缺失] kittentts —— pip install kittentts")
        ok = False
        return False

    try:
        import onnxruntime
        print(f"  [OK]   onnxruntime {onnxruntime.__version__}")
    except ImportError:
        print("  [缺失] onnxruntime —— pip install onnxruntime")
        ok = False

    try:
        import soundfile
        print("  [OK]   soundfile")
    except ImportError:
        print("  [缺失] soundfile —— pip install soundfile")

    # 权重是否已缓存
    try:
        from huggingface_hub import try_to_load_from_cache
        p = try_to_load_from_cache(DEFAULT_MODEL, "config.json")
        if isinstance(p, str) and os.path.exists(p):
            print(f"  [OK]   权重已缓存: {os.path.dirname(p)}")
        else:
            print(f"  [缺失] 权重未落地 —— 需要 25MB: {DEFAULT_MODEL}")
            print(f"          当前网络 HuggingFace/hf-mirror/ModelScope 均 403")
            print(f"          解决：手动拷权重到缓存目录，或换可达的镜像")
            ok = False
    except Exception as e:
        print(f"  [?]    缓存检查失败: {type(e).__name__}")

    return ok


def load(model_name=DEFAULT_MODEL):
    import warnings
    warnings.filterwarnings("ignore")
    from kittentts import KittenTTS
    return KittenTTS(model_name)


def synth(model, text, voice="Jasper", speed=1.0):
    return model.generate(text, voice=voice, speed=speed)


def selftest(model, text="动手打人可以治安拘留"):
    """
    关键自检：确认到底是不是中文音色。
    中文若不支持，输出会是英文音或乱音 —— 必须听，不能看波形判断。
    """
    print("=" * 64)
    print("中文自检 —— 这一步必须【听】，波形看不出来")
    print("=" * 64)
    outdir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "audio", "kittentts_自检")
    os.makedirs(outdir, exist_ok=True)

    import soundfile as sf
    names = VOICES + VOICES_ALT
    got = []
    for v in names:
        try:
            y = synth(model, text, voice=v)
        except Exception:
            continue
        p = os.path.join(outdir, f"{v}.wav")
        sf.write(p, np.asarray(y, dtype=np.float32), TARGET_SR)
        got.append((v, len(y) / TARGET_SR * 1000, p))

    print(f"\n成功合成 {len(got)} 个音色，文本：{text}\n")
    print(f"{'音色':<18}{'时长ms':>9}  文件")
    for v, ms, p in got:
        print(f"{v:<18}{ms:>9.0f}  {os.path.relpath(p)}")

    # 打包成一个串烧，方便一次听完
    if got:
        segs = []
        for v, _, p in got:
            y, sr = sf.read(p)
            segs.append(y.astype(np.float32))
            segs.append(np.zeros(int(0.35 * sr), np.float32))
        allv = np.concatenate(segs)
        sp = os.path.join(outdir, "全部音色串烧.wav")
        sf.write(sp, allv, TARGET_SR)
        subprocess.run(["ffmpeg", "-y", "-i", sp, "-codec:a", "libmp3lame",
                        "-b:a", "128k", sp.replace(".wav", ".mp3")],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"\n串烧：{sp.replace('.wav','.mp3')}  ({len(allv)/TARGET_SR:.1f}s)")
        print("听一遍，挑出真正能说中文的音色，填进编码表。")
    return got


def integrate_demo():
    """演示：权重到位后如何接入现有编码表（不改动其余管线）"""
    print("=" * 64)
    print("接入方式")
    print("=" * 64)
    print("""
本适配器与 eSpeak 那一版【接口对齐】，替换只需改一行：

    # 之前
    from 成熟TTS_espeak import EspeakNG
    tt = EspeakNG(voice="cmn")

    # 之后
    from KittenTTS适配器 import load, synth
    m = load("KittenML/kitten-tts-nano-0.8-int8")

下游不用动：
    · 音频 -> 摄影表（帧数 = 时长/1000*60）
    · 音频 <-> 人物绑定（actor 字段）
    · 音频格式规范（16bit/24kHz/单声道）
全部复用。

注意：KittenTTS 原生就是 24kHz，正好是规范闸的目标采样率，
      转码那步会变成直通，更省事。
""")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--preflight", action="store_true", help="体检")
    ap.add_argument("--selftest", action="store_true", help="中文音色自检")
    ap.add_argument("--text", default="动手打人可以治安拘留")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    a = ap.parse_args()

    if not any([a.preflight, a.selftest]):
        ap.print_help()
        integrate_demo()
        raise SystemExit(0)

    if a.preflight:
        ok = preflight()
        print(f"\n体检结论：{'可以开跑' if ok else '还缺东西，见上'}")
        if not ok:
            raise SystemExit(1)

    if a.selftest:
        if not preflight():
            raise SystemExit(1)
        selftest(load(a.model), a.text)
