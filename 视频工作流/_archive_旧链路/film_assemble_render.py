#!/usr/bin/env python3
"""film_assemble 分镜渲染与自检（原 165 行抽出）。
依赖: film_assemble 及原依赖
被依赖: film_assemble
改前必读: IMPROVE_film_assemble.md
"""
import os
import subprocess
import numpy as np
import cv2
from photo_rules import SHOT_TYPES
from chroma import contact_shadow, overlay
from subtitle import draw_subtitle
from character_sheet import SHEET
from film_assemble import (sub_shift, scroll_bg, prep_native, prep_scaled,
                           nose_offset_x, resolve_shot, plan_resolve,
                           _pick_asset, overlay_full, META, BG_DIR, NOSEROOM)

from subtitle import subtitle_alpha

def self_check():
    """只读自检，不渲染（ffmpeg 子进程慢且不必要）。返回 (ok, 项数)"""
    ok = True
    n = 0

    # 1) NOSEROOM 覆盖全部 SHOT_TYPES
    n += 1
    miss = [k for k in SHOT_TYPES if k not in NOSEROOM]
    if miss:
        print("FAIL NOSEROOM 缺景别: %s" % miss)
        ok = False
    else:
        print("PASS NOSEROOM 覆盖全部 %d 种景别" % len(SHOT_TYPES))

    # 2) 每种景别都能解析出可见宽度 > 0
    n += 1
    bad = []
    for st in SHOT_TYPES:
        try:
            r = resolve_shot(st, 960, 540, look="right")
            vis = min(540, r["x"] + r["char_w"]) - max(0, r["x"])
            if vis <= 0:
                bad.append("%s 可见宽 %d" % (st, vis))
        except Exception as e:
            bad.append("%s 异常 %s" % (st, e))
    if bad:
        print("FAIL 构图不可见: %s" % bad)
        ok = False
    else:
        print("PASS 全部 %d 景别构图可见宽 > 0" % len(SHOT_TYPES))

    # 3) 铁律28：fps 单一数据源
    n += 1
    try:
        import framerate as fr
        import inspect
        sig = inspect.signature(render_one)
        dv = sig.parameters["fps"].default
        if dv is None:
            print("PASS render_one(fps=None) 取 framerate.FPS=%d" % fr.FPS)
        else:
            print("FAIL fps 默认写死为 %s" % dv)
            ok = False
    except Exception as e:
        print("FAIL fps 检查异常: %s" % e)
        ok = False

    # 4) broken 过滤必须【真的改变结果】（铁律13：空转检查不算证据）
    #    对照实验：去掉过滤后会选到 broken 的组合数 必须 >= 1，
    #    且带过滤后这些组合确实没选到 broken。
    n += 1
    def _pick_nofilter(shot_type, state):
        for want in ("native", "scaled"):
            for k, v in SHEET.items():
                m = META.get(k, {})
                if shot_type in v.get("shots", []) and v["mode"] == want \
                        and state in m.get("poses", []):
                    return k, want
        return "stand", "scaled"

    diff = [(st, stt, _pick_asset(st, stt), _pick_nofilter(st, stt))
            for st in SHOT_TYPES for stt in META
            if _pick_asset(st, stt) != _pick_nofilter(st, stt)]
    broken = {k for k, v in META.items() if v.get("status") == "broken"}
    if not diff:
        print("FAIL 过滤从未生效（组合数 0）—— 该检查空转，无法证明过滤有用")
        ok = False
    elif any(g[0] in broken for _, _, g, _ in diff):
        print("FAIL 过滤后仍选到 broken: %s" % diff[:2])
        ok = False
    else:
        print("PASS broken 过滤生效（%d 个组合被拦截，例 %s: %s->%s）"
              % (len(diff), diff[0][0], diff[0][3][0], diff[0][2][0]))

    # 5) scroll_bg / sub_shift 边界
    n += 1
    try:
        import numpy as np
        bg = np.full((960, 540, 3), 200, np.uint8)
        out = scroll_bg(bg, 137.0, 540, 960)
        if out.shape == bg.shape and int(out.mean()) > 0:
            print("PASS scroll_bg 输出尺寸一致且非全黑")
        else:
            print("FAIL scroll_bg 异常: shape=%s" % (out.shape,))
            ok = False
        img = np.full((100, 100, 3), 128, np.uint8)
        sh = sub_shift(img, 10.0, 5.0)
        if sh.shape == img.shape:
            print("PASS sub_shift 位移后尺寸一致")
        else:
            print("FAIL sub_shift 尺寸变了")
            ok = False
    except Exception as e:
        print("FAIL 边界检查异常: %s: %s" % (type(e).__name__, e))
        ok = False

    print("\n%d 项检查 -> %s" % (n, "PASS" if ok else "FAIL"))
    return ok, n

