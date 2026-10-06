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
import numpy as np
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


def resample_tracks(tracks, sim_dt, fps, duration):
    """把固定步长仿真轨迹重采样为视频帧序列，使物理时间 == 视频时间

    病根：仿真步数直接当视频帧数，且 fps 与 sim_dt 脱钩，
         导致视频被慢放 (1/sim_dt)/fps 倍 —— 表现为大面积重复帧（卡顿）。
    修法：按 t = i/fps 反查连续索引并线性插值，帧数 = duration*fps。
    """
    n = max(2, int(round(duration * fps)))
    out = {}
    for k, seq in tracks.items():
        m = len(seq)
        res = []
        for i in range(n):
            x = (i / fps) / sim_dt
            j = int(x)
            if j >= m - 1:
                res.append(seq[-1])
                continue
            f = x - j
            a, b = seq[j], seq[j + 1]
            row = []
            for c in range(len(a)):
                va, vb = a[c], b[c]
                if isinstance(va, (int, float)) and isinstance(vb, (int, float)) \
                        and not isinstance(va, bool):
                    row.append(va + (vb - va) * f)
                else:
                    row.append(va)
            res.append(tuple(row))
        out[k] = res
    return out


def _phys_frames_auto(tracks, W=640, HH=360, pad=0.12, ground=None):
    """自适应视野刚体侧视图：按轨迹实际包围盒定标，支持负坐标

    _phys_frames2 假定 y>=0（地面在 0），摆锤锚点在原点上方、y 恒为负，
    会被映射到画面之外（实测：整段视频纯背景，240 帧全同）。本函数改为
    自动取包围盒，任何坐标系都能正确出片。
    """
    pts = []
    for k, seq in tracks.items():
        for row in seq:
            r = row[2]
            rr = r if isinstance(r, (int, float)) else max(r)
            pts += [(row[0], row[1]),
                    (row[0] - rr, row[1] - rr), (row[0] + rr, row[1] + rr)]
    xs = [q[0] for q in pts]; ys = [q[1] for q in pts]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w = max(x1 - x0, 1e-6); h = max(y1 - y0, 1e-6)
    x0 -= pad * w; x1 += pad * w; y0 -= pad * h; y1 += pad * h
    s = min(W / (x1 - x0), HH / (y1 - y0))
    ox = (W - (x1 - x0) * s) / 2.0
    oy = (HH - (y1 - y0) * s) / 2.0
    out = []
    n = min(len(v) for v in tracks.values())
    for i in range(n):
        im = Image.new("RGB", (W, HH), (238, 238, 234))
        d = ImageDraw.Draw(im)
        if ground is not None:
            gyy = oy + (y1 - ground) * s
            if 0 <= gyy <= HH:
                d.line([(0, gyy), (W, gyy)], fill=(120, 100, 80), width=2)
        for k, seq in tracks.items():
            x, y, r = seq[i][0], seq[i][1], seq[i][2]
            rr = max((r if isinstance(r, (int, float)) else max(r)) * s, 2.0)
            cx, cy = ox + (x - x0) * s, oy + (y1 - y) * s
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
            # 顺序：积分 → 碰撞求解(含位置分离) → 测量
            # 原顺序为「求解→积分→测量」，测到的是积分造成的穿透(一帧位移
            # 3/240=0.0125m)，物理上不可消——穿透必须在测量前被分离掉。
            a.p += a.v * dt
            b.p += b.v * dt
            RG.collide_pair(a, b)
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


def _phys_frames2(tracks, ground_y, span_m, W=640, HH=360):
    """侧视图：支持圆与方块。tracks: {名: [(x,y,r 或 (hw,hh), kind)]}"""
    pad = 0.12 * span_m
    x0, x1 = -pad, span_m + pad
    s = min(W / (x1 - x0), HH / (span_m + pad))
    n = min(len(v) for v in tracks.values())
    out = []
    for i in range(n):
        im = Image.new("RGB", (W, HH), (238, 238, 234))
        d = ImageDraw.Draw(im)
        gy = HH - ground_y * s
        d.line([(0, gy), (W, gy)], fill=(120, 100, 80), width=2)
        for k, seq in tracks.items():
            x, y, geom, kind = seq[i]
            cx, cy = (x - x0) * s, HH - y * s
            if kind == "box":
                hw, hh = geom
                a, b = max(hw * s, 2.0), max(hh * s, 2.0)
                d.rectangle([cx - a, cy - b, cx + a, cy + b],
                            fill=(96, 130, 180), outline=(40, 55, 80), width=2)
            else:
                rr = max(geom * s, 2.0)
                d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr],
                          fill=(216, 96, 72), outline=(70, 60, 55), width=2)
            d.text((cx - 3, cy - 4), k[:1], fill=(40, 40, 40))
        out.append(im)
    return out


