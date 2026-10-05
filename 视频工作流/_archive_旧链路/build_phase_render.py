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
import _ground_arc as GA
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


def _depth_scale(y, v_h, h_cam, px_per_m_near):
    """该地面 y 处的缩放系数（相对近端基准 px_per_m_near）。

    透视自洽式：px_per_m(y) = (y - v_h) / h_cam
      自检（本场景 v_h=482, h_cam=3.383）：
        y=880 -> (880-482)/3.383 = 117.6  == spec near_px_per_m 117.647 ✓
        y=600 -> (600-482)/3.383 =  34.9  ~= spec far_px_per_m 35.056 ✓
    """
    if v_h is None or h_cam is None:
        return 1.0
    denom = float(y) - float(v_h)
    if denom <= 1e-6:
        # 已到/越过地平线：不该发生。钳到极小值而非返回 1，避免"远处巨人"
        return 1e-3
    return (denom / float(h_cam)) / float(px_per_m_near)


def _resize_by(rgb, a, sc):
    """按系数缩放前景与其 alpha（保持宽高比）。"""
    import cv2 as _cv
    h, w = rgb.shape[:2]
    nh = max(2, int(round(h * sc)))
    nw = max(2, int(round(w * sc)))
    r2 = _cv.resize(rgb, (nw, nh), interpolation=_cv.INTER_AREA)
    a2 = _cv.resize(a, (nw, nh), interpolation=_cv.INTER_AREA)
    return r2, a2


def render(ctx):
    """逐帧合成。ctx 键: bg W H FPS OUT flag_frames man_frames
    tree_frame has_tree dur_f dur_m pts table total_s hw_px speed
    px_per_m U wr_gar s0 flag_xy total
    【V2】wtable cam s_start_m （世界弧长推进三件套）"""
    bg = ctx["bg"]
    W, H, FPS, OUT = ctx["W"], ctx["H"], ctx["FPS"], ctx["OUT"]
    flag_frames = ctx["flag_frames"]
    man_frames = ctx["man_frames"]
    v_h = ctx.get("horizon_y")
    h_cam = ctx.get("h_cam")
    tree_frame, has_tree = ctx["tree_frame"], ctx["has_tree"]
    dur_f, dur_m = ctx["dur_f"], ctx["dur_m"]
    pts, table, total_s, hw_px = ctx["pts"], ctx["table"], ctx["total_s"], ctx["hw_px"]
    speed, px_per_m, U, wr_gar = ctx["speed"], ctx["px_per_m"], ctx["U"], ctx["wr_gar"]
    s0, flag_xy = ctx["s0"], ctx["flag_xy"]
    # V2：世界弧长推进三件套（缺一报错，禁静默回落）
    wtable, cam = ctx["wtable"], ctx["cam"]
    hw_m = ctx["hw_m"]   # V4：路半宽（米），随 y 收敛为像素半宽
    s_start_m = ctx["s_start_m"]
    tree_xy = ctx["tree_xy"]
    n_out = int(round(ctx["total"] * FPS))
    vw = _open_writer(OUT, FPS, W, H)
    for i in range(n_out):
        t = i / FPS
        canvas = bg.copy()
        # 旗（base 语义点 = 杆底中心）
        fi = FR.frame_index(t, dur_f)[0] % len(flag_frames)
        rgb, a = flag_frames[fi]
        x0, y0, _ = place_at("base", rgb, a, flag_xy)
        canvas = over(canvas, rgb, a, x0, y0)
        # 树（程序化风摆，铁律79）
        if has_tree:
            trgb, ta = tree_frame
            trgb, ta = sway_image(trgb, ta, t, {"speed": U, "amp_scale": px_per_m}, tree_xy)
            x0, y0, _ = place_at("root", trgb, ta, tree_xy)
            canvas = over(canvas, trgb, ta, x0, y0)
        # 三人：沿路径【世界弧长】推进（V2）
        # 【为什么不能按像素弧长】实测：路径 6 段世界长均 8.10m，像素长却是
        #   238.2/98.4/53.8/33.8/23.3/17.0 px。用像素弧长匀速推进 =>
        #   世界速度从 4.14 m/s 失控到 54.76 m/s（设定 1.5），脚冲向地平线。
        #   正确：地面坐标按米积分，反查像素位置。见 _ground_arc。
        for k, s_start in enumerate(s0):
            d_m = s_start_m[k] + speed * t
            xy = GA.at_world_distance(d_m, wtable, cam)["xy"]
            # 【V4】三角形路宽：半宽随深度收敛，不是常数
            #   旧实现 hw_px = half_width_m * near_px_per_m 全程固定 141.2px，
            #   远端该 26.9px 处也用 141.2px —— 走廊是矩形带而非三角形。
            off = PA.clamp_offset(0.0, GA.hw_px_at(xy[1], hw_m, cam))
            # 相位偏移后必须取模：不取模第3人在 t>0.1s 就 IndexError（实测逼出）
            mi = FR.frame_index(t + k * 0.13, dur_m)[0] % len(man_frames)
            rgb, a = man_frames[mi]
            # P9：随深度缩小。不缩放则近端 200px 的人走到 z=60m 仍是 200px，
            #   成了"远处的巨人"，观感等同飘在空中。
            sc = _depth_scale(xy[1], v_h, h_cam, px_per_m)
            if abs(sc - 1.0) > 1e-3:
                rgb, a = _resize_by(rgb, a, sc)
            rgb, a = apply_garment_wind(rgb, a, t, wr_gar, px_per_m)
            x0, y0, _ = place_at("ground_contact", rgb, a, (xy[0] + off, xy[1]))
            canvas = over(canvas, rgb, a, x0, y0)
        vw.write(canvas[:, :, ::-1])
    vw.release()
    print(f"[7] 输出 {OUT}  {n_out}帧 {W}x{H} @{FPS}fps")
    return n_out
