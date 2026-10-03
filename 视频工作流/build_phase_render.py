#!/usr/bin/env python3
"""出片：逐帧合成循环。
依赖: framerate path build_util
被依赖: build_video
改前必读: IMPROVE_build_video.md
铁律: T76 角色位置 = 路径弧长 s + 横向偏移，禁自由 xy
      T77 等速按弧长参数化 / T79 植物风摆程序化，禁序列帧
"""
import cv2
import framerate as FR
import path as PA
from build_util import place_at, over, sway_image, apply_garment_wind

# 【已删】TREE_XY 硬编码落点 —— 树被钉在墙体立面上，与 spec 声明的地面锚点冲突。
# 树锚点一律由 ctx["tree_xy"] 传入（来自 spec 声明的 anchor_xy），禁代码写死。


def _open_writer(path, fps, W, H):
    """业界通用 H.264(avc1)；失败回退 mp4v 再转 libx264 -crf 18。
    mp4v 是 MPEG-4 Part2 古董编码器，非交付标准。"""
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"avc1"), fps, (W, H))
    if not vw.isOpened():
        vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (W, H))
    return vw


def render(ctx):
    """逐帧合成。ctx 键: bg W H FPS OUT flag_frames man_frames
    tree_frame has_tree dur_f dur_m pts table total_s hw_px speed
    px_per_m U wr_gar s0 flag_xy total"""
    bg = ctx["bg"]
    W, H, FPS, OUT = ctx["W"], ctx["H"], ctx["FPS"], ctx["OUT"]
    flag_frames = ctx["flag_frames"]
    man_frames = ctx["man_frames"]
    tree_frame, has_tree = ctx["tree_frame"], ctx["has_tree"]
    dur_f, dur_m = ctx["dur_f"], ctx["dur_m"]
    pts, table, total_s, hw_px = ctx["pts"], ctx["table"], ctx["total_s"], ctx["hw_px"]
    speed, px_per_m, U, wr_gar = ctx["speed"], ctx["px_per_m"], ctx["U"], ctx["wr_gar"]
    s0, flag_xy = ctx["s0"], ctx["flag_xy"]
    tree_xy = ctx["tree_xy"]
    n_out = int(round(ctx["total"] * FPS))
    vw = _open_writer(OUT, FPS, W, H)
    for i in range(n_out):
        t = i / FPS
        canvas = bg.copy()
        # 旗（base 语义点 = 杆底中心）
        fi = FR.frame_index(t, dur_f)[0]
        rgb, a = flag_frames[fi]
        x0, y0, _ = place_at("base", rgb, a, flag_xy)
        canvas = over(canvas, rgb, a, x0, y0)
        # 树（程序化风摆，铁律79）
        if has_tree:
            trgb, ta = tree_frame
            trgb, ta = sway_image(trgb, ta, t, {"speed": U, "amp_scale": px_per_m}, tree_xy)
            x0, y0, _ = place_at("root", trgb, ta, tree_xy)
            canvas = over(canvas, trgb, ta, x0, y0)
        # 三人：沿路径弧长推进（铁律76/77）
        for k, s_start in enumerate(s0):
            s = (s_start + speed * px_per_m * t) % total_s
            xy = PA.at_distance(pts, s, table=table)["xy"]
            off = PA.clamp_offset(0.0, hw_px)
            mi = FR.frame_index(t + k * 0.13, dur_m)[0]
            rgb, a = man_frames[mi]
            rgb, a = apply_garment_wind(rgb, a, t, wr_gar, px_per_m)
            x0, y0, _ = place_at("ground_contact", rgb, a, (xy[0] + off, xy[1]))
            canvas = over(canvas, rgb, a, x0, y0)
        vw.write(canvas[:, :, ::-1])
    vw.release()
    print(f"[7] 输出 {OUT}  {n_out}帧 {W}x{H} @{FPS}fps")
    return n_out
