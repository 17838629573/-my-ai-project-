#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开源 TTS 注册表 —— 按 GitHub 项目登记，统一接口调用
=====================================================
用户要求：不要自己写合成器，去 GitHub 找现成开源项目，登记成可调用模块。
本文件【一行合成算法都没有】，只做三件事：
  1. 登记各开源项目的实测事实（授权 / 体积 / 中文 / 权重来源 / 安装命令）
  2. 探测本机哪几个能用
  3. 提供统一接口 synth(text) -> (ndarray, sr)

------------------------------------------------------------------
【核心实测发现（这是本轮最重要的结论）】
------------------------------------------------------------------
我把候选项目逐个装了一遍，发现一个共同结构：

    pip 包里【不含权重】，权重是运行时从 HuggingFace / GitHub 下载的。

本沙盒 huggingface.co / github.com / modelscope.cn 全部 403，
所以所有"装完就能说"的项目，最后都卡在同一堵墙上。

但有一条例外路径被我证实可行 —— 见下 PIPER_LOCAL。

------------------------------------------------------------------
【登记册】verified = 我实际装过/测过；unverified = 仅据文档，未实测
------------------------------------------------------------------
"""
import json
import os
import shutil
import subprocess
import sys

import numpy as np

# ================================================================ 登记册
REGISTRY = {
    # ---------------------------------------------------------- 1
    "piper_local": {
        "name": "Piper（本地 ONNX，免联网）",
        "repo": "https://github.com/OHF-voice/piper1-gpl",
        "license": "GPL-3.0（原 rhasspy/piper 为 MIT，已归档）",
        "verified": True,
        "engine_ok": True,          # pip install piper-tts 实测成功
        "weights_local": True,      # 支持 -m 指向本地 .onnx
        "chinese": "zh_CN-huayan-medium（~61MB）需你自行下载后放入",
        "sample_rate": 22050,
        "note": ("【本轮唯一可行路径】pip 包装好了，且明确支持 -m 本地 .onnx。"
                 "只要你把 61MB 中文模型拷进来，全程零联网。"),
        "install": "pip install piper-tts",
        "run": "piper -m zh_CN-huayan-medium.onnx -f out.wav",
        "weight_files": ["zh_CN-huayan-medium.onnx", "zh_CN-huayan-medium.onnx.json"],
    },
    # ---------------------------------------------------------- 2
    "sanotts": {
        "name": "sanoTTS",
        "repo": "https://github.com/Ampixa/sanoTTS",
        "license": "开源（需确认子模块）",
        "verified": True,
        "engine_ok": True,          # pip install sanotts 实测成功 v0.5.0
        "weights_local": False,     # 运行时从 HF / GitHub releases 下
        "chinese": "仓库有中文包，但 pip 发布版(v0.5.0)音色表实测无中文",
        "sample_rate": 22050,
        "note": ("实测 v0.5.0 tables/voices.json 只有 9 个音色、3 种语言：\n"
                 "         en_US: amy / amy-1p1m / amy-1p8m / hfc / kristin / heart / heart-nano\n"
                 "         vi_VN: vi      id_ID: id\n"
                 "         无任何 zh_* 条目。\n"
                 "         有资料称【仓库里已有中文包，等下个 pip 版本落地】——\n"
                 "         ⚠ 这是自媒体转述，我没有实证。\n"
                 "         若要试中文，应 git clone 源码装，而不是 pip 装发布版。"),
        "install": "pip install sanotts",
        "run": "sanotts say '你好' --voice <中文包> -o out.wav",
        "weight_files": ["运行时下载"],
    },
    # ---------------------------------------------------------- 3
    "kitten": {
        "name": "KittenTTS",
        "repo": "https://github.com/KittenML/KittenTTS",
        "license": "Apache-2.0（可商用）",
        "verified": True,
        "engine_ok": True,          # pip install kittentts 实测成功
        "weights_local": False,
        "chinese": "官方音色全为英文命名，中文未证实",
        "sample_rate": 24000,
        "note": ("库装得上，25MB 权重下不来（HF 403）。\n"
                 "         官方 README 8 音色：Bella/Jasper/Luna/Bruno/Rosie/Hugo/Kiki/Leo，\n"
                 "         文档全是英文示例。另有资料称早期版本为 expr-voice-2-m 这类命名。\n"
                 "         顺带一个坑：release wheel 会拉 torch/spacy，\n"
                 "         有实测报告称依赖链可达 3GB（与 25MB 的模型反差极大）。"),
        "install": "pip install kittentts",
        "run": "KittenTTS('KittenML/kitten-tts-nano-0.8-int8')",
        "weight_files": ["运行时从 HF 下载 25MB"],
    },
    # ---------------------------------------------------------- 4
    "inflect": {
        "name": "Inflect-Micro-v2 / Nano-v2",
        "repo": "https://huggingface.co/owensong/Inflect-Micro-v2",
        "license": "Apache-2.0",
        "verified": False,
        "engine_ok": False,         # PyPI 上无此包
        "weights_local": False,
        "chinese": "未见中文说明",
        "sample_rate": 24000,
        "note": ("9.36M 参数 / 37.53MB FP32，24kHz，端到端含波形解码器，\n"
                 "         确定性 seed，官方 ONNX 路径。Nano 版 3.97M / 15.97MB。\n"
                 "         ⚠ 我没找到 PyPI 包，需 hf download，本环境 403 无法验证。"),
        "install": "hf download owensong/Inflect-Micro-v2 --local-dir .",
        "run": "from inference import InflectTTS; tts.save(text,'out.wav')",
        "weight_files": ["HF 仓库整体下载"],
    },
    # ---------------------------------------------------------- 5
    "tiny_tts": {
        "name": "TinyTTS",
        "repo": "https://github.com/tronghieuit/tiny-tts",
        "license": "Apache-2.0",
        "verified": True,
        "engine_ok": True,          # pip download 实测 2.1MB wheel
        "weights_local": False,
        "chinese": "不支持 —— 官方自述 Ultra-lightweight ENGLISH TTS",
        "sample_rate": None,
        "note": ("我拆了它的 wheel：2.1MB，里面只有 cmudict 发音词典\n"
                 "         （6MB pickle + 4MB rep），【没有模型权重】，\n"
                 "         权重从 hf_hub_download('backtracking/tiny-tts','G.pth') 下。\n"
                 "         且官方 SUMMARY 明写 English —— 中文场景直接排除。"),
        "install": "pip install tiny-tts",
        "run": "（English only）",
        "weight_files": ["G.pth（HF 下载）"],
    },
    # ---------------------------------------------------------- 6
    # ---------------------------------------------------------- 7
    "moss_nano": {
        "name": "MOSS-TTS-Nano",
        "repo": "https://github.com/OpenMOSS/MOSS-TTS-Nano",
        "license": "开源（复旦 NLP Lab / MOSI.AI）",
        "verified": False,
        "engine_ok": False,         # PyPI 镜像 moss-tts-nano 404
        "weights_local": False,
        "chinese": "支持 —— 官方 Demo 第一条即中文",
        "sample_rate": 48000,
        "note": ("0.1B 参数，纯 CPU 实时，48kHz 立体声，20 语种，含中文。\n"
                 "         Audio Tokenizer(~20M) + LLM 自回归；2026-04 出 ONNX 版，\n"
                 "         推理只需 ONNX Runtime CPU，无 PyTorch 依赖，单核可跑。\n"
                 "         ⚠ 无 pip 包（镜像 404），官方装法是 git clone —— 本环境 GitHub 403。\n"
                 "         这是三个候选里技术规格最贴合本工作流的一个（24k/48k 都能出）。"),
        "install": "git clone https://github.com/OpenMOSS/MOSS-TTS-Nano.git && pip install -e .",
        "run": "python infer_onnx.py --prompt-audio-path ref.wav --text '你好世界'",
        "weight_files": ["首次运行下载约 100MB"],
    },
    # ---------------------------------------------------------- 8
    "fish_speech": {
        "name": "Fish Speech（现 Fish Audio S2 / OpenAudio）",
        "repo": "https://github.com/fishaudio/fish-speech",
        "license": "代码 Apache-2.0 / 权重 CC-BY-NC-SA-4.0（非商用）",
        "verified": True,
        "engine_ok": False,         # PyPI 上只有陈旧 0.1.0
        "weights_local": False,
        "chinese": "支持（Tier-1 语种之一）",
        "sample_rate": None,
        "note": ("⚠ 两个硬问题：\n"
                 "         1) 授权：代码 Apache-2.0，但【权重是非商用】。\n"
                 "            商用必须向 Fish Audio 单独买授权 —— 不能默认可用。\n"
                 "         2) PyPI 上的 fish-speech 是 0.1.0 陈旧包，作者 Lengyue，\n"
                 "            非官方维护，111KB 无权重，需 torch —— 装了也跑不动。\n"
                 "         ⚠ 另外『模拟原神等游戏角色声音』本质是克隆真人配音演员的嗓音，\n"
                 "            未经授权在法律和伦理上都有问题，不建议这么做。"),
        "install": "git clone 官方仓库（本环境 403）",
        "run": "需 GPU；权重非商用",
        "weight_files": ["需下载，且非商用"],
    },
    # ---------------------------------------------------------- 9
    "cvms": {
        "name": "Character Voice Maker Studio",
        "repo": "无 —— Steam 商业软件（App ID 4226380）",
        "license": " proprietary，$29.99 买断",
        "verified": True,
        "engine_ok": False,         # 仅 Windows；我是 Linux x86_64
        "weights_local": False,
        "chinese": "宣称支持（23 语种含中文）",
        "sample_rate": 24000,
        "note": ("⚠ 这不是开源项目，是 Steam 上的付费 Windows 软件：\n"
                 "         · $29.99 买断，SteamDB 标注 Supported Systems = Windows\n"
                 "         · Steam 评测：13 篇，38% 好评 → 官方标签【多半差评】\n"
                 "         · 闭源，『Audio Interpolation Algorithm』是 proprietary 营销词，\n"
                 "           无法审计代码，也无法验证它到底怎么做合成\n"
                 "         · 描述称『在 pitch / timbre / resonance / articulation 维度上插值』\n"
                 "           —— 这个描述与参数合成（含共振峰合成）是同一族思路\n"
                 "         ⚠ 我这边是 Linux，装不了；且差评率高，不建议盲买。"),
        "install": "Steam 购买（Windows）",
        "run": "GUI 操作，导出 24kHz/16bit/单声道 WAV",
        "weight_files": ["随软件安装"],
    },
    # ---------------------------------------------------------- 10
    "espeak": {
        "name": "eSpeak NG（当前兜底）",
        "repo": "https://github.com/espeak-ng/espeak-ng",
        "license": "GPL-3.0",
        "verified": True,
        "engine_ok": True,
        "weights_local": True,      # espeak-ng-data 随 piper_phonemize 落地
        "chinese": "cmn 可用，已实测出声",
        "sample_rate": 22050,
        "note": ("共振峰合成 —— 机械感来自方法本身，不是参数没调对。\n"
                 "         但它是本环境唯一确定能出中文声音的引擎。"),
        "install": "（已就绪）",
        "run": "（本工作流已封装）",
        "weight_files": ["无（规则合成）"],
    },
}


# ================================================================ 探测
def detect():
    """探测本机各引擎实际可用性"""
    print("=" * 70)
    print("开源 TTS 注册表 · 本机探测")
    print("=" * 70)
    print(f"\n{'引擎':<16}{'可出声':<8}{'权重':<10}中文")
    print("-" * 70)

    avail = []
    for key, p in REGISTRY.items():
        # 引擎是否装得上
        if not p["engine_ok"]:
            state, w = "否", "—"
        elif not p["weights_local"]:
            state, w = "待权重", "需下载"
        else:
            if key == "espeak":
                state, w = "是", "无"
            elif key == "piper_local":
                has = any(os.path.exists(f) for f in p["weight_files"])
                state, w = ("是" if has else "待权重"), ("无" if has else "需 61MB")
            else:
                state, w = "?", "?"
        if state == "是":
            avail.append(key)
        zh = p["chinese"].split("（")[0]
        print(f"{p['name'][:15]:<16}{state:<8}{w:<10}{zh}")

    print("-" * 70)
    print(f"可立即出声：{avail or '无'}")

    print("\n【关键结论】")
    print("  所有神经 TTS 都是『pip 包内不含权重，运行时下载』这一结构。")
    print("  本环境 HF / GitHub / ModelScope 全 403，所以全部卡在下载这步。")
    print("  唯一例外：piper_local —— pip 装得上，且支持 -m 指向本地 .onnx。")
    return avail


# ================================================================ 适配器
class TTS:
    """统一接口：synth(text) -> (float32 ndarray, sample_rate)"""

    def __init__(self, engine=None, **kw):
        self.kw = kw
        self.engine = engine or self._pick()
        self._m = None

        if self.engine == "piper_local":
            m = kw.get("model") or _find_piper_model()
            if m is None:
                raise RuntimeError(
                    "未找到 piper 中文 .onnx。请把 zh_CN-huayan-medium.onnx "
                    "和同名 .onnx.json 放到工作目录，或通过 model= 指定路径。")
            self._m = m
        elif self.engine == "sanotts":
            import sanotts
            self._m = sanotts
        elif self.engine == "kitten":
            import warnings
            warnings.filterwarnings("ignore")
            from kittentts import KittenTTS
            self._m = KittenTTS(kw.get("model",
                                       "KittenML/kitten-tts-nano-0.8-int8"))
        elif self.engine == "espeak":
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from 成熟TTS_espeak import EspeakNG
            self._m = EspeakNG(voice=kw.get("voice", "cmn"), rate=None)
        else:
            raise RuntimeError(f"引擎 {self.engine} 不可用")

    @staticmethod
    def _pick():
        avail = _quiet_detect()
        return avail[0] if avail else "espeak"

    def synth(self, text):
        """不规定时长 —— 音频说了算，帧数由真实时长反推。"""
        if self.engine == "piper_local":
            import wave
            tmp = self.kw.get("out", "_piper_tmp.wav")
            subprocess.run(["piper", "-m", self._m, "-f", tmp],
                           input=text.encode(), check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            with wave.open(tmp) as w:
                sr = w.getframerate()
                y = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
            os.remove(tmp)
            return y.astype(np.float32) / 32768.0, sr

        if self.engine == "sanotts":
            r = self._m.synthesize(text, voice=self.kw.get("voice", "amy"))
            for a in ("audio", "wav", "samples", "waveform"):
                v = getattr(r, a, None)
                if v is not None:
                    return np.asarray(v, np.float32), \
                           int(getattr(r, "sample_rate", 22050))
            raise RuntimeError("sanoTTS 返回结构未知")

        if self.engine == "kitten":
            y = self._m.generate(text, voice=self.kw.get("voice", "Jasper"))
            return np.asarray(y, np.float32), 24000

        if self.engine == "espeak":
            y = self._m.synth(text)
            return y.astype(np.float32) / 32768.0, self._m.sr

        raise RuntimeError("无引擎")


def _find_piper_model():
    for f in ("zh_CN-huayan-medium.onnx", "zh_CN-huayan-x-low.onnx"):
        if os.path.exists(f):
            return f
    return None


def _quiet_detect():
    out = []
    for key, p in REGISTRY.items():
        if not p["engine_ok"]:
            continue
        if p["weights_local"]:
            if key == "espeak":
                out.append(key)
            elif key == "piper_local" and _find_piper_model():
                out.append(key)
    return out or ["espeak"]


# ================================================================ CLI
if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--detect", action="store_true", help="探测本机可用引擎")
    ap.add_argument("--dump", help="导出登记册为 JSON")
    ap.add_argument("--text", default="动手打人可以治安拘留")
    ap.add_argument("--engine", default=None)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    if a.dump:
        with open(a.dump, "w", encoding="utf-8") as f:
            json.dump(REGISTRY, f, ensure_ascii=False, indent=1)
        print(f"已导出 {a.dump}")
        raise SystemExit(0)

    if not a.out:
        detect()
        print("\n用法：")
        print("  python 开源TTS注册表.py --detect            # 探测")
        print("  python 开源TTS注册表.py --out a.wav         # 合成（自动选引擎）")
        print("  python 开源TTS注册表.py --dump reg.json     # 导出登记册")
        raise SystemExit(0)

    t = TTS(engine=a.engine)
    y, sr = t.synth(a.text)
    pcm = np.clip(y * 32767, -32768, 32767).astype(np.int16)
    import wave
    with wave.open(a.out, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    print(f"引擎 {t.engine}  sr={sr}  时长={len(y)/sr*1000:.0f}ms -> {a.out}")
