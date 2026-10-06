# 契约: proc/motion/character/cloth
#   一句话: 布料：Verlet 链、披帛/衣摆、draw_character 总入口
#   完整契约见 motion/character/__init__.py

import math
import numpy as np
from .render import draw_body, gait, gait_params, PROP, SOLE_LIFT
from motion import camera
from PIL import Image, ImageDraw



# ================================================================
# 五、次级运动（Verlet 链）—— 衣摆 / 飘带 / 头发
# ================================================================

class VerletChain:
    """Verlet 质点链 + 距离约束松弛

        p_{n+1} = 2 p_n - p_{n-1} + dt^2 * a
        约束松弛: delta *= 0.5 * (L - d) / d

    约束迭代次数决定刚度：1 次=软绳，20 次≈不可拉伸
    """

    def __init__(self, pts, seg_len=None, damp=0.985, iters=6,
                 gravity=(0.0, 260.0)):
        self.p = np.array(pts, dtype=np.float32)
        self.prev = self.p.copy()
        if seg_len is None:
            seg_len = np.linalg.norm(self.p[1:] - self.p[:-1], axis=1)
        self.L = np.asarray(seg_len, dtype=np.float32)
        self.damp = damp
        self.iters = iters
        self.g = np.array(gravity, dtype=np.float32)

    def step(self, dt=1 / 60.0, wind=(0.0, 0.0), anchor=None):
        n = len(self.p)
        v = (self.p - self.prev) * self.damp
        self.prev = self.p.copy()
        acc = self.g + np.asarray(wind, dtype=np.float32)
        self.p = self.p + v + acc * (dt * dt)

        if anchor is not None:
            self.p[0] = np.asarray(anchor, dtype=np.float32)
        for _ in range(self.iters):
            for i in range(n - 1):
                a, b = self.p[i], self.p[i + 1]
                delta = b - a
                dd = np.linalg.norm(delta) + 1e-9
                corr = delta * (0.5 * (self.L[i] - dd) / dd)
                if i != 0:
                    self.p[i] -= corr
                self.p[i + 1] += corr
        return self.p


# ================================================================
# 六、主入口
# ================================================================

def make_robe(attach, height_px):
    """衣摆 / 飘带链：锚点在腰与胸，长度按身高比例，不是拍脑袋的像素数。

    衣摆 damp 高、iters 多 → 厚重少摆；飘带 damp 低、iters 少 → 轻飘。
    """
    cx, cy = attach["chest"]
    wx, wy = attach["waist"]
    L = float(height_px)
    # 衣摆：自腰垂下，长度 ≈ 腰到膝（D&C: 腰0.560 膝0.285 → 0.275H）
    n_hem = 7
    hem = [[wx, wy + L * (0.275 * (i + 1) / n_hem)] for i in range(n_hem)]
    hem = [[wx, wy]] + hem
    # 飘带：自胸斜垂，长度 ≈ 0.22H
    n_s = 6
    sash = [[cx - L * 0.020 * (i + 1), cy + L * (0.22 * (i + 1) / n_s)]
            for i in range(n_s)]
    sash = [[cx, cy]] + sash
    return {
        "hem": VerletChain(hem, damp=0.972, iters=8, gravity=(0.0, 320.0)),
        "sash": VerletChain(sash, damp=0.955, iters=4, gravity=(0.0, 200.0)),
    }





def draw_character(cv, ctx, t=0.0, preset="natural", phase0=0.0,
                   x=None, y=None, height_px=None,
                   robe=(128, 74, 52), skin=(214, 176, 148),
                   attach=None, chains=None, wind=(0.0, 0.0), dt=1 / 60.0,
                   yaw=90.0, body_h=1.70):
    """人物表（2D）入口：正交相机 + 侧视。沿路走远请直接用 draw_body + 真相机。

    x,y: 脚底在屏幕的位置；height_px: 身高像素
    attach: dict，把飘带/衣摆的锚点返回给调用方（供 VerletChain 用）
    """
    ctx = ctx if ctx is not None else {"w": cv.w, "h": cv.h}
    P = gait_params(preset)
    ph = (phase0 + t / P["dur"]) % 1.0
    J = gait(ph, preset)

    H = height_px if height_px is not None else int(ctx["h"] * 0.30)
    if x is None:
        x = ctx["w"] * 0.5
    if y is None:
        y = ctx["h"] * 0.86

    # 正交相机：把"身高像素"换算成 像素/米
    vtop = float(J["head"][1]) + PROP["head_r"] * 1.12 + SOLE_LIFT
    s = H / max(vtop * body_h, 1e-6)
    cam = camera.OrthoCam(s=s, cx=float(x), y0=float(y))
    draw_body(cv, cam, J, Xc=0.0, Zc=10.0, yaw=yaw, body_h=body_h,
              robe=robe, skin=skin, chains=chains, wind=wind, dt=dt,
              attach=attach)
    return ph, J

__all__ = [n for n in dir() if not n.startswith("__")]
