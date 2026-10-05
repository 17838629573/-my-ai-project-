#!/usr/bin/env python3
"""render_v4 自检与出片主流程（原 182 行上帝函数抽出）。
依赖: render_v4 及原依赖
被依赖: render_v4
改前必读: IMPROVE_render_v4.md
"""
import os
import sys
import time
import json
import subprocess
import numpy as np
import cv2
import actors
import physics as ph
import systems
from systems import Ctx
from framerate import FPS
from photo_rules import SHOT_TYPES, body_pixels, ground_y, validate_sequence
from film_assemble import nose_offset_x
# 父模块私有常量（W/H/OUT/SHOTS 等只定义在 render_v4，本文件是它的拆分产物）
# 注：render_v4 反向 import 本文件发生在函数体内（懒加载），故顶层引用不成环
from render_v4 import (W, H, OUT, SHOTS, BG_DIR, ENC_IN, ENC_OUT,
                       LEGACY_OUT_NAMES, check_all_shots,
                       make_parts, build_engine, _load_seq)

def self_check():
    """只读自检，不渲染。返回 (ok: bool, 检查项数)"""
    ok = True
    n = 0

    # 1) SHOTS 三轴
    n += 1
    errs = validate_sequence([dict(shot_type=x["shot_type"], angle=x["angle"],
                                   movement=x["movement"]) for x in SHOTS])
    if errs:
        print("FAIL 三轴校验:")
        for e in errs:
            print("   -", e)
        ok = False
    else:
        print("PASS 三轴校验（%d 镜：景别/角度/运动齐全，相邻梯度<=2）" % len(SHOTS))

    # 2) 背景文件存在
    n += 1
    miss = [sh["name"] for sh in SHOTS
            if not os.path.exists(os.path.join(BG_DIR, sh["bg"] + ".jpg"))
            and not os.path.exists(os.path.join(BG_DIR, sh["bg"] + ".png"))]
    if miss:
        print("FAIL 背景缺失: %s" % miss)
        ok = False
    else:
        print("PASS 背景齐全（%d 镜）" % len(SHOTS))

    # 3) actors 门禁（驱动不了即 HALT，禁降级）
    n += 1
    try:
        check_all_shots()
        print("PASS actors 门禁（所有声明动作均可驱动）")
    except SystemExit as e:
        print("FAIL actors 门禁触发 HALT (code=%s)" % e.code)
        ok = False
    except Exception as e:
        print("FAIL actors 门禁异常: %s: %s" % (type(e).__name__, e))
        ok = False

    # 4) build_engine 可构建
    n += 1
    try:
        eng = build_engine()
        have = sorted(eng.systems)
        print("PASS build_engine（按需调度表 %d 项: %s）" % (len(have), ",".join(have)))
    except Exception as e:
        print("FAIL build_engine: %s: %s" % (type(e).__name__, e))
        ok = False

    # 5) 铁律19：默认输出名不得是历史成片
    n += 1
    if os.path.basename(OUT) in LEGACY_OUT_NAMES:
        print("FAIL 默认输出名是历史成片名 '%s'（铁律19 防复用）" % OUT)
        ok = False
    else:
        print("PASS 输出名非历史成片（%s）" % os.path.basename(OUT))

    print("\n%d 项检查 -> %s" % (n, "PASS" if ok else "FAIL"))
    return ok, n

