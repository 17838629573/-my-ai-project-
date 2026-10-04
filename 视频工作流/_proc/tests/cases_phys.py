"""C 组物理用例（弹球 / 两球对撞）

契约: tests/cases_phys
  输入: 无（用例自带固定参数，无需随机）
  输出: (checks, extra)——checks 交 harness.report，extra 为补充事实
  依赖: numpy, PIL, motion.rigid, tests.harness, motion.run
  被依赖: tests/run_all
  约束: 判据阈值一律取自 harness.CRIT，不许就地拍数；
        积分统一用 motion.rigid.FIXED_DT；渲染走 motion.run.to_mp4
  校验: python -m tests.run_all
"""
import os
from PIL import Image, ImageDraw
import motion.rigid as RG
from motion.run import to_mp4
import tests.harness as H

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _phys_frames(tracks, ground_y, span_m, W=640, HH=360):
    """纯刚体侧视图：世界米 -> 像素。tracks: {名: [(x_m, y_m, r_m)]}"""
    pad = 0.12 * span_m
    x0, x1 = -pad, span_m + pad
    s = min(W / (x1 - x0), HH / (span_m + pad))
    out = []
    n = min(len(v) for v in tracks.values())
    for i in range(n):
        im = Image.new("RGB", (W, HH), (238, 238, 234))
        d = ImageDraw.Draw(im)
        gy = HH - ground_y * s
        d.line([(0, gy), (W, gy)], fill=(120, 100, 80), width=2)
        for k, seq in tracks.items():
            x, y, r = seq[i]
            cx, cy = (x - x0) * s, HH - y * s
            rr = max(r * s, 2.0)
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                      fill=(216, 96, 72), outline=(70, 60, 55), width=2)
            d.text((cx - 4, cy - 4), k[:1], fill=(40, 40, 40))
        out.append(im)
    return out


def _save_mp4(frames, prefix, fps=60):
    p = os.path.join(OUT, "%s.mp4" % prefix)
    to_mp4(frames, p, fps)
    return p


def case_C18():
    """弹球：反弹高度逐次衰减 = 前一次 e^2，不穿地，不增能"""
    h0, e, T = 1.20, 0.75, 4.0
    b = RG.Body(p=h0 + 0.11, v=0.0, r=0.11, e=e)
    dt = RG.FIXED_DT
    hs, vs, peaks = [], [], []
    prev_v = 0.0
    for _ in range(int(round(T / dt)) + 1):
        if prev_v > 0.0 and b.v <= 0.0:
            peaks.append(b.p + b.v * b.v / (2.0 * RG.G) - b.r)
        prev_v = b.v
        RG.integrate(b, dt)
        RG.collide_ground(b, 0.0)
        hs.append(b.p)
        vs.append(b.v)
    pk = peaks[:4]
    err = H.restitution_err(pk, e)
    states = [(1.0, (0.0, vs[i]), hs[i]) for i in range(len(hs))]
    eg = H.energy_gain(states)
    pen = max(0.0, 0.11 - min(hs))
    checks = [("restitution_err", err), ("energy_gain", eg),
              ("penetration_m", pen)]
    tracks = {"ball": [(0.0, hs[i], 0.11) for i in range(len(hs))]}
    mp4 = _save_mp4(_phys_frames(tracks, 0.0, 1.4), "C18_弹球")
    return checks, {"mp4": mp4,
                    "峰值_离地_m": [round(float(x), 4) for x in pk],
                    "理论_e2衰减": [round(h0 * e ** (2 * k), 4)
                                 for k in range(len(pk))]}


def case_C20():
    """两球对撞：等质量交换速度、异质量动量守恒，不穿模"""
    res, tracks = {}, {}
    dt = 1.0 / 240.0
    for tag, m1, m2, v1, v2 in (("a", 1.0, 1.0, 2.0, -1.0),
                                ("b", 2.0, 1.0, 3.0, -1.0)):
        a = RG.Body(p=-0.60, v=v1, m=m1, r=0.11, e=1.0)
        b = RG.Body(p=0.60, v=v2, m=m2, r=0.11, e=1.0)
        before = [(m1, (v1, 0.0)), (m2, (v2, 0.0))]
        pen, tk1, tk2 = 0.0, [], []
        for _ in range(2000):
            RG.collide_pair(a, b)
            a.p += a.v * dt
            b.p += b.v * dt
            pen = max(pen, (a.r + b.r) - abs(b.p - a.p))
            tk1.append((a.p, 0.11, a.r))
            tk2.append((b.p, 0.11, b.r))
            if b.p - a.p > 1.2:
                break
        after = [(m1, (a.v, 0.0)), (m2, (b.v, 0.0))]
        res[tag] = (H.momentum_err(before, after), pen, a.v, b.v)
        tracks[tag + "1"], tracks[tag + "2"] = tk1, tk2
    me = max(res["a"][0], res["b"][0])
    pn = max(res["a"][1], res["b"][1])
    swap = (abs(res["a"][2] + 1.0) < 1e-9 and abs(res["a"][3] - 2.0) < 1e-9)
    checks = [("momentum_err", me), ("penetration_m", pn)]
    mp4 = _save_mp4(_phys_frames({"a1": tracks["a1"], "a2": tracks["a2"]},
                                 0.0, 1.6), "C20_两球对撞")
    return checks, {"mp4": mp4, "等质量交换速度": swap,
                    "等质量末速": (round(res["a"][2], 6), round(res["a"][3], 6)),
                    "异质量末速": (round(res["b"][2], 6), round(res["b"][3], 6))}
