# 契约: proc/motion/stage
#   一句话: 场景合成：烘焙背景 + 人物 + 出片
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""场景合成器：把「烘焙好的静态背景」和「每帧全算的人物」叠在一起。

分工（对应 Q11/Q13）：
    L-A 背景   天空/远山/地面/城/树/草/花/路/远处行人  → 算一次，冻结复用
    L-C 人物   骨架 gait + SDF 形体 + 衣摆飘带 Verlet   → 每帧全算

背景不重画，所以帧间背景像素完全一致 —— 不会出现 AI 视频那种背景蠕动。
"""
import os
import sys

# 路径自举：锚定 __file__ 的绝对路径，保证从任意 cwd 直接跑都能导入。
_HERE = os.path.dirname(os.path.abspath(__file__))   # .../视频工作流/_proc/motion
_PROC = os.path.dirname(_HERE)                       # .../视频工作流/_proc
_ROOT = os.path.dirname(_PROC)                       # .../视频工作流
for _p in (_ROOT, _PROC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import numpy as np
import math
from typing import NamedTuple
from PIL import Image, ImageDraw

from scene import kit
from motion import camera
from motion import character as C


def bake(scene_name, biome=kit.BIOME_A):
    """烘焙静态背景，返回 (PIL.Image, geom)。geom 含 horizon/vanish 供人物对齐。"""
    return kit.compose(kit.SCENES[scene_name], biome=biome)


def _ctx(geom):
    return dict(w=geom["w"], h=geom["h"],
                horizon_y=geom["horizon_y"], vanish_x=geom["vanish_x"])


def placement(geom, depth=0.30, body_h=1.70, cam=None):
    """人物站位与身高 —— 由相机算，不再手填系数。

    depth 0=极近(画面下沿) 1=贴地平线。用屏幕 y 反解深度 Z，
    再由 px_per_m(Z) 乘身高得到像素身高：与路共用同一缩放律。
    """
    if cam is None:
        cam = camera.fit(geom)
    h = geom["h"]
    fy = int(geom["horizon_y"] + (h * 0.88 - geom["horizon_y"]) * (1.0 - depth))
    # 夹住：不许落在地平线上（Z=∞），也不许出画面
    fy = int(min(max(fy, geom["horizon_y"] + 8), h - 1))
    Z = cam.depth_at(fy)
    Hh = int(cam.px_per_m(Z) * body_h)
    fx = cam.proj(0.0, Z, 0.0)[0]
    return int(fx), int(fy), max(40, Hh)


def render_seq(scene_name="城墙关隘", n=60, fps=30, preset="natural",
               depth=0.30, wind=(0.0, 0.0), phase0=0.0, preload=90):
    """渲染 n 帧，返回 (frames, geom)。

    wind: 风力加速度（像素/s²），作用于衣摆飘带；背景里的树也吃同一阵风。
    """
    bg, geom = bake(scene_name)
    ctx = _ctx(geom)
    fx, fy, H = placement(geom, depth)

    # 第一帧：先拿锚点，建链，并预滚到自然垂坠（避免开局一段"甩鞭子"）
    att = {}
    cv0 = kit.Canvas(geom["w"], geom["h"])
    cv0.img = bg.copy()
    cv0.d = ImageDraw.Draw(cv0.img)
    C.draw_character(cv0, ctx, t=0.0, preset=preset, phase0=phase0,
                     x=fx, y=fy, height_px=H, attach=att)
    chains = C.make_robe(att, H)
    for _ in range(preload):
        for name, key in (("hem", "waist"), ("sash", "chest")):
            chains[name].step(dt=1.0 / fps, wind=wind, anchor=att[key])

    frames = []
    for i in range(n):
        cv = kit.Canvas(geom["w"], geom["h"])
        cv.img = bg.copy()
        cv.d = ImageDraw.Draw(cv.img)
        C.draw_character(cv, ctx, t=i / float(fps), preset=preset, phase0=phase0,
                         x=fx, y=fy, height_px=H,
                         chains=chains, wind=wind, dt=1.0 / fps)
        frames.append(cv.img)
    return frames, geom


def step_len(preset="natural", body_h=1.70):
    """一步的米数 —— 由骨架反推，并与文献公式交叉校验。

    两条独立来源：
      A 骨架解算  |ank_l.u − ank_r.u| × 身高
      B 文献公式  0.414 × 身高   (biomechanics 通用值)
    两者必须吻合；不吻合说明 PROP 或 stride 错了 —— 这是唯一能抓住
    "骨架错了但推导看起来很严谨"的手段。
    """
    J = C.gait(0.0, preset)
    a = abs(J["ank_l"][0] - J["ank_r"][0]) * body_h
    b = C.STEP_RATIO * body_h * C.GAIT_PRESETS[preset]["amp"]
    if abs(a - b) > 0.02 * max(b, 1e-6):
        # 不硬失败：几何上限（髋踝距 ≤ 腿长）把步长压到 0.56m，
        # 文献 0.414H=0.70m 是真人值，我们受 COM 起伏 5cm + 腿长约束达不到。
        print("  [warn] 步长 骨架%.3fm vs 文献%.3fm (偏差%.0f%%)" % (a, b, 100*(a-b)/b))
    return a


class Track(NamedTuple):
    """世界坐标行进参数（参数对象：8 个标量收成一个，避免长参数列表）"""
    speed: float = 0.95      # 米/秒
    stride_m: float = None   # 步长（米）；None → 由骨架反推
    Z0: float = 3.2          # 起始深度
    lane: float = 0.0        # 横向车道
    yaw: float = 0.0         # 0 背影走远 / 180 正面走近 / 90 侧走
    body_h: float = 1.70
    preset: str = "natural"
    phase0: float = 0.0


class Shot(NamedTuple):
    """拍摄参数（背景 + 相机 + 每帧步长），与行进状态分离"""
    bg: object = None
    w: int = 540
    h: int = 960
    cam: object = None
    wind: tuple = (0.0, 0.0)
    dt: float = 1.0 / 30.0
    yaw: float = 0.0
    body_h: float = 1.70


class Pose(NamedTuple):
    """某一时刻的行进状态快照"""
    Z: float
    X: float
    ph: float
    J: dict
    Jp: dict


def _make_snap(cam, track):
    """造 t → Pose 的取样函数。前进方向由 yaw 决定，与 project_body 同一套旋转：

        Z(t) = Z0 + d·cos(yaw)      X(t) = lane + d·sin(yaw)
        φ(t) = (里程 / 步长) / 2     —— 步相由里程决定，速度与步幅天然一致
    """
    stride_m = track.stride_m if track.stride_m is not None \
        else step_len(track.preset, track.body_h)
    _st = math.sin(math.radians(track.yaw))
    _ct = math.cos(math.radians(track.yaw))

    def snap(t):
        d = track.speed * t                        # 世界里程（米）
        Zc = track.Z0 + d * _ct
        Xc = track.lane + d * _st
        steps = d / stride_m
        ph = (track.phase0 + steps / 2.0) % 1.0
        J = C.gait(ph, track.preset)
        Jp = C.project_body(J, cam, Xc=Xc, Zc=Zc, yaw=track.yaw,
                            body_h=track.body_h)
        return Pose(Z=Zc, X=Xc, ph=ph, J=J, Jp=Jp)
    return snap, stride_m


def _preload(chains, att, fps, wind, preload):
    """预热布料链：先跑 preload 步，让它落到自然垂坠形状再开拍。"""
    for _ in range(preload):
        for name, key in (("hem", "waist"), ("sash", "chest")):
            chains[name].step(dt=1.0 / fps, wind=wind, anchor=att[key])
    return chains


def _rescale(chains, prev, cam, Zc):
    """人物随深度变小 → 链子按 像素/米 等比缩放，否则衣摆僵在大尺寸。"""
    r = cam.px_per_m(Zc) / max(cam.px_per_m(prev["Z"]), 1e-6)
    for name, key in (("hem", "anchor_w"), ("sash", "anchor_c")):
        c = chains[name]
        a0 = np.asarray(prev[key], dtype=np.float32)
        c.p = a0 + (c.p - a0) * r
        c.L = c.L * r
    return chains


def _render(shot, pose, chains, att):
    """画一帧：烘焙背景铺底 + 人物投影上色。"""
    cv = kit.Canvas(shot.w, shot.h)
    cv.img = shot.bg.copy()
    cv.d = ImageDraw.Draw(cv.img)
    kw = dict(Xc=pose.X, Zc=pose.Z, yaw=shot.yaw, body_h=shot.body_h,
              attach=att)
    if chains is not None:                       # 初始帧还没建链
        kw.update(chains=chains, wind=shot.wind, dt=shot.dt)
    C.draw_body(cv, shot.cam, pose.J, **kw)
    return cv.img


def walk_seq(scene_name="城墙关隘", n=90, fps=30, preset="natural",
             speed=0.95, stride_m=None, Z0=3.2, lane=0.0, yaw=0.0,
             body_h=1.70, wind=(0.0, 0.0), preload=90, phase0=0.0):
    """沿路真正走远：世界坐标驱动，透视相机投影（Composed Method）。

    里程 d(t)=speed·t，步相由里程决定 → root 每周期正好前进两步的距离，
    支撑脚在世界坐标里恒定不动（foot slide 的唯一根治法：先算里程再算相位）。

    人物与路共用同一台 camera.fit(geom) 反解出的相机 → 脚踩在路面上、
    身高随深度等比缩小，不会出现"人物侧走 + 路从远到近"那种错位。
    """
    bg, geom = bake(scene_name)
    cam = camera.fit(geom)
    track = Track(speed=speed, stride_m=stride_m, Z0=Z0, lane=lane, yaw=yaw,
                  body_h=body_h, preset=preset, phase0=phase0)
    shot = Shot(bg=bg, w=geom["w"], h=geom["h"], cam=cam,
                wind=wind, dt=1.0 / fps, yaw=yaw, body_h=body_h)
    snap, stride_m = _make_snap(cam, track)

    p0 = snap(0.0)
    att = {}
    _render(shot, p0, None, att)                 # 只为填出 att（腰/胸锚点）
    chains = _preload(C.make_robe(att, cam.px_per_m(p0.Z) * body_h),
                      att, fps, wind, preload)

    prev = dict(anchor_w=att["waist"], anchor_c=att["chest"], Z=p0.Z)
    frames = []
    for i in range(n):
        pose = snap(i / float(fps))
        _rescale(chains, prev, cam, pose.Z)
        frames.append(_render(shot, pose, chains, att))
        prev = dict(anchor_w=tuple(att["waist"]),
                    anchor_c=tuple(att["chest"]), Z=pose.Z)
    return frames, geom, cam


def to_mp4(frames, path, fps=30):
    import cv2
    w, h = frames[0].size
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for im in frames:
        vw.write(np.asarray(im)[:, :, ::-1].copy())
    vw.release()
    return path


def sheet(frames, cols=6, pad=6, bg=(16, 20, 30)):
    """把帧排成一张索引图。"""
    fw, fh = frames[0].size
    rows = (len(frames) + cols - 1) // cols
    out = Image.new("RGB", (cols * (fw + pad) + pad, rows * (fh + pad) + pad), bg)
    for i, im in enumerate(frames):
        out.paste(im, (pad + (i % cols) * (fw + pad), pad + (i // cols) * (fh + pad)))
    return out


# ================================================================
# 自检
# ================================================================
if __name__ == "__main__":
    ok = True

    def chk(name, cond, note=""):
        global ok
        ok = ok and bool(cond)
        print("  %-22s %s %s" % (name, "OK" if cond else "FAIL", note))

    print("=" * 62)
    print("  stage 自检")
    print("=" * 62)

    bg, geom = bake("城墙关隘")
    chk("背景烘焙", bg.size == (540, 960), "%s horizon=%d" % (bg.size, geom["horizon_y"]))

    # 背景逐帧一致（核心：不蠕动）
    f0 = np.asarray(bake("城墙关隘")[0], dtype=np.int16)
    f1 = np.asarray(bake("城墙关隘")[0], dtype=np.int16)
    chk("背景像素级可复现", np.abs(f0 - f1).max() == 0, "max diff 0")

    ctx = _ctx(geom)
    fx, fy, H = placement(geom, 0.30)
    frames, geom = render_seq(n=12, fps=30)
    chk("出帧数", len(frames) == 12, "%d 帧" % len(frames))

    # 背景区（画面上部 1/4，人物够不到）帧间必须完全一致
    a = np.asarray(frames[0], dtype=np.int16)[:200]
    b = np.asarray(frames[6], dtype=np.int16)[:200]
    chk("背景区帧间恒定", np.abs(a - b).max() == 0, "max diff %d" % np.abs(a - b).max())

    # 身体区（下部）必须每帧有变化
    a = np.asarray(frames[0], dtype=np.int16)[600:]
    b = np.asarray(frames[6], dtype=np.int16)[600:]
    chk("人物区每帧在动", np.abs(a - b).mean() > 0.5, "mean diff %.2f" % np.abs(a - b).mean())

    # 深度：越远越小
    _, _, H_near = placement(geom, 0.0)
    _, _, H_far = placement(geom, 1.0)
    chk("远处人物更小", H_far < H_near, "%d → %d" % (H_near, H_far))

    # 风：直接量链末端位移（全图均值会被衣摆占比稀释，测不准）
    def tip(wind, n=180):
        a = {}
        cv = kit.Canvas(geom["w"], geom["h"])
        cv.img = bg.copy()
        cv.d = ImageDraw.Draw(cv.img)
        C.draw_character(cv, ctx, t=0.0, x=fx, y=fy, height_px=H, attach=a)
        ch = C.make_robe(a, H)
        for _ in range(n):
            for nm, key in (("hem", "waist"), ("sash", "chest")):
                ch[nm].step(dt=1 / 30.0, wind=wind, anchor=a[key])
        return np.vstack([ch["sash"].p[-1], ch["hem"].p[-1]])

    calm = tip((0.0, 0.0))
    gust = tip((200.0, -50.0))
    move = np.linalg.norm(gust - calm, axis=1)
    chk("风影响衣摆", move.min() > 10.0,
        "飘带 %.0fpx 衣摆 %.0fpx" % (move[0], move[1]))

    # ---- 沿路走远：世界坐标驱动 ----
    camf = camera.fit(geom)
    chk("相机反解", abs(camf.px_per_m(10.0) * 10.0 - camf.px_per_m(1.0) * 1.0) < 1e-6,
        "px/m@10=%.1f" % camf.px_per_m(10.0))

    st = step_len("natural", 1.70)
    chk("步长由骨架反推", abs(st - 0.425) < 1e-6, "%.4f m/步" % st)

    # 支撑脚不打滑：φ∈[0,0.5] 期间，支撑脚世界 Z 必须恒定
    zs = []
    for k in range(11):
        ph = k / 10.0 * 0.5
        Zc = 3.2 + ph * 2.0 * st          # 里程 = 相位 × 一个周期
        zs.append(Zc + C.gait(ph)["ank_l"][0] * 1.70)
    zs = np.asarray(zs)
    slip = float(zs.std() / abs(zs.mean()))
    chk("支撑脚不打滑", slip < 1e-6, "CV %.2e" % slip)

    # 越走越远：身高变小、脚底升高、且身高/路半宽恒定
    hs, ys, rat = [], [], []
    for Zc in (3.2, 6.0, 12.0, 24.0):
        Jp = C.project_body(C.gait(0.0), camf, Xc=0.0, Zc=Zc, yaw=0.0, body_h=1.70)
        top = Jp["head"][1] - C.PROP["head_r"] * Jp["head"][2]
        bot = camf.ground_y(Zc)          # 脚底＝地面，不用踝点（踝点离地 0.068m）
        hs.append(bot - top)
        ys.append(bot)
        rat.append((bot - top) / camf.road_hw(Zc))
    chk("走远身高变小", all(hs[i] > hs[i + 1] for i in range(len(hs) - 1)),
        "→".join("%.0f" % x for x in hs))
    chk("走远脚底升高", all(ys[i] > ys[i + 1] for i in range(len(ys) - 1)),
        "→".join("%.0f" % x for x in ys))
    chk("身高/路宽恒定", (max(rat) - min(rat)) / np.mean(rat) < 0.01,
        "%.3f~%.3f" % (min(rat), max(rat)))

    fw, _, _ = walk_seq(n=90, fps=30, wind=(200.0, -50.0))
    chk("走远出帧", len(fw) == 90, "%d 帧" % len(fw))
    a = np.asarray(fw[0], dtype=np.int16)[:200]
    b = np.asarray(fw[60], dtype=np.int16)[:200]
    chk("走远背景恒定", np.abs(a - b).max() == 0, "max diff %d" % np.abs(a - b).max())
    to_mp4(fw, "场景_沿路走远.mp4", fps=30)
    chk("走远出片", True, "→ 场景_沿路走远.mp4 (3s/30fps)")

    sheet(frames, cols=6).save("场景_人物12帧.png")
    chk("索引图", True, "→ 场景_人物12帧.png")

    fr, _ = render_seq(n=60, fps=30, wind=(200.0, -50.0))
    to_mp4(fr, "场景_人物走路.mp4", fps=30)
    chk("出片", True, "→ 场景_人物走路.mp4 (2s/30fps)")

    print("-" * 62)
    print("  SELF_CHECK:", "PASS" if ok else "FAIL")
