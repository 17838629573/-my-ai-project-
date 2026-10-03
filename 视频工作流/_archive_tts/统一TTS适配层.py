#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一 TTS 适配层 —— 按可用性自动选引擎，接口一致
==================================================
【设计原则】用户说得对：不要自己造合成器，用现成的。
本文件一行合成算法都没有，只做「探测 -> 选择 -> 适配」。

优先级（自然度从高到低）：
  1. sanoTTS   —— 纯 NumPy，权重 337KB~2.7MB，无需 torch/onnxruntime
  2. KittenTTS —— ONNX，nano 25MB，24kHz
  3. eSpeak NG —— 共振峰合成，机械感是方法决定的（兜底）

【sanoTTS 实测结论（重要，与流传说法有出入）】
  ✓ pip install sanotts         成功，v0.5.0
  ✓ import sanotts              成功
  ✓ 纯 NumPy                    已加载模块中无 torch / onnxruntime
  ✗ 权重不在 pip 包里           运行时从 HuggingFace(ampixa/sanoTTS) 或
                                GitHub releases 下载，本次实测两个源均 403
  ✗ v0.5.0 无中文音色           tables/voices.json 实测：
                                  en_US: amy / amy-1p1m / amy-1p8m /
                                         hfc / kristin / heart / heart-nano
                                  vi_VN: vi
                                  id_ID: id
                                没有任何 zh_* 条目

  ⚠ 所以"中文原生支持"这一条，在 v0.5.0 上不成立。
    若 voices-v2 release 新增了中文包，需要联网后才能确认，本环境无法验证。

【一个容易混淆的点：sanoTTS 也用 espeak】
  它的 frontend.EspeakEngine 确实用 espeak-ng 做 G2P（文本->音素）。
  但【只做音素，不做波形】——波形由神经网络声码器生成。
  这正是它和 eSpeak 机械味的分界线：
     eSpeak NG = espeak 音素 + 共振峰合成器（数学拼波形） → 机械
     sanoTTS   = espeak 音素 + 神经声码器              → 自然
  所以"用了 espeak"不等于"会机械"。
"""
import os
import shutil
import subprocess
import sys

import numpy as np

OUT_SR = 24000          # 规范闸目标采样率


# ---------------------------------------------------------------- 探测
def probe_sano():
    """返回 (可用, 说明)"""
    try:
        import sanotts
    except ImportError:
        return False, "未安装（pip install sanotts）"

    import json
    tbl = os.path.join(os.path.dirname(sanotts.__file__), "tables", "voices.json")
    voices = {}
    if os.path.exists(tbl):
        d = json.load(open(tbl))
        voices = d.get("voices", {})
    zh = [k for k, v in voices.items()
          if str(v.get("language", "")).lower().startswith("zh")]

    # 权重是否已缓存
    cached = False
    try:
        from sanotts.voicepack import DEFAULT_CACHE_DIR
        cached = os.path.isdir(str(DEFAULT_CACHE_DIR)) and \
                 len(os.listdir(str(DEFAULT_CACHE_DIR))) > 0
    except Exception:
        pass

    if zh:
        return True, f"可用，中文音色 {zh}"
    if cached:
        return True, f"权重已缓存，但无中文音色（现有 {sorted(voices)}）"
    return False, ("库已装但权重未下载；且 v0.5.0 音色表无中文"
                   f"（仅 {sorted(set(v.get('language') for v in voices.values()))}）")


def probe_kitten():
    try:
        import kittentts
    except ImportError:
        return False, "未安装（pip install kittentts）"
    try:
        from huggingface_hub import try_to_load_from_cache
        p = try_to_load_from_cache("KittenML/kitten-tts-nano-0.8-int8",
                                   "config.json")
        if isinstance(p, str) and os.path.exists(p):
            return True, "权重已缓存"
    except Exception:
        pass
    return False, "库已装，权重 25MB 未落地"


def probe_espeak():
    """走本项目已有的 成熟TTS_espeak.py"""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from 成熟TTS_espeak import EspeakNG
        tt = EspeakNG(voice="cmn", rate=None)
        y = tt.synth("测试")
        return (len(y) > 0), f"可用（共振峰合成，机械感是方法决定）"
    except Exception as e:
        return False, f"{type(e).__name__}: {str(e)[:80]}"


def report():
    print("=" * 68)
    print("TTS 引擎探测")
    print("=" * 68)
    print(f"\n{'引擎':<12}{'可用':<7}说明")
    print("-" * 68)
    res = {}
    for name, fn in [("sanoTTS", probe_sano),
                     ("KittenTTS", probe_kitten),
                     ("eSpeak NG", probe_espeak)]:
        ok, msg = fn()
        res[name] = ok
        print(f"{name:<12}{'是' if ok else '否':<7}{msg}")
    print("-" * 68)
    pick = next((n for n in ["sanoTTS", "KittenTTS", "eSpeak NG"]
                 if res.get(n)), None)
    print(f"当前选中：{pick or '无可用引擎'}")
    return pick


# ---------------------------------------------------------------- 适配
class TTS:
    """统一接口：synth(text) -> (np.array, sample_rate)"""

    def __init__(self, engine=None, **kw):
        self.engine = engine or report()
        self.kw = kw
        self._m = None
        if self.engine == "sanoTTS":
            import sanotts
            self._m = sanotts
        elif self.engine == "KittenTTS":
            import warnings
            warnings.filterwarnings("ignore")
            from kittentts import KittenTTS
            self._m = KittenTTS(kw.get("model",
                                       "KittenML/kitten-tts-nano-0.8-int8"))
        elif self.engine == "eSpeak NG":
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from 成熟TTS_espeak import EspeakNG
            self._m = EspeakNG(voice=kw.get("voice", "cmn"), rate=None)

    def synth(self, text):
        """返回 (float32 ndarray, sample_rate)。不规定时长——音频说了算。"""
        if self.engine == "sanoTTS":
            r = self._m.synthesize(text, voice=self.kw.get("voice", "amy"))
            for a in ("audio", "wav", "samples", "waveform"):
                v = getattr(r, a, None)
                if v is not None:
                    y = np.asarray(v, dtype=np.float32)
                    return y, int(getattr(r, "sample_rate", 22050))
            raise RuntimeError("sanoTTS 结果结构未知：" +
                               str([a for a in dir(r) if not a.startswith('_')]))
        if self.engine == "KittenTTS":
            y = self._m.generate(text, voice=self.kw.get("voice", "Jasper"))
            return np.asarray(y, dtype=np.float32), OUT_SR
        if self.engine == "eSpeak NG":
            y = self._m.synth(text)
            return y.astype(np.float32) / 32768.0, self._m.sr
        raise RuntimeError("无可用引擎")


# ---------------------------------------------------------------- CLI
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="只探测不合成")
    ap.add_argument("--text", default="动手打人可以治安拘留")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    if a.report or not a.out:
        report()
        raise SystemExit(0)

    t = TTS()
    y, sr = t.synth(a.text)
    out = a.out
    pcm = np.clip(y * 32767, -32768, 32767).astype(np.int16)
    import wave
    with wave.open(out, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    print(f"引擎 {t.engine}  采样率 {sr}  时长 {len(y)/sr*1000:.0f}ms -> {out}")
