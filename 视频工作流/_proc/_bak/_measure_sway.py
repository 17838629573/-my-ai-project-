# -*- coding: utf-8 -*-
"""实测：根(髋)在 u(前后) / w(左右) 两轴的摆幅，换算成米和屏幕像素。"""
import numpy as np, math
import camera, character as C
from stage import bake

H = 1.70
bg, geom = bake("城墙关隘")
cam = camera.fit(geom)

for preset in ("natural",):
    P = C.gait_params(preset)
    us, ws, vs = [], [], []
    for i in range(120):
        J = C.gait(i / 120.0, preset)
        us.append(J["pelvis"][0] * H)
        ws.append(J["pelvis"][2] * H if len(J["pelvis"]) > 2 else 0.0)
        vs.append(J["pelvis"][1] * H)
    us, ws, vs = np.array(us), np.array(ws), np.array(vs)
    print("preset=%s  hip_sway参数=%.4f (归一化)" % (preset, P["hip_sway"]))
    print("  u(前后) 峰峰 %.4f m  幅度 %.4f m" % (np.ptp(us), np.ptp(us)/2))
    print("  w(左右) 峰峰 %.4f m  幅度 %.4f m" % (np.ptp(ws), np.ptp(ws)/2))
    print("  v(上下) 峰峰 %.4f m  幅度 %.4f m" % (np.ptp(vs), np.ptp(vs)/2))
    # 侧视 yaw=90：u→屏幕x
    Z = 4.2
    px = cam.px_per_m(Z)
    xs = [C.project_body(C.gait(i/120.0, preset), cam, Zc=Z, yaw=90.0, body_h=H)["pelvis"][0]
          for i in range(120)]
    xs = np.array(xs)
    print("  侧视屏幕 骨盆x 峰峰 %.1f px (px_per_m=%.1f)" % (np.ptp(xs), px))
    print("  侧视屏幕 脚x 峰峰 ", end="")
    fx = np.array([C.project_body(C.gait(i/120.0, preset), cam, Zc=Z, yaw=90.0, body_h=H)["ank_l"][0]
                   for i in range(120)])
    print("%.1f px" % np.ptp(fx))
