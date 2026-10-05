# 契约: proc/motion/character/render
#   一句话: 渲染：相机投影、SDF 场栅格化、法线明暗着色
#   完整契约见 motion/character/__init__.py

import math
import numpy as np
from .sdf import *
from .proportions import *
from .joints import *
from .leg import *
from .gait import *
from PIL import Image, ImageDraw
from motion import camera



def project_body(J, cam, Xc=0.0, Zc=10.0, yaw=90.0, body_h=1.70):
    """归一化 (u,v,w) 关节 → 屏幕像素。

    关节先在身体局部绕竖直轴转 yaw，再平移到世界 (Xc,Zc)，最后交给相机投影。
        yaw =   0°  背对镜头（朝画面深处走远）  ← 沿路走远用这个
        yaw =  90°  纯侧视（人物表 / 横向走过）
        yaw = 180°  正对镜头走来
    返回 {name: (sx, sy, s)}，s 是该点的 **像素/米**（半径缩放要用）。
    """
    th = math.radians(yaw)
    st, ct = math.sin(th), math.cos(th)
    out = {}
    for k, j in J.items():
        u, v, w = float(j[0]), float(j[1]), float(j[2] if len(j) > 2 else 0.0)
        U = u * body_h                 # 前向 → 米
        V = (v + SOLE_LIFT) * body_h   # 离地高度 → 米（脚底对齐地面）
        Wd = w * body_h                # 侧向 → 米
        X = Xc + U * st + Wd * ct
        Z = Zc + U * ct - Wd * st
        sx, sy, s = cam.proj(X, Z, V)
        out[k] = (float(sx), float(sy), float(s))
    return out


def body_geometry(Jp, body_h=1.70):
    """屏幕关节 → 胶囊表（像素）。半径按各自深度的 像素/米 缩放。"""
    caps = []
    for a, b, r in BODY_SPEC:
        ax, ay, sa = Jp[a]
        bx, by, sb = Jp[b]
        caps.append((float(ax), float(ay), float(bx), float(by),
                     max(r * body_h * 0.5 * (sa + sb), 0.8)))
    hx, hy, hs = Jp["head"]
    ell = [(float(hx), float(hy),
            max(PROP["head_r"] * 0.86 * body_h * hs, 1.0),
            max(PROP["head_r"] * 1.12 * body_h * hs, 1.0))]
    for side in ("l", "r"):
        ax, ay, as_ = Jp["ank_" + side]
        tx, ty, ts = Jp["toe_" + side]
        caps.append((float(ax), float(ay), float(tx), float(ty),
                     max(0.024 * body_h * 0.5 * (as_ + ts), 0.8)))
    sm = max(0.030 * body_h * max(s for _, _, s in Jp.values()), 0.5)
    return caps, ell, sm


def field_px(caps, ell, smooth, pad=6.0):
    """在**屏幕像素网格**上建 SDF。返回 (d, (x0, y0), d_head)。

    头单独存一份 d_head，用来做肤色蒙版（不再按"上 1/5 切一条线"瞎切）。
    """
    xs, ys, rs = [], [], []
    for ax, ay, bx, by, r in caps:
        xs += [ax, bx]; ys += [ay, by]; rs.append(r)
    for cx, cy, rx, ry in ell:
        xs += [cx - rx, cx + rx]; ys += [cy - ry, cy + ry]; rs.append(max(rx, ry))
    m = 2.0 * max(rs) + pad
    x0 = float(int(min(xs) - m)); y0 = float(int(min(ys) - m))
    W = max(8, int(max(xs) + m - x0)); H = max(8, int(max(ys) + m - y0))
    gx = np.arange(W, dtype=np.float32) + x0
    gy = np.arange(H, dtype=np.float32) + y0
    PX, PY = np.meshgrid(gx, gy)
    d = np.full((H, W), 1e6, np.float32)
    for ax, ay, bx, by, r in caps:
        d = smin(d, sd_capsule(PX, PY, ax, ay, bx, by, r), k=smooth)
    dh = None
    for cx, cy, rx, ry in ell:
        e = sd_ellipse(PX, PY, cx, cy, rx, ry)
        dh = e if dh is None else np.minimum(dh, e)
        d = smin(d, e, k=smooth)
    if dh is None:
        dh = np.full((H, W), 1e6, np.float32)
    return d, (x0, y0), dh


def _anchors(Jp, body_h, attach=None):
    """投影后的躯干锚点（供 Verlet 链挂点）。

    按投影后的真实像素位置，不再按"贴图的几分之几" —— 否则链子会从身上飘出去。
    返回原 attach 字典（就地写入），并附 s(像素/米) 与 hp(身高像素) 供链子定尺寸。
    """
    att = attach if attach is not None else {}
    att["chest"] = (Jp["chest"][0], Jp["chest"][1])
    att["waist"] = (Jp["waist"][0], Jp["waist"][1])
    att["head"] = (Jp["head"][0], Jp["head"][1])
    att["cx"] = float(np.mean([Jp[k][0] for k in ("pelvis", "waist", "chest", "neck")]))
    att["s"] = float(Jp["pelvis"][2])           # 像素/米，给链子定粗细
    att["hp"] = body_h * att["s"]               # 身高像素，布料宽度按它缩放
    return att


