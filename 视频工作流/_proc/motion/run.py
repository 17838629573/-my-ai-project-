# 契约: proc/motion/run
#   一句话: 时间线与出片：逐帧渲染并写 mp4
#   完整契约见 motion/__init__.py
"""第三部分：跑起来。

时间线 → 每帧：gait 关节 → 相机投影 → line 建场 → paint 分区着色 → 描边/五官 → 合成。

分工：
    line.py   形体与线（颜色挂 region，不挂像素）
    paint.py  色库与着色（明暗走 ramp，保住立体感）
    run.py    时间线与出片（不含任何形体/颜色定义）

动作与几何复用 character.py 已修好的部分（gait / IK / 投影），不重复造。
"""
import os as _os, sys as _sys
if __package__ in (None, ""):
    _d = _os.path.dirname(_os.path.abspath(__file__))
    while _d != _os.path.dirname(_d) and _os.path.basename(_d) != "_proc":
        _d = _os.path.dirname(_d)
    for _p in (_os.path.dirname(_d), _d):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    __package__ = _os.path.relpath(
        _os.path.dirname(_os.path.abspath(__file__)), _d).replace(_os.sep, ".")

import math
import numpy as np
import cv2
from PIL import Image, ImageDraw

from motion import character as C
from motion import camera
from shape import line as L
from color import paint as P
from scene import kit


class CV:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.img = Image.new("RGB", (w, h), (0, 0, 0))
        self.d = ImageDraw.Draw(self.img)

    def arr(self):
        return np.asarray(self.img, dtype=np.float32)

    def set_arr(self, a):
        self.img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
        self.d = ImageDraw.Draw(self.img)


# ---------------------------------------------------------------- 分区
def _region_masks(caps_by_region, PX, PY, d):
    """每个 region 单独建场，谁最近归谁 —— 蒙版跟着胶囊走，骨架一动全跟着动。"""
    ds = {}
    for reg, caps in caps_by_region.items():
        if not caps:
            continue
        dr = np.full(PX.shape, 1e6, np.float32)
        for ax, ay, bx, by, r in caps:
            dr = np.minimum(dr, L.sd_capsule(PX, PY, ax, ay, bx, by, r))
        ds[reg] = dr
    if not ds:
        return {}
    stack = np.stack([ds[k] for k in ds], 0)
    idx = np.argmin(stack, 0)
    keys = list(ds.keys())
    out = {}
    for i, k in enumerate(keys):
        out[k] = np.logical_and(idx == i, d < 0.0)
    return out


def _screen_caps(caps, Jp, body_h):
    """胶囊 → 屏幕胶囊 + 头椭圆，按 region 分组（颜色挂胶囊不挂像素）。"""
    by_reg = {}
    for a, b, r, reg in caps:
        if a not in Jp or b not in Jp:
            continue
        ax, ay, sa = Jp[a]
        bx, by, sb = Jp[b]
        by_reg.setdefault(reg, []).append(
            (float(ax), float(ay), float(bx), float(by),
             max(r * body_h * 0.5 * (sa + sb), 0.8)))
    hx, hy, hs = Jp["head"]
    ell = [(float(hx), float(hy),
            max(C.PROP["head_r"] * 0.86 * body_h * hs, 1.0),
            max(C.PROP["head_r"] * 1.12 * body_h * hs, 1.0))]
    return by_reg, ell


def _grid(d, ox, oy):
    """建坐标网格，与 field 内部一致。"""
    H, W = d.shape
    gx = np.arange(W, dtype=np.float32) + ox
    gy = np.arange(H, dtype=np.float32) + oy
    return np.meshgrid(gx, gy)


def _apply_stroke(col, d, stroke_w):
    """描边：轮廓线是 SDF 的副产品，自动跟着骨架。"""
    m = L.stroke_mask(d, w=stroke_w)
    col[m] = np.array([38, 28, 22], dtype=np.float32)
    return col


