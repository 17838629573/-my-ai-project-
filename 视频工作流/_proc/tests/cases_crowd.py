"""D 组多主体用例（人群碰撞 / 两人击掌）

契约: tests/cases_crowd
  输入: 无（用例自带固定参数，固定种子，无随机）
  输出: (checks, extra)——checks 交 harness.report，extra 为补充事实
  依赖: numpy, PIL, motion.crowd, tests.harness, motion.run
  被依赖: tests/run_all
  约束: 判据阈值一律取自 harness.CRIT，不许就地拍数；
        多主体推进统一走 motion.crowd.orca_step + separate_all；
        渲染走 motion.run.to_mp4；俯视与侧视共用同一世界坐标
  校验: python -m tests.run_all
"""
import os
import numpy as np
from PIL import Image, ImageDraw
import motion.crowd as CR
from motion.run import to_mp4
import tests.harness as H

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, HH = 640, 360
FPS = 24
DT = 1.0 / FPS


def _gray(frames):
    return [np.asarray(im.convert("L"), float) for im in frames]


def _top_view(ags, span=4.6, trails=None):
    """俯视 XZ：世界米 → 像素。ags: [Agent]"""
    im = Image.new("RGB", (W, HH), (238, 238, 234))
    d = ImageDraw.Draw(im)
    s = min(W, HH) / span
    cx, cy = W / 2.0, HH / 2.0

    def px(p):
        return (cx + p[0] * s, cy + p[1] * s)

    # 网格
    for g in np.arange(-2.0, 2.01, 0.5):
        d.line([(cx + g * s, 0), (cx + g * s, HH)], fill=(222, 222, 216), width=1)
        d.line([(0, cy + g * s), (W, cy + g * s)], fill=(222, 222, 216), width=1)
    if trails:
        for tr in trails.values():
            for i in range(1, len(tr)):
                a, b = px(tr[i - 1]), px(tr[i])
                d.line([a, b], fill=(180, 196, 220), width=2)
    cols = [(216, 96, 72), (72, 128, 200), (96, 168, 96), (190, 150, 60)]
    for k, a in enumerate(ags):
        x, y = px(a.p)
        rr = max(a.r * s, 3.0)
        d.ellipse([x - rr, y - rr, x + rr, y + rr],
                  fill=cols[k % len(cols)], outline=(60, 55, 50), width=2)
        vx, vy = px(a.p + a.v * 0.35)
        d.line([(x, y), (vx, vy)], fill=(40, 40, 40), width=3)
        d.text((x - 3, y - 5), a.name or str(k), fill=(30, 30, 30))
    return im


def _stick_side(ags, arms=None, Hh=1.70, span=3.2):
    """侧视：两人连线为横轴，画简化骨架；arms 给 (外展角°,肘屈角°)"""
    im = Image.new("RGB", (W, HH), (240, 236, 228))
    d = ImageDraw.Draw(im)
    s = (HH * 0.72) / Hh
    cx = W / 2.0
    gy = HH * 0.88                      # 地面
    d.line([(0, gy), (W, gy)], fill=(150, 130, 105), width=2)

    def P(wx, hy):
        return (cx + wx * s, gy - hy * s)

    for k, (wx, side) in enumerate(ags):
        col = (72, 128, 200) if k == 0 else (216, 96, 72)
        hip_y, sh_y, head_y = 0.53 * Hh, 0.818 * Hh, 0.948 * Hh
        foot = P(wx, 0.0)
        hip = P(wx, hip_y)
        sh = P(wx, sh_y)
        head = P(wx, head_y)
        d.line([foot, hip], fill=col, width=4)                       # 腿（合并）
        d.line([hip, sh], fill=col, width=5)                         # 躯干
        d.ellipse([head[0] - 0.065 * Hh * s, head[1] - 0.075 * Hh * s,
                   head[0] + 0.065 * Hh * s, head[1] + 0.055 * Hh * s],
                  fill=col, outline=(50, 45, 40), width=2)           # 头
        # 非击掌臂：垂在体侧
        d.line([sh, P(wx, hip_y - 0.30 * Hh)], fill=col, width=3)
        # 击掌臂（若给了角度）
        if arms and k < len(arms):
            ab, eb = arms[k]
            a = np.radians(ab)
            ux, uy = side * np.sin(a), -np.cos(a)                    # 上臂单位向量（y 向上）
            L1 = 0.186 * Hh
            e = (sh[0] + ux * L1 * s, sh[1] - uy * L1 * s)
            b = np.radians(eb)
            # 前臂：由上臂朝上方转 eb
            ca, sa = np.cos(b), np.sin(b)
            vx, vy = ux * ca - uy * sa, ux * sa + uy * ca
            L2 = 0.146 * Hh
            wr = (e[0] + vx * L2 * s, e[1] - vy * L2 * s)
            d.line([sh, e], fill=col, width=4)
            d.line([e, wr], fill=col, width=4)
            d.ellipse([wr[0] - 4, wr[1] - 4, wr[0] + 4, wr[1] + 4],
                      fill=(245, 214, 170), outline=(90, 70, 55), width=1)
    return im


