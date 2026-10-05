#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开放语音语料库 · 注册表 + 接入器
==================================================
用户提议：网上有开放的原素材，为什么不用真人的？

【好消息】确实有，而且授权非常干净 —— 比 TTS 模型权重干净得多。
【坏消息】我这边所有下载源都是 403（实测，见下），拿不到。

所以本文件做两件事：
  1. 把查到的开放语料库登记成表（授权 / 规模 / 标注类型 / 获取方式）
  2. 写一个接入器 —— 你在自己机器下载后放进来，我这套 PSOLA 管线直接吃

------------------------------------------------------------------
【实测：下载源连通性】
------------------------------------------------------------------
  403  www.openslr.org/18/              (THCHS-30)
  403  cn-mirror.openslr.org/...        (国内镜像)
  403  openslr.magicdatatech.com/93     (AISHELL-3)
  403  openslr.elda.org/93
  403  commonvoice.mozilla.org
  403  datacollective.mozillafoundation.org
  403  data.keithito.com               (LJSpeech)
  403  huggingface.co / hf-mirror.com
  403  www.modelscope.cn
  200  mirrors.cloud.tencent.com/pypi  ← 只有 PyPI 镜像通

PyPI 上共探测 10 个可能含语料的包名，只有 `aishell` 存在，
但实测 wheel 仅 7KB —— 是代码不是数据。

------------------------------------------------------------------
【登记册：按授权从宽到严】
------------------------------------------------------------------
"""
import argparse
import glob
import os
import re

# ================================================================ 登记册
CORPORA = {
    # ---------------------------------------------------------- 1
    "common_voice_zh": {
        "name": "Mozilla Common Voice · 中文(中国大陆)",
        "license": "CC0-1.0（公有领域，无任何义务）",
        "hours": "1073.77（已验证 239.14）",
        "speakers": "7,546",
        "sr": "48kHz → MP3",
        "annot": "整句文本（无音素/音节对齐）",
        "url": "https://datacollective.mozillafoundation.org/",
        "for_tts": "★ 授权最干净，但【无音素对齐】，拼接合成需自己切分",
        "risk": "禁止识别说话人身份；禁止二次分发原数据集",
        "size": "21.4 GB",
    },
    # ---------------------------------------------------------- 2
    "aishell3": {
        "name": "AISHELL-3（专为中文 TTS 设计）",
        "license": "Apache-2.0（可商用）",
        "hours": "85",
        "speakers": "218",
        "sr": "44.1kHz",
        "annot": "汉字级 + 【拼音级】转录，含声调，准确率 >98%",
        "url": "http://openslr.org/93/",
        "for_tts": "★★★ 最匹配 —— 唯一为 TTS 设计且有拼音+声调标注的中文库",
        "risk": "无",
        "size": "19 GB",
    },
    # ---------------------------------------------------------- 3
    "thchs30": {
        "name": "THCHS-30（清华）",
        "license": "Apache-2.0（可商用）",
        "hours": "30",
        "speakers": "50",
        "sr": "16kHz",
        "annot": "整句 + 【音素级 lexicon】（resource.tgz 里有词典）",
        "url": "http://openslr.org/18/",
        "for_tts": "★★ 授权干净、体积小；但 16kHz 且 2002 年录音，音质偏老",
        "risk": "无",
        "size": "6.4 GB（resource.tgz 仅 24MB）",
    },
    # ---------------------------------------------------------- 4
    "aishell1": {
        "name": "AISHELL-1",
        "license": "Apache-2.0（可商用）",
        "hours": "178",
        "speakers": "400",
        "sr": "16kHz",
        "annot": "整句汉字",
        "url": "http://openslr.org/33/",
        "for_tts": "★ 量大，但为 ASR 设计，无拼音/声调标注",
        "risk": "无",
        "size": "14.5 GB",
    },
    # ---------------------------------------------------------- 5
    "st_cmds": {
        "name": "Free ST Chinese Mandarin (ST-CMDS)",
        "license": "CC BY-NC-ND 4.0",
        "hours": "110",
        "speakers": "855",
        "sr": "16kHz",
        "annot": "整句",
        "url": "http://openslr.org/38/",
        "for_tts": "⚠ 见下方 ND 风险说明",
        "risk": "NC=非商用；ND=禁止衍生 —— 拼接合成的产物是否算衍生作品存争议",
        "size": "7.67 GB",
    },
    # ---------------------------------------------------------- 6
    "magicdata": {
        "name": "MAGICDATA 普通话朗读",
        "license": "CC BY-NC-ND 4.0",
        "hours": "755",
        "speakers": "1,080",
        "sr": "16kHz",
        "annot": "整句 + 说话人信息",
        "url": "http://openslr.org/68/",
        "for_tts": "⚠ 同样是 ND 条款",
        "risk": "NC + ND",
        "size": "52 GB",
    },
    # ---------------------------------------------------------- 7
    "ljspeech": {
        "name": "LJSpeech（英文，单说话人）",
        "license": "Public Domain（无任何义务）",
        "hours": "24",
        "speakers": "1 女声",
        "sr": "22.05kHz",
        "annot": "整句 + 归一化文本",
        "url": "https://keithito.com/LJ-Speech-Dataset/",
        "for_tts": "英文单说话人 —— 拼接合成的经典素材，但做不了中文",
        "risk": "无",
        "size": "2.6 GB",
    },
}

# ND 条款对拼接合成的影响（查证 Creative Commons 官方定义）
ND_NOTE = """
【为什么 ND 条款对本工作流特别危险】