def main():
    check_all_shots()
    only = sys.argv[2] if len(sys.argv) > 2 else None
    tgt = set(only.split(",")) if only else None

    # 三轴校验：景别/角度/运动必须都声明且合法
    seq_errs = validate_sequence([dict(shot_type=x["shot_type"], angle=x["angle"],
                                       movement=x["movement"]) for x in SHOTS])
    if seq_errs:
        print("[剪辑校验] 有问题：")
        for e in seq_errs:
            print("  -", e)
    else:
        print("[剪辑校验] PASS（三轴齐全 + 相邻梯度 <=2）")

    parts = make_parts()
    eng = build_engine()
    os.makedirs("_seg_v4", exist_ok=True)
    segs = []
    t_all = time.time()

    print("=" * 74)
    print("按需调度渲染 v4")
    print("=" * 74)

    for s in SHOTS:
        if tgt and s["name"] not in tgt:
            # 【修复】--only 模式曾把磁盘残留的旧段一并合并，
            # 导致输出全片而非目标镜（静默失效）。只渲染/合并目标镜。
            continue

        ctx = Ctx(W, H)
        ctx.parts = parts
        ctx.subtitle_text = s["caption"]
        # 【关键】人物尺寸由景别反算，不再手填 char_px
        st = SHOT_TYPES[s["shot_type"]]
        ctx.char_px, _in_frame = body_pixels(st, H)
        ctx.ground_y = ground_y(st, H, ctx.char_px)
        ctx.char_w = int(ctx.char_px * 0.42)
        ctx.char_x = nose_offset_x(s["shot_type"], W, ctx.char_w, s.get("look", "right"))
        # 走路镜头启用锁相：背景位移由步距反算，不照抄 bg_speed
        ctx.walk_locked = bool(s["has_walk"])
        ctx.fps = FPS
        # 【接线】风级 → 蒲福换算 → 风速；px/m → 重力像素换算
        lvl = s.get("wind_level", 0)
        ctx.wind_speed = ph.beaufort(lvl)
        ctx.px_per_m = ph.px_per_m(ctx.char_px, systems.REAL_HEIGHT_M)
        # 该镜出现的 dynamic actor 参与风响应
        ctx.wind_actors = [n for n, _a in s.get("actors", [])
                           if actors.ACTORS.get(n, {}).get("body_type") == "dynamic"]
        # 可动件资产装配：按屏幕占比分级缩放
        mv = [n for n, _a in s.get("movables", [])]
        if mv:
            import character_sheet as css
            for nm in mv:
                a = actors.ACTORS.get(nm)
                if not a or not a.get("file"):
                    continue
                fp = os.path.join(actors.CHAR_DIR, a["file"])
                if not os.path.exists(fp):
                    print("  [movables] 缺资产:", nm); continue
                tgt_h = css.tier_target_h(0.25)   # 可动件按中景配角级
                img = css.load_scaled(fp, tgt_h)
                # 【序列帧】优先加载 <name>_fNN.png 循环序列（业界定式：
                # 布料/火/水烘焙成 flipbook），无序列才退回单张
                seq = _load_seq(actors.CHAR_DIR, a["file"])
                if seq:
                    ctx.movable_seqs = getattr(ctx, "movable_seqs", {})
                    ctx.movable_seqs[nm] = seq
                    ctx.parts[nm] = seq[0]
                else:
                    ctx.parts[nm] = img
                if not hasattr(ctx, "movable_period"):
                    ctx.movable_period = {}
                ctx.movable_period[nm] = a.get("loop_period", 1.0)
        ctx.movables = mv
        bgp = os.path.join(BG_DIR, s["bg"] + ".jpg")
        if os.path.exists(bgp):
            ctx.bg = cv2.resize(cv2.imread(bgp), (W, H),
                                interpolation=cv2.INTER_AREA)
        n = int(s["seconds"] * FPS)
        ctx.total_frames = n

        want = eng.configure({"has_walk": s["has_walk"],
                              "has_wind": s["has_wind"],
                              "has_movables": bool(ctx.movables)})
        eng.reset_stats()

        out = os.path.join("_seg_v4", s["name"] + ".mp4")
        proc = subprocess.Popen(
            ["ffmpeg", "-y", *ENC_IN, *ENC_OUT, out],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)

        t0 = time.time()
        eng.run(n, ctx, fps=FPS,
                on_frame_end=lambda c, i, t: proc.stdin.write(c.canvas.tobytes()))
        proc.stdin.close()
        rc = proc.wait()
        dt = time.time() - t0

        active = sorted(want)
        sleep = [x for x in eng.systems if x not in want]
        print(f"\n[{s['name']}] {n}帧 rc={rc} {dt:.1f}s "
              f"{os.path.getsize(out)/1024:.0f}KB")
        print(f"  启用: {', '.join(active) if active else '无'}")
        print(f"  休眠: {', '.join(sleep) if sleep else '无'}")
        print(eng.report())
        segs.append(out)

    lst = OUT + ".txt"
    with open(lst, "w", encoding="utf-8") as f:
        for x in segs:
            f.write(f"file '{os.path.abspath(x)}'\n")
    r = subprocess.run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", lst,
                        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                        "-pix_fmt", "yuv420p", OUT],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"\n合并 rc={r.returncode} -> {OUT}")
    if r.returncode == 0:
        print(f"  {os.path.getsize(OUT)/1024:.0f}KB  "
              f"总耗时 {time.time()-t_all:.1f}s")