def render_one(p, out_mp4, W=540, H=960, fps=None, bg_speed=1.5, bob=5.0,
               step_frames=30, cam_pull=0.0, cam_push=0.0, crf=18):
    bg_full = cv2.imread(os.path.join(BG_DIR, p["bg"] + ".jpg"))
    if bg_full is None:
        raise FileNotFoundError(p["bg"])

    if p["mode"] == "native":
        ch_img = prep_native(p["asset"], W, H)
        seq = [ch_img]
        walk = False
    else:
        # 行走需要两帧交替
        st = p["asset"]
        if st == "walk_a":
            a = prep_scaled("walk_a", p["char_h"])
            b = prep_scaled("walk_b", p["char_h"])
            seq = [a, b]; walk = True
        else:
            seq = [prep_scaled(st, p["char_h"])]; walk = False

    # 铁律28：fps 单一数据源，禁止写死 60
    if fps is None:
        import framerate as fr
        fps = fr.FPS
    n = max(1, int(p["seconds"] * fps))
    proc = subprocess.Popen(
        ["ffmpeg", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
         "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
         "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
         "-pix_fmt", "yuv420p", out_mp4],
        stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    for i in range(n):
        u = i / max(1, n - 1)
        scale = 1.0 - cam_pull * u + cam_push * u
        canvas = np.ascontiguousarray(scroll_bg(bg_full, bg_speed * i, W, H))

        if p["mode"] == "native":
            canvas = overlay_full(canvas, seq[0], scale)
        else:
            img = seq[int(i // step_frames) % len(seq)] if walk else seq[0]
            dy = -abs(np.sin(2 * np.pi * (i % (step_frames * len(seq))) /
                             (step_frames * len(seq)))) * bob if walk \
                else np.sin(i / 26.0) * 1.5
            px = p["x"]
            py = p["ground_y"] - int(p["char_h"] * scale) + int(dy)
            # 接触阴影
            sm = contact_shadow(max(6, int(img.shape[1] * scale * 0.9)),
                                max(3, int(p["char_h"] * scale * 0.05)), 0.45)
            sy = p["ground_y"] - sm.shape[0] // 2
            sx = int(px + img.shape[1] * scale * 0.05)
            y0, y1 = max(0, sy), min(H, sy + sm.shape[0])
            x0, x1 = max(0, sx), min(W, sx + sm.shape[1])
            if y1 > y0 and x1 > x0:
                roi = canvas[y0:y1, x0:x1].astype(np.float32)
                roi *= (1.0 - sm[:y1 - y0, :x1 - x0, None] * 0.55)
                canvas[y0:y1, x0:x1] = roi.astype(np.uint8)
            fx, fy = px - int(px), py - int(py)
            if abs(fx) > 1e-3 or abs(fy) > 1e-3:
                img = sub_shift(img, fx, fy)
            overlay(canvas, img, int(px), int(py), scale=scale)

        if p["caption"]:
            canvas = draw_subtitle(canvas, p["caption"], alpha=subtitle_alpha(i, n))
        proc.stdin.write(canvas.tobytes())
    proc.stdin.close()
    return n, proc.wait()

