"""build_video 的自检/检查逻辑（由 _extract_tool.py 从 build_video.py 抽出）

改前必读: IMPROVE_build_video.md
"""
import json
import os
import numpy as np
from PIL import Image
import cv2
import chroma as CH
import framerate as FR
import groundline as GL
import scale_map as SM
import path as PA
import genqueue as GQ
import placement as PL
import shot_plan as SP
import wind_sway as WS
import cloth_wire as CW
from composite import _srgb_to_lin, _lin_to_srgb
KEYJOINTS = ("l_ankle", "r_ankle", "l_knee", "r_knee", "l_wrist", "r_wrist")

def load_sheet(path, grid, take):
    """图集 -> 逐帧 RGBA。连通域定界 + 跨帧统一包围框（pivot 稳定）。"""
    if not os.path.exists(path):
        raise SystemExit(
            f"[素材] 缺 {path} —— 素材已清空，须先生图再出片。"
            f"禁静默降级（铁律31/99）。")
    im = np.array(Image.open(path).convert("RGB"))
    bgr = im[:, :, ::-1].copy()
    bgra, a = CH.chroma_key(bgr)
    gh, gw = a.shape[0] // grid[0], a.shape[1] // grid[1]
    masks = [a[(i // grid[1]) * gh:(i // grid[1] + 1) * gh,
               (i % grid[1]) * gw:(i % grid[1] + 1) * gw] for i in range(take)]
    y0, x0, y1, x1 = gh, gw, 0, 0
    for m in masks:
        ys, xs = np.nonzero(m > 0.5)
        if len(ys) == 0:
            continue
        y0 = min(y0, ys.min()); y1 = max(y1, ys.max())
        x0 = min(x0, xs.min()); x1 = max(x1, xs.max())
    y0 = max(0, y0 - 2); x0 = max(0, x0 - 2)
    y1 = min(gh - 1, y1 + 2); x1 = min(gw - 1, x1 + 2)
    rgb_full = bgra[:, :, :3][:, :, ::-1]
    BH, BW = y1 - y0 + 1, x1 - x0 + 1
    cx = (x0 + x1) // 2
    cy = (y0 + y1) // 2
    out = []
    for i, m in enumerate(masks):
        r, c = i // grid[1], i % grid[1]
        sub_rgb = rgb_full[r * gh:(r + 1) * gh, c * gw:(c + 1) * gw]
        crgb = np.zeros((BH, BW, 3), np.uint8)
        ca = np.zeros((BH, BW))
        ys, xs = np.nonzero(m > 0.5)
        if len(ys) == 0:
            out.append((crgb, ca)); continue
        dx, dy = cx - (xs.min() + xs.max()) // 2, cy - (ys.min() + ys.max()) // 2
        ty0, tx0 = dy, dx
        sy0, sy1 = max(0, -ty0), min(m.shape[0], BH - ty0)
        sx0, sx1 = max(0, -tx0), min(m.shape[1], BW - tx0)
        if sy1 > sy0 and sx1 > sx0:
            crgb[ty0 + sy0:ty0 + sy1, tx0 + sx0:tx0 + sx1] = sub_rgb[sy0:sy1, sx0:sx1]
            ca[ty0 + sy0:ty0 + sy1, tx0 + sx0:tx0 + sx1] = m[sy0:sy1, sx0:sx1]
        out.append((crgb, ca))
    return out

def _resize_cs(rgb, size):
    """色彩空间正确的 resize。
    业界(ImageMagick官方用法)：缩小必须走线性光，否则细节区域会偏暗；
    放大反而不要走线性光——线性光放大会加重负瓣 halo，画质更差。
    """
    nw, nh = size
    h = rgb.shape[0]
    if nh <= h:  # downsample -> 线性光
        lin = _srgb_to_lin(rgb)
        out = np.stack([np.array(Image.fromarray(
            (lin[..., c] * 255).astype(np.uint8)).resize((nw, nh), Image.LANCZOS))
            for c in range(3)], axis=-1).astype(np.float32) / 255.0
        return _lin_to_srgb(out)
    return np.array(Image.fromarray(rgb).resize((nw, nh), Image.LANCZOS))

def resize_h(frame, target_h):
    rgb, a = frame
    h, w = a.shape
    nw = max(1, int(round(w * target_h / h)))
    rgb2 = _resize_cs(rgb, (nw, target_h))
    a2 = np.array(Image.fromarray((a * 255).astype(np.uint8)).resize((nw, target_h), Image.LANCZOS)).astype(float) / 255.0
    return rgb2, a2

def sway_image(rgb, a, t, wind, world_xy, amp_px=14.0):
    """程序化风摆：按高度权重做逐行横向位移（铁律79/80，根部不动）。"""
    h, w = a.shape
    out_rgb = np.zeros_like(rgb)
    out_a = np.zeros_like(a)
    ys_rows = np.nonzero(a.max(axis=1) > 0.5)[0]
    if len(ys_rows) == 0:
        return rgb, a
    top, bot = ys_rows.min(), ys_rows.max()
    span = max(1.0, float(bot - top))
    for y in range(h):
        hr = (y - top) / span                      # 0=顶 1=底
        t_norm = max(0.0, min(1.0, 1.0 - hr))      # 归一化高度：底0 顶1
        if t_norm <= 0.0:
            wt = 0.0                                # 根部恒 0（铁律80）
        else:
            wt = WS.layer_weight(t_norm, "branch")
        ph = WS.phase_of((float(world_xy[0]), float(world_xy[1])), 0.0)
        d = WS.sway_offset(t_norm, t, wind, "branch", phase=ph)
        dx = int(round(d * amp_px * wt))
        sx0, sx1 = max(0, -dx), min(w, w - dx)
        if sx1 > sx0:
            out_rgb[y, sx0:sx1] = rgb[y, sx0 + dx:sx1 + dx]
            out_a[y, sx0:sx1] = a[y, sx0 + dx:sx1 + dx]
    return out_rgb, out_a

def over(canvas, rgb, a, x, y):
    # 【已修】拆分时漏算了画布尺寸：W/H 未定义 → NameError。
    h, w = a.shape
    H, W = canvas.shape[:2]          # 画布高、宽（此前凭空引用 W/H）
    X, Y = int(round(x)), int(round(y))
    sx, sy = max(0, -X), max(0, -Y)
    ex, ey = min(w, W - X), min(h, H - Y)
    if ex <= sx or ey <= sy:
        return canvas
    aa = a[sy:ey, sx:ex][:, :, None]
    src = rgb[sy:ey, sx:ex].astype(float)
    dst = canvas[Y + sy:Y + ey, X + sx:X + ex].astype(float)
    canvas[Y + sy:Y + ey, X + sx:X + ex] = (src * aa + dst * (1 - aa)).astype(np.uint8)
    return canvas

def place_at(kind, rgb, a, target_xy):
    """语义点落到 target_xy -> 左上角（铁律84）。"""
    h, w = a.shape
    reg = {"kind": kind, "canvas_w": float(w), "canvas_h": float(h)}
    r = PL.place(reg, (float(target_xy[0]), float(target_xy[1])), scale=1.0)
    return r["x0"], r["y0"], r

def _need(d, key, where):
    if key not in d:
        raise SystemExit(f"[4b] 缺必填 {where}.{key} —— 禁静默留空（铁律31）")
    return d[key]

def _joint_seq(spec, height_m, n_key=8):
    """biped 关节坐标序列：由 pose 的 FK/IK+足端轨迹算出（禁模糊词描述姿态）。

    返回文本：每代表帧一组关键关节的米制坐标，供生图模板做结构性提示词。
    原点=双脚地面中点，单位米。物性(anthro/face/stand/gait)来自 scene_spec，
    由 AI 搜证填入；cycle 由 gait_cycle_from_speed 反算，禁手填。
    """
    import pose, _common as C
    rig = _need(spec, "biped_rig", "scene_spec")
    gait = dict(_need(rig, "gait", "biped_rig"))
    speed = float(_need(gait, "speed_m_s", "gait"))
    # stride 默认按身高 0.88 倍（业界步幅≈0.85~0.9 身高）；cycle 由代码反算
    stride = float(gait.get("stride_m", height_m * 0.88))
    cycle = C.gait_cycle_from_speed(speed, stride)
    gait["cycle_s"] = cycle
    gait["stride_m"] = stride
    pspec = {"height_m": height_m, "anthro": rig["anthro"],
             "face": rig["face"], "poses": rig["poses"], "gait": gait}
    out = []
    for i in range(n_key):
        t = i / n_key * cycle
        j = pose.solve(pspec, "walk", t=t)["joints"]
        # 【已修】pose.solve 返回世界坐标（人整体前进 speed*t）。
        # 序列帧是 in-place（原地走），必须减掉身体位移，
        # 否则 30 格会横向走出 stride=1.5m，且首尾帧不闭合、无法循环。
        _bx = speed * t
        seg = " | ".join(
            "%s(%.2f,%.2f)" % (k, j[k][0] - _bx, j[k][1]) for k in KEYJOINTS)
        # 【已修】足端语义必须逐帧给出：旧实现只在末尾追加一次 t=0 的值，
        # 模型只看到一串坐标数字，于是 32 帧全画成双脚着地（看不到抬脚）。
        (fxL, fyL), phL = pose.foot_target(t, "l", gait)
        (fxR, fyR), phR = pose.foot_target(t, "r", gait)
        seg += (" || 左足%s抬%.3fm(x=%.3f)；右足%s抬%.3fm(x=%.3f)"
                % ("摆动·" if phL == "swing" else "支撑·贴地", fyL, fxL - _bx,
                   "摆动·" if phR == "swing" else "支撑·贴地", fyR, fxR - _bx))
        out.append("帧%d t=%.2fs: %s" % (i + 1, t, seg))
    print(f"[4a] {height_m}m 步态 cycle={cycle:.3f}s stride={stride:.3f}m "
          f"cadence={120/cycle:.0f}步/分（代码算，禁手填）")
    return "\n".join(out)

def apply_garment_wind(rgb, a, t_s, gr, px_per_m, wind_dir=1.0):
    """衣摆受风：对人物下部做水平剪切位移，权重自 y0 线性增至底部。

    频率/幅度全部来自 wind_response 数值层，禁硬编码。
    铁律91：调用处禁写死频率或 amp_scale。
    """
    import cv2 as _cv, numpy as _np
    h, w = rgb.shape[:2]
    y0 = int(h * 0.72)
    amp_px = float(gr["amp_m"]) * float(px_per_m)
    f = float(gr.get("freq_hz") or gr.get("freq_hz_raw") or 0.0)
    ph = 2 * 3.141592653589793 * f * float(t_s)
    dx = amp_px * _np.sin(ph) * float(wind_dir)
    ys = _np.arange(h, dtype=_np.float32)
    wt = _np.clip((ys - y0) / max(1, h - y0), 0.0, 1.0).astype(_np.float32)
    map_x = _np.tile(_np.arange(w, dtype=_np.float32), (h, 1))
    map_y = _np.tile(ys.reshape(h, 1), (1, w))
    map_x = (map_x - (dx * wt.reshape(h, 1))).astype(_np.float32)
    map_y = map_y.astype(_np.float32)
    return (_cv.remap(rgb, map_x, map_y, interpolation=_cv.INTER_LINEAR,
                      borderMode=_cv.BORDER_CONSTANT),
            _cv.remap(a, map_x, map_y, interpolation=_cv.INTER_LINEAR,
                      borderMode=_cv.BORDER_CONSTANT))