def _blit(cv, d, col, ox, oy):
    """把 SDF 的 alpha 与着色结果合成到画布（只碰画面内的那块矩形）。"""
    a = np.asarray(cv.img, dtype=np.float32)
    hh, ww = d.shape
    px, py = int(round(ox)), int(round(oy))
    x0, y0 = max(0, px), max(0, py)
    x1, y1 = min(cv.w, px + ww), min(cv.h, py + hh)
    if x1 <= x0 or y1 <= y0:
        return
    sub_a = (d < 0)[y0 - py:y1 - py, x0 - px:x1 - px].astype(np.float32)
    sub_c = col[y0 - py:y1 - py, x0 - px:x1 - px]
    al = sub_a[:, :, None]
    a[y0:y1, x0:x1] = a[y0:y1, x0:x1] * (1 - al) + sub_c * al
    cv.img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    cv.d = ImageDraw.Draw(cv.img)


def _step_chains(chains, dt, wind, att):
    """推进 Verlet 链：hem 挂腰、sash 挂胸，各自跟自己的锚点。"""
    for name, key in (("hem", "waist"), ("sash", "chest")):
        if name in chains:
            chains[name].step(dt=dt, wind=wind, anchor=att[key])


def draw_body(cv, cam, J, Xc=0.0, Zc=10.0, yaw=90.0, body_h=1.70,
              robe=(128, 74, 52), skin=(214, 176, 148),
              chains=None, wind=(0.0, 0.0), dt=1 / 60.0, attach=None,
              hem_scale=None):
    """统一渲染入口：任何相机 / 任何朝向 / 任何深度都用这一条。

    层序遵循 2D 合成惯例：Fill(SDF 着色) → Children(衣摆/飘带) → 再交由上层描边。
    """
    Jp = project_body(J, cam, Xc=Xc, Zc=Zc, yaw=yaw, body_h=body_h)
    caps, ell, sm = body_geometry(Jp, body_h)
    d, (ox, oy), dh = field_px(caps, ell, sm)

    col = shade_sdf(d, robe)
    hm = dh < 0.0
    if np.any(hm):
        sk = shade_sdf(np.where(hm, dh, 1e6), skin)
        col = np.where(hm[..., None], sk, col)
    _blit(cv, d, col, ox, oy)

    _att = _anchors(Jp, body_h, attach)

    if chains:
        _step_chains(chains, dt, wind, _att)
        wpx = max(2, int((hem_scale or 0.020) * body_h * _att["s"]))
        if wpx >= 2:
            _draw_chains(cv, chains, robe, wpx, height_px=_att.get("hp"))
    return Jp


# ================================================================
# 四、着色（inflate 伪 3D 法线）
# ================================================================

def shade_sdf(d, base_rgb, light=(-0.55, -0.62, 0.56), amb=0.42,
              rim_pow=2.6, rim_amt=0.34, d_max=None):
    """由 SDF 直接算伪 3D 法线并着色。

    边缘 nz=0（垂直视线，与 Lumo 的轮廓边界条件一致）
    中心 nz=1（朝向观察者）
    → 一个圆被着色成一个球
    """
    inside = d < 0.0
    if not inside.any():
        return np.zeros((*d.shape, 3), dtype=np.float32)

    if d_max is None:
        d_max = max(-d[inside].min(), 1e-6)
    t = np.clip(-d / d_max, 0.0, 1.0)           # 归一化内距

    # 2D 梯度（中心差分）
    gy, gx = np.gradient(d)
    gl = np.sqrt(gx * gx + gy * gy) + 1e-9
    nx, ny = gx / gl, gy / gl                    # 指向外

    nz = np.sqrt(np.clip(1.0 - (1.0 - t) ** 2, 0.0, 1.0))
    k = np.sqrt(np.clip(1.0 - nz * nz, 0.0, 1.0))
    Nx, Ny, Nz = nx * k, ny * k, nz

    L = np.array(light, dtype=np.float32)
    L = L / (np.linalg.norm(L) + 1e-9)
    lam = np.clip(Nx * L[0] + Ny * L[1] + Nz * L[2], 0.0, 1.0)

    rim = np.clip(1.0 - nz, 0.0, 1.0) ** rim_pow

    base = np.asarray(base_rgb, dtype=np.float32)[None, None, :]
    col = base * (amb + (1.0 - amb) * lam[:, :, None])
    col = col + rim[:, :, None] * rim_amt * 255.0
    col[~inside] = 0.0
    return np.clip(col, 0, 255)

def _draw_chains(cv, chains, color, width, height_px=None):
    """把链画成**有宽度的布料**，不是细线。

    之前只画 width 递减的多段线 → 屏幕上就是两根细长条，看着像尾巴。
    布料必须有横向铺开：沿链求法向，左右各偏半个"半宽"，连成闭合多边形。
    """
    dr = cv.d
    L = float(height_px or width * 40.0)
    for name, ch in chains.items():
        p = np.asarray(ch.p, dtype=np.float64)
        n = len(p)
        # 半宽：衣摆是下摆散开的裙（下宽上窄），飘带是窄带（梢更窄）
        if name == "hem":
            hw = L * np.linspace(0.075, 0.115, n)
        else:
            hw = L * np.linspace(0.016, 0.006, n)
        tan = np.vstack([p[1:] - p[:-1], p[-1] - p[-2]])
        ln = np.linalg.norm(tan, axis=1) + 1e-9
        nrm = np.stack([-tan[:, 1] / ln, tan[:, 0] / ln], axis=1)
        left = p + nrm * hw[:, None]
        right = p - nrm * hw[:, None]
        poly = np.vstack([left, right[::-1]])
        dr.polygon([tuple(v) for v in poly], fill=color)
        # 下摆/带梢压一道暗边，布料才有厚度
        dr.line([tuple(v) for v in right], fill=tuple(int(c * 0.72) for c in color),
                width=max(1, int(L * 0.006)))

__all__ = [n for n in dir() if not n.startswith("__")]
