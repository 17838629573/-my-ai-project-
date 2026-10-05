"""showreel/timeline.py — 90秒赛博朋克长镜头渲染主循环（离线轨迹查表 + 连续相机）。

契约: proc/showreel/timeline
   一句话: 按视频帧查表渲染，背景/物体/角色/雨丝，相机不切镜

读 showreel/_phys/traj_*.npz（物理预跑轨迹，(帧,物体,3) = x,y,angle），
按视频帧查表渲染：背景(自绘夜空+霓虹+湿沥青) → 物理物体(正交投影) → 角色(骨架 draw_actor) → 雨丝。
相机连续环绕/跟随/推拉，不切镜、不黑屏、不重置。
用法: python3 showreel/timeline.py [start] [end] [--w 1920] [--h 1080]
依赖: motion.camera.OrthoCam, motion.run.draw_actor, motion.character.render.to_mp4
来源: 正交相机与投影范式取自 motion/run.py:180；物理轨迹查表避免"仿真步数当帧数"的慢放坑
      （docs/rigid2d_踩坑记录.md 坑5）。
"""
import os
import sys
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PIL import Image, ImageDraw

from motion import camera, run as mrun
from scene import kit
from motion.character import render as CRE
from motion.run import to_mp4
from showreel import scene as S
from showreel import params as P

W, H = 1920, 1080
FPS = 24
NF = 90 * FPS
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_phys")
MP4 = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "showreel_90s.mp4")


def load_traj():
    """读所有 traj_*.npz → 段列表 [(F, n, 3), ...]。

    不能简单 concat：压力阶段每 3 秒生成新球，物体数逐段递增
    （实测 81 → 82），列数不同会 ValueError。按段保留各自的 n。
    """
    segs = []
    for fn in sorted(os.listdir(OUT)):
        if fn.startswith("traj_") and fn.endswith(".npz"):
            segs.append(np.load(os.path.join(OUT, fn))["traj"])
    if not segs:
        raise SystemExit("[err] 无轨迹，先跑 showreel/phys.py")
    return segs


def snap_at(segs, i):
    """按全局帧号取该段的快照（每段物体数可能不同）。"""
    off = 0
    for a in segs:
        if i < off + a.shape[0]:
            return a[i - off]
        off += a.shape[0]
    return segs[-1][-1]


def load_meta():
    """重建 Street 拿几何元信息（顺序与轨迹一致）。"""
    st = S.Street(dt=1.0 / 240.0, iters=10)
    out = []
    for b in st.world.bodies:
        out.append((
            getattr(b, "shape", "box"),
            float(getattr(b, "hw", getattr(b, "r", 0.1))),
            float(getattr(b, "hh", getattr(b, "r", 0.1))),
            getattr(b, "tag", "obj"),
        ))
    return out


def background(draw, t, cam_s, cam_x, y0):
    """夜空渐变 + 霓虹楼影 + 湿沥青（自绘，不依赖 kit）。"""
    # 夜空：上深蓝紫 → 地平线品红
    for i in range(H):
        u = i / float(H)
        r = int(18 + 60 * max(0.0, (u - 0.55)) * 2.2)
        g = int(10 + 12 * u)
        b = int(46 + 40 * (1 - u))
        draw.line([(0, i), (W, i)], fill=(r, g, b))
    # 霓虹楼影（随相机视差）
    rng = np.random.RandomState(7)
    for k in range(26):
        bx = rng.uniform(-0.2, 1.2)
        bw = rng.uniform(0.03, 0.09)
        bh = rng.uniform(0.18, 0.52)
        sx = int((bx - cam_x * 0.06) * W) % (W + 200) - 100
        top = int(y0 - bh * H * 0.55)
        col = (48, 12, 70) if k % 2 else (30, 10, 54)
        draw.rectangle([sx, top, sx + int(bw * W), int(y0)], fill=col)
        # 窗格霓虹
        for wj in range(3):
            for hi in range(int(bh * 12)):
                if rng.rand() < 0.34:
                    wx = sx + 6 + wj * int(bw * W / 3)
                    wy = top + 8 + hi * 16
                    c = (255, 90, 190) if rng.rand() < 0.5 else (80, 200, 255)
                    draw.rectangle([wx, wy, wx + 5, wy + 8], fill=c)
    # 湿沥青 + 霓虹倒影（竖向拉伸的模糊条）
    draw.rectangle([0, int(y0), W, H], fill=(14, 12, 22))
    for k in range(14):
        rx = int(rng.uniform(0, 1) * W)
        rw = int(rng.uniform(6, 40))
        hgt = int(rng.uniform(60, 260))
        alpha = rng.rand()
        c = (int(120 * alpha) + 20, int(30 * alpha), int(140 * alpha) + 30)
        for j in range(hgt):
            f = 1 - j / float(hgt)
            draw.line([(rx, int(y0) + j), (rx + rw, int(y0) + j)],
                      fill=(int(c[0] * f), int(c[1] * f), int(c[2] * f)))


def draw_bodies(draw, meta, frame, cam_s, cam_x, y0):
    """正交投影画物理物体：sx = cx + (X-cam_x)*s, sy = y0 - Y*s。"""
    cx = W * 0.5
    for i, (shape, hw, hh, tag) in enumerate(meta):
        if i >= frame.shape[0]:
            break
        x, y, a = frame[i]
        sx = cx + (x - cam_x) * cam_s
        sy = y0 - y * cam_s
        if sx < -200 or sx > W + 200:
            continue
        if shape == "circle":
            r = hw * cam_s
            draw.ellipse([sx - r, sy - r, sx + r, sy + r],
                         fill=(230, 120, 60), outline=(20, 10, 10))
        else:
            w = hw * cam_s
            h = hh * cam_s
            # 简易旋转：取四角旋转后多边形
            pts = []
            for (dx, dy) in ((-w, -h), (w, -h), (w, h), (-w, h)):
                rx = dx * np.cos(a) - dy * np.sin(a)
                ry = dx * np.sin(a) + dy * np.cos(a)
                pts.append((sx + rx, sy + ry))
            col = {"domino": (200, 60, 90), "box": (120, 200, 190),
                   "wall": (150, 150, 160), "crate": (170, 140, 80),
                   "cup": (235, 235, 240), "ball": (240, 150, 50)}.get(
                       str(tag).split("_")[0], (130, 170, 210))
            draw.polygon(pts, fill=col, outline=(12, 10, 16))


