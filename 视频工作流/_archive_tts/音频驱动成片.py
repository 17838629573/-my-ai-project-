#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
端到端：音频 -> 摄影表 -> 画面 -> 带音轨成片
============================================
链路：V0-V4 音频 -> 帧数/口型 -> 分层渲染 -> ffmpeg 封装音轨
短ID全程，长名只在最后显示。
"""
import os, sys, subprocess, time, wave
import cv2, numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from 短ID编解码 import Codebook, audio_to_xsheet, frame_count, parse_visemes
from 占位音轨 import duration_ms, LINES
from 工作流v2_分层与交互 import bake_background, Layer, composite_layers

D = os.path.dirname(os.path.abspath(__file__))
SHOTS = os.path.join(D, "shots")
if not os.path.isdir(SHOTS):
    SHOTS = os.path.join(D, "..", "rain_film", "shots")
W, H = 360, 640
SIZE = (W, H)
FPS = 60


def load(i):
    return cv2.resize(cv2.imread(os.path.join(SHOTS, f"{i}.jpg")), SIZE,
                      interpolation=cv2.INTER_AREA)


def main():
    cb = Codebook()
    print("=" * 58)
    print("端到端  ·  音频驱动  ·  短ID  ·  60fps")
    print("=" * 58)

    bg_src = load("01")
    char_src = load("03")

    # 1. 烘焙背景（一次）
    baked = bake_background(bg_src, blur_radius=15, flat_levels=48,
                            detail_scale=0.5)
    print("\n[1] 背景烘焙完成（模糊+色阶+降采样，只做一次）")

    # 2. 角色层（短ID A1/B3）
    char_rgba = cv2.cvtColor(char_src[190:430, 80:250], cv2.COLOR_BGR2BGRA)
    ch, cw = char_rgba.shape[:2]

    # 3. 音频 -> 摄影表（短ID V0-V4）
    print("\n[2] 音频 -> 摄影表")
    seq = []
    states = ["A1", "B1", "A2", "C1", "A3"]
    vis = ["M1M3M0M5", "M3M1M0", "M1M5M0", "M3M1M0", "M1M3M0"]
    total_f = 0
    for i, (vid, text, dur, syl) in enumerate(LINES):
        wav = os.path.join(D, "audio", f"{vid}.wav")
        real = duration_ms(wav) if os.path.exists(wav) else dur
        n = frame_count(int(round(real)))
        total_f += n
        seq.append((vid, int(round(real)), vis[i % len(vis)], states[i % len(states)]))
        print(f"    {vid} {cb.get(vid,'text'):<14} {real:>6.0f}ms -> {n:>3}帧  "
              f"状态 {states[i%len(states)]}")
    print(f"    合计 {total_f} 帧 = {total_f/FPS:.1f}s")

    xs = audio_to_xsheet(seq, fps=FPS)
    print(f"    摄影表 {len(xs)} 行，帧号唯一: "
          f"{len(set(r.frame for r in xs)) == len(xs)}")

    # 4. 渲染（口型只影响面部小区域，状态决定角色层）
    print("\n[3] 渲染")
    frames = []
    mouth_box = (0, 0, 46, 30)   # 面部口型区（相对角色层左上）
    for r in xs:
        p = r.frame / max(1, total_f - 1)
        x = int(70 + 70 * p)
        y = int(190 + 18 * p)
        layers = [Layer(baked.image, 0, (0, 0), 0.08)]
        img = char_rgba.copy()
        # 口型：只在小区域内做垂直缩放，模拟张合（确定性，不生成新图）
        if r.viseme in ("M1", "M2", "M3"):
            mx, my, mw, mh = mouth_box
            k = {"M1": 1.6, "M2": 1.2, "M3": 1.9}.get(r.viseme, 1.0)
            sub = img[my:my + mh, mx:mx + mw]
            if sub.size:
                nh = int(mh * k)
                img[my:my + mh, mx:mx + mw] = cv2.resize(
                    cv2.resize(sub, (mw, nh)), (mw, mh))
        layers.append(Layer(img, 2, (x, y), 0.0))
        frames.append(composite_layers(layers, SIZE, (24 * p, 0)))

    print(f"    {len(frames)} 帧渲染完成")

    # 5. 封装音轨
    out = os.path.join(D, "工作流v2_带音轨.mp4")
    p = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", os.path.join(D, "audio", "全片.wav"),
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
         "-shortest", out],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    t0 = time.time()
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    p.wait()
    dt = time.time() - t0

    sz = os.path.getsize(out) / 1024 if os.path.exists(out) else 0
    print(f"\n[4] 封装音轨")
    print(f"    {out}")
    print(f"    {len(frames)}帧 {FPS}fps  耗时 {dt:.1f}s  体积 {sz:.0f}KB")

    # 6. 校验
    cap = cv2.VideoCapture(out)
    n_f = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps_g = cap.get(cv2.CAP_PROP_FPS)
    cap.release()
    ok_f = abs(n_f - len(frames)) <= 1
    ok_fps = abs(fps_g - FPS) < 0.5
    print(f"\n[5] 校验  帧数 {n_f}/{len(frames)} {'OK' if ok_f else 'BAD'}   "
          f"帧率 {fps_g:.1f}/{FPS} {'OK' if ok_fps else 'BAD'}")
    print("=" * 58)
    return 0 if (ok_f and ok_fps) else 1


if __name__ == "__main__":
    sys.exit(main())
