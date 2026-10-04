# -*- coding: utf-8 -*-
"""脚部特写索引：12 帧，标出脚跟(蓝)/脚尖(黄)，验证脚全程朝前不翻转。"""
import numpy as np
import character as C
import camera
import kit
from PIL import Image, ImageDraw

W, Hh = 200, 340
tiles = []
for i in range(12):
    ph = i / 12.0
    cv = kit.Canvas(W, Hh, (28, 34, 48))
    J = C.gait(ph)
    vtop = float(J["head"][1]) + C.PROP["head_r"] * 1.12 + C.SOLE_LIFT
    s = 250 / max(vtop * 1.70, 1e-6)
    cam = camera.OrthoCam(s=s, cx=W * 0.5, y0=Hh * 0.90)
    Jp = C.project_body(J, cam, Xc=0.0, Zc=10.0, yaw=90.0, body_h=1.70)
    C.draw_body(cv, cam, J, yaw=90.0, body_h=1.70)
    d = ImageDraw.Draw(cv.img)
    gy = Hh * 0.90
    d.line([(0, gy), (W, gy)], fill=(120, 130, 150), width=1)
    for side in ("l", "r"):
        if "toe_" + side not in Jp:
            continue
        t = Jp["toe_" + side]
        h = Jp["heel_" + side]
        d.line([(h[0], h[1]), (t[0], t[1])], fill=(255, 70, 70), width=3)
        d.ellipse([t[0] - 4, t[1] - 4, t[0] + 4, t[1] + 4], fill=(255, 220, 0))
        d.ellipse([h[0] - 4, h[1] - 4, h[0] + 4, h[1] + 4], fill=(60, 160, 255))
    d.text((4, 4), "ph=%.2f" % ph, fill=(255, 255, 255))
    tiles.append(cv.img)

sheet = Image.new("RGB", (W * 6, Hh * 2), (18, 22, 32))
for i, im in enumerate(tiles):
    sheet.paste(im, ((i % 6) * W, (i // 6) * Hh))
sheet.save("脚部特写_12帧.png")
print("saved 脚部特写_12帧.png")

# 数据核对
print("\nphs   脚尖-脚跟 x差(应>0)  pitch°")
for i in range(12):
    ph = i / 12.0
    pit = C.foot_pitch(ph)
    J = C.gait(ph)
    ok = "OK" if np.cos(pit) > 0 else "翻!"
    print(" %.2f   cos=%+.3f %s    %+7.1f" % (ph, np.cos(pit), ok, np.degrees(pit)))