def rain(draw, t, rng):
    """雨丝：固定种子，随时间下落，避免逐帧随机闪烁。"""
    n = 220
    for k in range(n):
        x0 = rng.uniform(0, W)
        y0 = rng.uniform(0, H)
        sp = rng.uniform(28, 70)
        ln = rng.uniform(16, 40)
        yy = (y0 + t * sp * 24) % (H + 60) - 30
        draw.line([(x0, yy), (x0 - ln * 0.18, yy + ln)],
                  fill=(150, 190, 230), width=1)


def pose_woman(t):
    """女性姿态合成（0-24s 段）。"""
    from motion.character import sit, gait, run as R, jump, turn, gesture
    from motion.character import kick, crouch
    # 注意: motion.character 包的 __init__ 做了 `from .gait import *`,
    # 因此 `from motion.character import gait` 取到的是** gait 函数**而非 gait 模块
    # （同名遮蔽，与 render.py 之前踩的坑一致）。这里直接用函数。
    J = sit.sit_pose(0.0)
    if 5.0 <= t < 7.5:                      # 走
        J = gait((t - 5.0) * R.step_freq(1.4))
    elif 7.5 <= t < 10.5:                   # 跑
        J = gait((t - 5.0) * R.step_freq(3.2))
    elif 10.5 <= t < 12.0:                  # 急停
        J = gait((t - 5.0) * R.step_freq(3.2))
    elif 12.0 <= t < 15.0:                  # 跳
        J = jump.jump(t - 12.0, scale_h=1.0)
    elif 15.0 <= t < 18.0:                  # 转身180
        u = (t - 15.0) / 3.0
        # gait 是函数不是模块（包 __init__ 做了 from .gait import *，同名遮蔽），
        # gait.gait(0.0) 会 AttributeError —— 这里直接调用 gait(0.0)。
        J = gait(0.0)
        turn.turn_legs(J, u)
    elif 18.0 <= t < 24.0:                  # 挥手
        J = sit.sit_pose(0.0)
    return J


def render(start=0, end=NF, w=W, h=H, out=MP4):
    """90秒长镜头主循环：物理轨迹查表 + 连续相机 + 分层合成。

    渲染**不另写一套**：直接复用 showreel/render.py 的 compose()
    （缓存背景 → 远层雨 → 物理物体 → 角色离屏 alpha 合成 → 近层雨 → 辉光后处理）。
    原先本文件自绘 background/rain 并手写合成，与 render.py 形成两套重复实现，
    且 `Image.fromarray(cv.arr())` 传入 float32 数组（cv.arr() 是 float32），
    PIL 报错信息里带 "(1,1,3), |f4" —— 这是它被误读成"画布塌缩成 1×1"的真因。
    compose() 内部走 `cv.img.copy()`（uint8），从结构上不存在该问题。
    来源: 分层合成与离屏 alpha 取自 showreel/render.py:217 compose()；
          连续运镜取自 showreel/camrig.py CamRig(default_shots())。
    """
    from showreel.render import build_bg, props_from_world, compose
    from showreel.camrig import CamRig, default_shots
    global W, H
    W, H = w, h
    segs = load_traj()
    gp = P.GlobalParams()
    bg = build_bg(seed=7)
    rig = CamRig(default_shots())
    st = S.Street(dt=1.0 / 240.0, iters=10)
    bodies = st.world.bodies
    frames = []
    n = min(end, sum(a.shape[0] for a in segs))
    for i in range(start, n):
        t = i / float(FPS)
        snap = snap_at(segs, i)
        if snap.shape[0] > len(bodies):
            snap = snap[:len(bodies)]      # 新增物体待 props_from_world 支持后再放开
        _w = gp.wind(t) if hasattr(gp, "wind") else 0.0
        if isinstance(_w, (tuple, list, np.ndarray)):
            # wind 返回 (方向, 强度) 或 (wx, wy) —— 取强度标量
            wind = float(np.linalg.norm(np.asarray(_w[:2], dtype=float)))
        else:
            wind = float(_w)
        # 连续运镜：优先把跟随目标喂给 rig，失败则退化为纯时间样条
        try:
            cam = rig.cam(t, woman=(float(snap[0][0]), float(snap[0][1])))
        except TypeError:
            cam = rig.cam(t)
        props = props_from_world(bodies, snap=snap, i=i)
        actors = [(-1.0 + t * 0.16, 2.6, 0.0, pose_woman(t), dict(), 1.68)]
        frames.append(compose(t, cam, bg, props=props, actors=actors, wind=wind))
        if i % 60 == 0:
            print("[frame] %d t=%.2f" % (i, t))
    to_mp4(frames, out, fps=FPS)
    print("[ok] %s  frames=%d" % (out, len(frames)))
    return out


def main(argv):
    a = [x for x in argv[1:] if not x.startswith("--")]
    s = int(a[0]) if len(a) > 0 else 0
    e = int(a[1]) if len(a) > 1 else NF
    o = MP4
    if "--out" in argv:
        o = argv[argv.index("--out") + 1]
    return render(s, e, out=o)


if __name__ == "__main__":
    main(sys.argv)