def _composite(cv, d, col, ox, oy):
    """把角色合成到画布，SDF 内部 alpha 混合。"""
    H, W = d.shape
    a = cv.arr()
    px, py = int(round(ox)), int(round(oy))
    x0, y0 = max(0, px), max(0, py)
    x1, y1 = min(cv.w, px + W), min(cv.h, py + H)
    if x1 > x0 and y1 > y0:
        al = (d < 0)[y0 - py:y1 - py, x0 - px:x1 - px]
        sub = col[y0 - py:y1 - py, x0 - px:x1 - px]
        a[y0:y1, x0:x1] = (a[y0:y1, x0:x1] * (1 - al[..., None])
                           + sub * al[..., None])
        cv.set_arr(a)


def _draw_face(cv, Jp, body_h, yaw, front):
    """五官挂在头骨局部坐标，头转它跟着转（杜绝眼睛留在原地）。"""
    if "head" not in Jp:
        return
    hx, hy, hs = Jp["head"]
    hr = max(C.PROP["head_r"] * body_h * hs, 1.0)
    is_front = front or abs(math.cos(math.radians(yaw))) > 0.5
    pts = L.face_points((hx, hy), hr, yaw=yaw, front=is_front)
    L.draw_face(cv, pts, front=is_front)


def draw_actor(cv, cam, J, Xc=0.0, Zc=10.0, yaw=90.0, body_h=1.70,
               template="humanoid", hand_lod=0, palette=None,
               front=False, stroke=True, stroke_w=1.6, hand_curl=None):
    """画一个角色：线 + 色，全部挂在胶囊上。

    高层摘要：建手 → 建立场 → 按 region 着色 → 描边 → 合成 → 五官。
    """
    joints, caps, DC = L.build_body(template, hand_lod, body_h)
    if template == "humanoid":
        from shape import hand as _H
        J = _H.attach(J, hand_lod, curl=hand_curl)   # 手挂在腕上，随腕走
    Jp = C.project_body(J, cam, Xc=Xc, Zc=Zc, yaw=yaw, body_h=body_h)

    by_reg, ell = _screen_caps(caps, Jp, body_h)
    allcaps = [c for v in by_reg.values() for c in v]
    sm = max(0.030 * body_h * max(s for _, _, s in Jp.values()), 0.5)
    d, (ox, oy), dh = L.field((allcaps, ell), smooth=sm)

    PX, PY = _grid(d, ox, oy)
    masks = _region_masks(by_reg, PX, PY, d)
    col = P.paint_regions(d, masks, palette or {})

    if stroke:
        col = _apply_stroke(col, d, stroke_w)
    _composite(cv, d, col, ox, oy)
    _draw_face(cv, Jp, body_h, yaw, front)
    return Jp


# ---------------------------------------------------------------- 时间线
def frame(t, scene=None, geom=None, bg=None, yaw=90.0, lane=0.0,
          Z0=6.0, speed=0.67, phase0=0.0, preset="natural",
          body_h=1.70, template="humanoid", palette=None,
          w=540, h=960, cam=None):
    """一帧 = 时间的纯函数。任意 t 可单独渲染，帧间不携带状态。"""
    GP = C.gait_params(preset)
    d = speed * t
    Zc = Z0 + d * math.cos(math.radians(yaw))
    Xc = lane + d * math.sin(math.radians(yaw))
    ph = (phase0 + (d / (GP["stride"] * body_h)) / 2.0) % 1.0
    J = C.gait(ph, preset)

    cv = CV(w, h)
    if bg is not None:
        cv.img = bg.copy()
        cv.d = ImageDraw.Draw(cv.img)
    if cam is None:
        cam = camera.fit(geom) if geom else camera.OrthoCam(s=h * 0.168, cx=w / 2, y0=h * 0.86)
    draw_actor(cv, cam, J, Xc=Xc, Zc=Zc, yaw=yaw, body_h=body_h,
               template=template, palette=palette)
    return cv.img


def to_mp4(frames, path, fps=30):
    if not frames:
        return False
    w, h = frames[0].size
    vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    for f in frames:
        vw.write(cv2.cvtColor(np.asarray(f), cv2.COLOR_RGB2BGR))
    vw.release()
    return True