Creative Commons 官方对"NoDerivatives"的定义：
  禁止【分发】改编作品。创作改编本身是允许的，
  只是不能以改编形式分享给他人。

对我们的场景：拼接合成(concatenative synthesis)的产物是否算
"改编作品"，法律上没有明确判例。而我们的场景恰恰是
【要分发成片视频】—— 这正好踩在 ND 最敏感的那一侧。

所以即便 ST-CMDS / MAGICDATA 数据量大、音质好，
我也不建议用在你要发布的视频里。
优先选 CC0（Common Voice）或 Apache-2.0（AISHELL-3 / THCHS-30）。
"""


# ================================================================ 接入器
def scan_corpus(root):
    """扫描语料库目录，统计可用单元"""
    out = {"root": root, "wav": 0, "hours": 0.0, "speakers": set(),
           "has_transcript": False, "transcript_files": []}
    if not os.path.isdir(root):
        return None
    wavs = glob.glob(os.path.join(root, "**", "*.wav"), recursive=True)
    out["wav"] = len(wavs)
    # 说话人 = 常见语料库的目录层级（AISHELL 是 SSBxxxx，THCHS 是 D4_xxx）
    for p in wavs[:2000]:
        parts = p.replace(root, "").strip(os.sep).split(os.sep)
        for seg in parts[:-1]:
            if re.match(r"^(SSB\d+|[A-Z]\d+_?\w*|speaker\d*|spk\d*)$", seg):
                out["speakers"].add(seg)
                break
    # 转录文件
    for name in ("*.txt", "*.tsv", "*.trans.txt", "*.csv"):
        fs = glob.glob(os.path.join(root, "**", name), recursive=True)[:5]
        if fs:
            out["transcript_files"].extend(fs)
    out["has_transcript"] = len(out["transcript_files"]) > 0
    out["speakers"] = len(out["speakers"])
    # 估算时长
    import wave
    tot = 0
    for p in wavs[:300]:
        try:
            with wave.open(p) as w:
                tot += w.getnframes() / w.getframerate()
        except Exception:
            pass
    if wavs:
        out["hours"] = tot / min(300, len(wavs)) * len(wavs) / 3600
    return out


def report():
    print("=" * 74)
    print("开放语音语料库 · 登记册（按授权从宽到严）")
    print("=" * 74)
    for k, v in CORPORA.items():
        print(f"\n■ {v['name']}")
        print(f"   授权   {v['license']}")
        print(f"   规模   {v['hours']}h / {v['speakers']} 说话人 / {v['size']}")
        print(f"   采样   {v['sr']}")
        print(f"   标注   {v['annot']}")
        print(f"   TTS    {v['for_tts']}")
        print(f"   风险   {v['risk']}")
        print(f"   获取   {v['url']}")
    print("\n" + "=" * 74)
    print(ND_NOTE)



# ================================================================ 单元索引
def load_transcript(path, fmt="auto"):
    """
    读常见转录格式：
      AISHELL-3 / LJSpeech:  <utt_id> <text>
      Common Voice:          TSV，列 client_id / path / sentence
    """
    rows = []
    with open(path, encoding="utf-8", errors="replace") as f:
        head = f.readline()
    if fmt == "auto":
        fmt = "tsv" if ("\t" in head and ("sentence" in head or "path" in head)) else "kv"
    with open(path, encoding="utf-8", errors="replace") as f:
        for i, ln in enumerate(f):
            ln = ln.rstrip("\n")
            if not ln:
                continue
            if fmt == "tsv":
                cs = ln.split("\t")
                # Common Voice: client_id, path, sentence, ...
                if len(cs) >= 3:
                    if i == 0 and cs[2] == "sentence":
                        continue
                    rows.append((cs[1], cs[2]))
            else:
                cs = ln.split(None, 1)
                if len(cs) == 2:
                    rows.append((cs[0], cs[1]))
    return rows


def build_unit_index(root, min_dur=0.10, max_dur=1.20):
    """
    把语料库建成『可拼接单元索引』：
      整句 -> 按静音切分 -> 得候选单元 -> 记下 (路径, 起止, 时长)
    这是拼接合成真正需要的输入形态（业界叫 unit inventory）。
    """
    import wave
    import numpy as np
    wavs = sorted(glob.glob(os.path.join(root, "**", "*.wav"), recursive=True))
    idx = []
    for p in wavs:
        try:
            with wave.open(p) as w:
                sr = w.getframerate()
                y = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        except Exception:
            continue
        y = y.astype(np.float64)
        if len(y) < sr * min_dur:
            continue
        # 能量包络 + 阈值切分
        W = int(0.020 * sr); H = int(0.010 * sr)
        env = []
        for i in range(0, max(1, len(y) - W), H):
            env.append(np.sqrt((y[i:i + W] ** 2).mean()))
        env = np.array(env)
        if len(env) < 3:
            continue
        thr = max(env.max() * 0.08, np.percentile(env, 20))
        voiced = env > thr
        # 连续段
        segs = []
        st = None
        for i, v in enumerate(voiced):
            if v and st is None:
                st = i
            elif not v and st is not None:
                segs.append((st, i)); st = None
        if st is not None:
            segs.append((st, len(voiced)))
        for a, b in segs:
            t0, t1 = a * H / sr, b * H / sr
            d = t1 - t0
            if min_dur <= d <= max_dur:
                idx.append({"file": p, "t0": t0, "t1": t1,
                            "dur": d, "sr": sr})
    return idx


# ================================================================ CLI
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", help="扫描已下载的语料库目录")
    ap.add_argument("--list", action="store_true", help="列出登记册")
    ap.add_argument("--index", help="从语料库目录建立单元索引")
    ap.add_argument("--transcript", help="读转录文件")
    a = ap.parse_args()

    if a.index:
        idx = build_unit_index(a.index)
        print(f"单元索引: {len(idx)} 个候选单元")
        if idx:
            ds = [u["dur"] for u in idx]
            import numpy as np
            print(f"  时长 中位 {np.median(ds)*1000:.0f}ms  "
                  f"范围 {min(ds)*1000:.0f}–{max(ds)*1000:.0f}ms")
            print("  样例:")
            for u in idx[:5]:
                print(f"    {os.path.basename(u['file'])} "
                      f"{u['t0']*1000:.0f}–{u['t1']*1000:.0f}ms")
        raise SystemExit(0)

    if a.transcript:
        rows = load_transcript(a.transcript)
        print(f"转录 {len(rows)} 条")
        for k, v in rows[:5]:
            print(f"  {k}\t{v[:40]}")
        raise SystemExit(0)

    if a.scan:
        r = scan_corpus(a.scan)
        if r is None:
            print("目录不存在:", a.scan)
            raise SystemExit(1)
        print(f"语料库 {r['root']}")
        print(f"  wav 数量   {r['wav']}")
        print(f"  估算时长   {r['hours']:.2f} 小时")
        print(f"  识别说话人 {r['speakers']}")
        print(f"  有转录     {r['has_transcript']}")
        for f in r["transcript_files"][:3]:
            print(f"    {f}")
        raise SystemExit(0)

    report()
    print("\n用法：")
    print("  python 开放语料库接入.py --list              # 看登记册")
    print("  python 开放语料库接入.py --scan <目录>        # 扫描你下载的语料库")
