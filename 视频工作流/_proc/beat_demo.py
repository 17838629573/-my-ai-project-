# 契约: proc/(root)/beat_demo
#   一句话: 入口脚本：走 beat 时间线出演示片
#   完整契约见 (root)/__init__.py
# -*- coding: utf-8 -*-
"""W1 验证：用 beat 时间线串 4 段动作，出 12 秒片。
提示词的 4 个动作段（坐/翻页/起身走/坐下）能力表还没有，只能用 walk 填满，
但这一段证明「时间线能把多段串起来、跨段不跳、朝向能转」。
"""
import numpy as np
from PIL import Image, ImageDraw
from scene import kit
from motion import camera, run, beat

W, H, FPS = 540, 960, 30
scene = {"name": "城墙关隘", "layers": [
    {"t": "sky"}, {"t": "cloud", "coverage": 0.35}, {"t": "mountain", "layers": 4},
    {"t": "ground"}, {"t": "city", "n": 14, "rows": 2}, {"t": "road", "half_near": 0.26}]}
bg, geom = kit.compose(scene, W, H)
cam = camera.fit(geom)

SP = 0.67
tl = beat.Timeline()
# 段起点必须接上一段终点，否则转身瞬间位置跳
tl.add("walk", 0, 3, params={"speed": SP, "dur": 3.0}, bid="1走近",
       root={"X0": 0.0, "Z0": 9.00, "yaw": 180.0}, blend_in=0.5, blend_out=0.5)
tl.add("walk", 3, 6, params={"speed": SP, "dur": 3.0}, bid="2转身走远",
       root={"X0": 0.0, "Z0": 6.99, "yaw": 0.0}, blend_in=0.5, blend_out=0.5)
tl.add("walk", 6, 9, params={"speed": SP, "dur": 3.0}, bid="3再走近",
       root={"X0": 0.0, "Z0": 9.00, "yaw": 180.0}, blend_in=0.5, blend_out=0.5)
tl.add("walk", 9, 12, params={"speed": 0.45, "dur": 3.0}, bid="4侧向离场",
       root={"X0": 0.0, "Z0": 6.99, "yaw": 90.0}, blend_in=0.5, blend_out=0.5)

frames, poses = [], []
for i in range(FPS * 12):
    t = i / FPS
    J, Xc, Zc, yaw = tl.solve(t)
    poses.append((Xc, Zc, yaw))
    cv = run.CV(W, H)
    cv.img = bg.copy()
    cv.d = ImageDraw.Draw(cv.img)
    run.draw_actor(cv, cam, J, Xc=Xc, Zc=Zc, yaw=yaw,
                   body_h=1.70, template="humanoid", palette=None)
    frames.append(cv.img)

run.to_mp4(frames, "W1_时间线_4段12秒.mp4", FPS)

# 索引图：每 1 秒取一帧
idx = Image.new("RGB", (W * 4, H // 4 * 3), "white")
for k, f in enumerate(frames[::FPS][:12]):
    idx.paste(f.resize((W, H // 4)), ((k % 4) * W, (k // 4) * (H // 4)))
idx.save("W1_时间线_每秒一格.png")

# 验证
a = np.stack([np.asarray(f, dtype=float) for f in frames])
diff = np.abs(a[1:] - a[:-1]).mean(axis=(1, 2))
p = np.array(poses)
print("段数           4")
print("总帧           %d" % len(frames))
print("帧间差 均值    %.3f  最大 %.3f" % (diff.mean(), diff.max()))
print("X 轨迹         %.2f → %.2f" % (p[0, 0], p[-1, 0]))
print("Z 轨迹         %.2f → %.2f" % (p[0, 1], p[-1, 1]))
print("yaw 轨迹       %.0f → %.0f" % (p[0, 2], p[-1, 2]))
jz = np.abs(np.diff(p[:, 1])).max()
jx = np.abs(np.diff(p[:, 0])).max()
print("位置单帧最大跳 Z %.4f m  X %.4f m" % (jz, jx))
print("里程            %.2f m（4段合计 0.67*9+0.45*3=7.38）" % tl.mileage(12.0))