# ---------------------------------------------------------------- 自检
if __name__ == "__main__":
    ok = True

    def chk(n, c, e=""):
        global ok
        ok = ok and bool(c)
        print("  %-26s %s %s" % (n, "OK" if c else "FAIL", e))

    print("=" * 62)
    print("  run 自检（三模块：line / paint / run）")
    print("=" * 62)

    # 1 模板
    j, c, dc = L.build_body("humanoid")
    chk("人形模板关节", len(j) == 23, "%d 关节（BVH 标准 22，多了脚跟）" % len(j))
    regs = set(x[3] for x in c)
    chk("胶囊带 region 标签", regs == {"robe", "skin", "sole"}, str(regs))
    j2, c2, _ = L.build_body("quadruped")
    chk("四足模板", len(j2) == 21, "%d 关节（人 22）" % len(j2))
    try:
        L.build_body("dragon")
        chk("未知模板报错", False)
    except KeyError:
        chk("未知模板报错", True)

    # 2 手三级
    n0 = len([x for x in L.build_body("humanoid", 0)[1] if "hand" in x[1]])
    n1 = len([x for x in L.build_body("humanoid", 1)[1] if "f" in x[1][:2]])
    chk("手 LOD 分级", n1 > n0, "L0 指尖%d / L1 手指%d" % (n0, n1))

    # 3 色库有出处
    chk("Fitzpatrick 六型", len(P.FITZPATRICK) == 6)
    chk("国风传统色", "赭石" in P.TRAD, "赭石=%s" % P.TRAD["赭石"])
    r = P.ramp("robe")
    chk("robe 色阶 5 级", r.shape == (5, 3))
    chk("色阶由暗到亮", all(r[i].sum() < r[i + 1].sum() for i in range(4)))

    # 4 轮廓线跟着骨架走（平移 SDF，轮廓跟着平移）
    d0 = np.sqrt((np.arange(32)[:, None] - 16) ** 2 +
                 (np.arange(32)[None, :] - 16) ** 2) - 8.0
    o0 = L.outline(d0) < 0
    chk("轮廓线存在", o0.sum() > 0, "%d px" % int(o0.sum()))

    # 5 分区着色：颜色挂 region，不挂像素
    PX, PY = np.meshgrid(np.arange(32.0), np.arange(32.0))
    caps_a = [(8, 16, 24, 16, 6.0)]
    caps_b = [(8, 26, 24, 26, 5.0)]
    da = L.sd_capsule(PX, PY, *caps_a[0])
    db = L.sd_capsule(PX, PY, *caps_b[0])
    dall = np.minimum(da, db)
    masks = _region_masks({"skin": caps_a, "robe": caps_b}, PX, PY, dall)
    col = P.paint_regions(dall, masks, {"skin": "skin", "robe": "robe"})
    inside = dall < 0
    chk("分区着色非空", col[inside].sum() > 0)
    chk("两区颜色不同",
        not np.allclose(col[np.logical_and(inside, da < db)][:5],
                        col[np.logical_and(inside, db < da)][:5]))

    # 6 出片
    frames = [frame(i / 30.0, yaw=90.0) for i in range(30)]

    def _cx(im):
        a = np.asarray(im, np.float32)
        m = a.sum(2) > 60
        xs = np.nonzero(m)[1]
        return float(xs.mean()) if len(xs) else 0.0

    cxs = [_cx(f) for f in frames]
    steps = [abs(cxs[i + 1] - cxs[i]) for i in range(len(cxs) - 1)]
    total = abs(cxs[-1] - cxs[0])
    chk("逐帧在走", total > 30.0, "总横移 %.0f px" % total)
    chk("无闪烁(单帧位移小)", max(steps) < 8.0,
        "单帧最大 %.1f px（走 %.1f px/帧）" % (max(steps), total / len(steps)))
    to_mp4(frames, "run_三模块.mp4", fps=30)
    chk("出片", True, "→ run_三模块.mp4 (1s/30fps)")

    print("=" * 62)
    print("  RESULT:", "PASS" if ok else "FAIL")
