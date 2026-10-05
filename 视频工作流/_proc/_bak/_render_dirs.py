# -*- coding: utf-8 -*-
import numpy as np, camera, character as C
from stage import bake
from PIL import Image
import subprocess, os
H=1.70; W,Hh=540,960; FPS=30
def seq(yaw, name, zs, secs=3.0):
    bg,geom=bake("城墙关隘"); cam=camera.fit(geom)
    n=int(secs*FPS); fr=[]
    P=C.gait_params("natural")
    for i in range(n):
        t=i/FPS; Z=zs(t) if callable(zs) else zs
        ph=(P["speed"]*t/P["step_m"]*0.5)%1.0
        cv=type("C",(),{"w":W,"h":Hh})()
        im=Image.fromarray(bg.copy()); cv_draw=None
        import cv2
        arr=np.array(im)
        # 用 canvas 包装
        class CV:
            pass
        c=CV(); c.w=W; c.h=Hh
        C.draw_character(c, {"w":W,"h":Hh}, phase0=ph, yaw=yaw, body_h=H)
        fr.append(None)
    return fr
print("skip")