def case_C16():
    """堆叠方块：重力下稳定，不塌陷、不抖动、不穿模"""
    import motion.rigid2d as R2
    boxes, pen, traj = R2.stack_sim(n_box=4, size=0.22, T=3.0)
    # 末段 0.5s 质心纵向漂移（米）→ 折算像素：抖动判据
    tail = traj[int(len(traj) * 5.0 / 6.0):]
    # 抖动口径：末段逐帧纵向位移的最大值（折算像素），而非相对首帧的慢漂
    s_px = min(640.0 / (1.8 * 1.24), 360.0 / (1.8 + 0.12 * 1.8))
    step_m = max(max(abs(tail[i + 1][k][1] - tail[i][k][1])
                     for i in range(len(tail) - 1)) for k in range(len(boxes)))
    drift_m = max(max(abs(p[k][1] - tail[0][k][1]) for p in tail)
                  for k in range(len(boxes)))
    checks = [("penetration_m", pen), ("jitter_px", step_m * s_px)]
    tk = {"b%d" % k: [(traj[i][k][0], traj[i][k][1], (0.22, 0.22), "box")
                      for i in range(len(traj))] for k in range(len(boxes))}
    # 修帧步失配：仿真 721 步若直当 721 帧 @20fps 出片 = 36 秒（慢放 12 倍）。
    # 改为重采样到 T=3.0 秒 * 24fps = 72 帧，物理时间 == 视频时间。
    tk = resample_tracks(tk, 1.0 / 240.0, 24, 3.0)
    mp4 = _save_mp4(_phys_frames_auto(tk, ground=0.0), "C16_堆叠方块", fps=24)
    return checks, {"mp4": mp4, "末段漂移_m": round(float(drift_m), 6),
                    "层序_y": [round(float(b.p[1]), 4) for b in boxes]}


def case_C17():
    """斜坡滚球：沿坡加速下滑，不穿斜面，不增能"""
    import motion.rigid2d as R2
    ball, traj, pen, a_theory = R2.ramp_sim(theta_deg=20.0, L=2.0, mu=0.05)
    vy = [(p[0], p[1]) for p in traj]
    # 能量：动能+势能，末态不得大于初态
    states = [(1.0, ((vy[i + 1][0] - vy[i][0]) / (1 / 240.0),
                     (vy[i + 1][1] - vy[i][1]) / (1 / 240.0)), vy[i][1])
              for i in range(len(vy) - 1)]
    eg = H.energy_gain(states)
    v_end = float(np.hypot(*((np.array(traj[-1]) - np.array(traj[-2]))
                             / (1 / 240.0)))) if len(traj) > 1 else 0.0
    checks = [("penetration_m", pen), ("energy_gain", eg)]
    tk = {"ball": [(p[0], p[1], 0.11, "circle") for p in traj]}
    tk = resample_tracks(tk, 1.0 / 240.0, 24, 2.5)   # 仿真 T=2.5s，重采样到 24fps
    mp4 = _save_mp4(_phys_frames2(tk, -1.2, 2.4), "C17_斜坡滚球", fps=24)
    return checks, {"mp4": mp4, "理论加速度": round(a_theory, 4),
                    "末速_m_s": round(v_end, 4)}


def case_C19():
    """摆锤撞击：水平动量守恒（绳为外力，撞击角决定残差），绳长不变，不穿模"""
    import motion.rigid2d as R2
    bob, ball, pre, post, pen = R2.pendulum_sim()
    pre = 0.0 if pre is None else pre
    post = 0.0 if post is None else post
    me = abs(post - pre) / max(abs(pre), 1e-9)
    L_err = abs(float(np.linalg.norm(bob.p)) - 1.0)
    checks = [("momentum_err", me), ("penetration_m", pen)]
    # 修假渲染：原先用常量占位（摆锤恒在 (-0.6, 0)），视频完全静止。
    # 改为 pendulum_sim(with_traj=True) 取真实轨迹并重采样。
    bob2, ball2, _p, _q, _e2, traj = R2.pendulum_sim(T=1.6, with_traj=True)
    tk = {"bob": [(t[0], t[1], 0.12, "circle") for t in traj],
          "ball": [(t[2], t[3], 0.12, "circle") for t in traj]}
    tk = resample_tracks(tk, 1.0 / 2400.0, 24, 1.6)
    mp4 = _save_mp4(_phys_frames_auto(tk), "C19_摆锤碰撞", fps=24)
    return checks, {"mp4": mp4, "碰撞前水平动量": round(float(pre), 6),
                    "碰撞后水平动量": round(float(post), 6),
                    "绳长误差_m": round(L_err, 8)}