def _save_mp4(frames, prefix, fps=FPS):
    p = os.path.join(OUT, "%s.mp4" % prefix)
    to_mp4(frames, p, fps)
    return p


# ------------------------------------------------------------------ D24
def case_D24():
    """D24 三角色互相碰撞：彼此阻挡/绕开，不重叠，不抖动"""
    goals = [np.array([1.5, 1.5]), np.array([-1.5, 1.5]), np.array([0.0, -1.8])]
    ags = [CR.Agent(-1.5, -1.5, name="A"),
           CR.Agent(1.5, -1.5, name="B"),
           CR.Agent(0.0, 1.8, name="C")]
    trails = {a.name: [] for a in ags}
    # 前段穿越碰撞，后段全部到位静止——抖动只在静止段量（判据口径：
    # jitter_px 抓的是"该静止却在颤"，人群移动产生的像素差是运动不是抖动）
    T = 8.0
    N_MOVE = int(round(6.0 / DT))
    n = int(round(T / DT))
    frames, pairs_all, disp = [], [], []
    prev = [a.p.copy() for a in ags]
    for _ in range(n):
        for a, g in zip(ags, goals):
            dv = g - a.p
            nrm = float(np.linalg.norm(dv))
            a.vpref = (dv / nrm * 1.30) if nrm > 0.05 else np.zeros(2)
        CR.orca_step(ags, DT, vmax=1.4)
        CR.separate_all(ags, iters=4)
        for a in ags:
            trails[a.name].append(a.p.copy())
        for i in range(len(ags)):
            for j in range(i + 1, len(ags)):
                dist = float(np.linalg.norm(ags[j].p - ags[i].p))
                pairs_all.append((dist, ags[i].r, ags[j].r))
        step = max(float(np.linalg.norm(a.p - b)) for a, b in zip(ags, prev))
        disp.append(step)
        prev = [a.p.copy() for a in ags]
        frames.append(_top_view(ags, trails=trails))

    pen = H.penetration_m(pairs_all)
    still = frames[N_MOVE:]
    jit = H.jitter_px(_gray(still)) if len(still) > 4 else 0.0
    # 静止段确实静止（否则 jitter 判据不成立）
    drift = max(float(np.linalg.norm(ags[k].p - prev[k])) for k in range(len(ags)))
    path = _save_mp4(frames, "D24_人群碰撞")
    checks = [("penetration_m", pen), ("jitter_px", jit)]
    extra = {"帧数": len(frames), "最大重叠(m)": round(pen, 5),
             "静止段抖动(px)": round(jit, 5),
             "静止段残余位移(m)": round(drift, 6),
             "末位置(米)": [tuple(np.round(a.p, 3)) for a in ags],
             "视频": os.path.basename(path)}
    return checks, extra


# ------------------------------------------------------------------ D21
def case_D21():
    """D21 两人击掌：靠近 → 抬臂拍合 → 分开；不穿模、不跳变"""
    Hh = 1.70
    gap_final = 1.10
    x0 = 1.60                       # 起始半间距
    t_contact = 1.60
    T = 3.2
    n = int(round(T / DT))

    def half_gap(t):
        """走到位 → 停住击掌 → 退开"""
        if t <= 1.00:
            return x0 + (gap_final / 2 - x0) * (t / 1.00)
        if t <= 2.40:
            return gap_final / 2
        return gap_final / 2 + 0.55 * (t - 2.40)

    frames, pairs_all, disp = [], [], []
    prev = None
    for i in range(n):
        t = i * DT
        g = half_gap(t)
        ags = [(-g, -1.0), (g, 1.0)]          # (世界x, 朝向 side)
        arms = []
        for k, (_, side) in enumerate(ags):
            ab, eb, _wh = CR.high5_arm(t, t_contact, duration=1.2, H=Hh, side=side)
            arms.append((ab, eb))
        pos = [np.array([-g, 0.0]), np.array([g, 0.0])]
        dist = float(np.linalg.norm(pos[1] - pos[0]))
        pairs_all.append((dist, 0.25, 0.25))
        # 掌心不穿模：两人掌心距 ≥ 0
        _, _, palm_gap = CR.high5_pose(t, t_contact, gap=dist, H=Hh)
        pairs_all.append((palm_gap + 1e-9, 0.0, 0.0))   # 只取负值时才计穿透
        if prev is not None:
            disp.append(abs(g - prev))
        prev = g
        frames.append(_stick_side(ags, arms=arms, Hh=Hh))

    pen = H.penetration_m(pairs_all)
    fjr = H.frame_jump_ratio(disp) if len(disp) > 3 else 0.0
    path = _save_mp4(frames, "D21_击掌")
    checks = [("penetration_m", pen), ("frame_jump_ratio", fjr)]
    extra = {"帧数": len(frames), "最大穿透(m)": round(pen, 6),
             "帧间跳变比": round(fjr, 4),
             "击掌间距(m)": gap_final, "视频": os.path.basename(path)}
    return checks, extra
