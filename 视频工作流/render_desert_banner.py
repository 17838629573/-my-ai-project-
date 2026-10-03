#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
沙漠幡旗 —— 独立验证项目（不复用大唐偷渡客的任何分镜）
=====================================================
目的：验证「代码算无量纲数 → AI 搜锚定 → 生图 → 代码循环播放」这条链。

代码报出的参数（6级风）：
  M*  = 0.086    质量比（<1，轻旗，易失稳）
  K_B = 2.22e-3  无量纲弯曲刚度
  Fr  = 4.14     弗劳德数
  U*  = 14.10    流体力/重力 —— 风力约为自重的 119 倍
  St  ≈ 0.2      → 摆动频率 2.73 Hz，周期 0.366 s

形态判据（AI 依据 NOAA 蒲福表锚定）：
  6级 → "Heavy flag extends and flaps more vigorously"
  U*=14.1 远超展开阈值 → 幡身接近水平绷直、末端抽打

用法: python3 render_desert_banner.py
"""
import os, sys, subprocess, time
import cv2, numpy as np

import systems
import physics as ph
import actors
import render_v4 as R          # 复用引擎与装配代码，不复用其 SHOTS
from systems import Ctx

import framerate
from framerate import FPS          # 铁律28：帧率唯一数据源
W, H = 540, 960
OUT = "沙漠幡旗.mp4"
SECONDS = 4.0

# ── 分镜：本项目的独立声明（与大唐偷渡客无关）───────────────────
SHOTS = [{
    "name":     "desert_banner",
    "caption":  "风起，幡动。",
    "shot_type": "FS",          # 全景：人物全身 + 幡旗完整入画
    "angle":    "eye",
    "movement": "static",
    "look":     "right",
    "bg":       "desert",
    "has_walk": True,           # 玄奘横向走过
    "has_wind": True,
    "wind_level": 6,            # ← 代码由此算 U*=14.10
    "actors":   [("xz", "walk"), ("banner", "flutter")],
    "movables": [("banner", "flutter")],
}]

# ── actors 门禁：驱动不了就停，不降级 ────────────────────────────
def check_actors():
    errs = []
    for s in SHOTS:
        errs += actors.check_shot(s["name"], s["actors"])
        errs += actors.check_shot(s["name"], s["movables"])
    errs += actors.check_body_type()
    if errs:
        print("[actors 门禁] FAIL")
        for e in errs:
            print("   -", e)
        sys.exit(1)
    print("[actors 门禁] PASS —— 所有动作均可驱动")


def build_ctx(s):
    ctx = Ctx(W, H)
    ctx.fps = FPS
    ctx.subtitle_text = s["caption"]

    # 景别反算人物尺寸（不手填）
    st = R.SHOT_TYPES[s["shot_type"]]
    ctx.char_px, _ = R.body_pixels(st, H)
    ctx.ground_y = R.ground_y(st, H, ctx.char_px)
    ctx.char_w = int(ctx.char_px * 0.42)
    ctx.char_x = R.nose_offset_x(s["shot_type"], W, ctx.char_w, s.get("look", "right"))
    ctx.walk_locked = bool(s["has_walk"])

    # 风级 → 风速；像素/米
    ctx.wind_speed = ph.beaufort(s.get("wind_level", 0))
    ctx.px_per_m = ph.px_per_m(ctx.char_px, systems.REAL_HEIGHT_M)

    # 背景
    bgp = os.path.join(R.BG_DIR, s["bg"] + ".jpg")
    if os.path.exists(bgp):
        ctx.bg = cv2.resize(cv2.imread(bgp), (W, H), interpolation=cv2.INTER_AREA)
    else:
        raise FileNotFoundError("缺背景: " + bgp)

    # 人物部件（骨架贴图槽位）
    ctx.parts = R.make_parts()

    # ── 可动件装配：序列帧 ──────────────────────────────────
    import character_sheet as css
    ctx.movable_seqs = {}
    ctx.movable_period = {}
    for nm, _a in s["movables"]:
        a = actors.ACTORS.get(nm)
        if not a or not a.get("file"):
            continue
        fp = os.path.join(actors.CHAR_DIR, a["file"])
        if not os.path.exists(fp):
            print("  [movables] 缺资产:", nm)
            continue
        seq = R._load_seq(actors.CHAR_DIR, a["file"])
        if not seq:
            print("  [movables] 无序列帧（退回单张）:", nm)
            ctx.parts[nm] = css.load_scaled(fp, css.tier_target_h(0.25))
        else:
            ctx.movable_seqs[nm] = seq
            ctx.parts[nm] = seq[0]
        # 周期由 St 推出，不是手填
        ctx.movable_period[nm] = a.get("loop_period", 1.0)
    ctx.movables = [n for n, _a in s["movables"]]
    ctx.wind_actors = [n for n, _a in s["actors"]
                       if actors.ACTORS.get(n, {}).get("body_type") == "dynamic"]
    # 幡旗放置：视线反侧，立在地面
    ctx.movable_x = int(W * 0.68)
    ctx.total_frames = int(SECONDS * FPS)
    return ctx


def main():
    t0 = time.time()
    check_actors()
    eng = R.build_engine()
    os.makedirs("_seg", exist_ok=True)
    segs = []

    print("=" * 70)
    print("沙漠幡旗 —— 无量纲数驱动的可动件验证")
    print(f"  6级风: U*={14.10}  Fr={4.14}  f={2.73}Hz  周期={0.366}s")
    print("=" * 70)

    for s in SHOTS:
        ctx = build_ctx(s)
        n = ctx.total_frames
        want = eng.configure({"has_walk": s["has_walk"],
                              "has_wind": s["has_wind"],
                              "has_movables": bool(ctx.movables)})
        eng.reset_stats()
        out = os.path.join("_seg", s["name"] + ".mp4")
        proc = subprocess.Popen(["ffmpeg", "-y", *R.ENC_IN, *R.ENC_OUT, out],
                                stdin=subprocess.PIPE,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL)
        eng.run(n, ctx, fps=FPS,
                on_frame_end=lambda c, i, t: proc.stdin.write(c.canvas.tobytes()))
        proc.stdin.close(); rc = proc.wait()
        print(f"\n[{s['name']}] {n}帧 rc={rc} {os.path.getsize(out)/1024:.0f}KB")
        print(f"  启用: {', '.join(sorted(want))}")
        print(eng.report())
        segs.append(out)

    lst = "_seglist.txt"
    with open(lst, "w", encoding="utf-8") as f:
        for x in segs:
            f.write(f"file '{os.path.abspath(x)}'\n")
    r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                        "-pix_fmt", "yuv420p", OUT],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"\n合并 rc={r.returncode} -> {OUT}  "
          f"{os.path.getsize(OUT)/1024:.0f}KB  总耗时 {time.time()-t0:.1f}s")


if __name__ == "__main__":
    main()
