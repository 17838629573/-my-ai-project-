"""渲染与剪影校验（测试第二步：出片并量剪影）

契约: tests/gen
  输入: 用例名（cases.py 的 id）+ 关节序列生成函数
  输出: mp4 / 索引 png / 剪影判据实测值
  依赖: numpy PIL _proc.motion.run _proc.shape.line _proc.tests.harness
  被依赖: tests/run_all
  约束: 一律走 run.draw_actor 单一渲染管线，不许另写画人的代码；
        剪影判据阈值必须有 CRIT 出处；
        渲染掩膜由"与本帧背景差分"取得，GT 掩膜由屏幕胶囊重建

为什么要有这个模块
  A3/A7 曾渲染出"只有头和一块躯干、没有腿脚"的残缺人物，
  运动学判据全过（因为关节数据是对的），只有剪影判据能抓到。
"""
import math
import os
import sys

import numpy as np
from PIL import Image

# 自举：按 __file__ 上溯定位项目根，禁止硬编码绝对路径
# （硬编码会导致 clone 到别处就 ImportError）
# gen.py 位于 <root>/_proc/tests/ → 上溯三级
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROC = os.path.join(ROOT, "_proc")
for p in (ROOT, os.path.dirname(PROC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from _proc.motion import camera as C
from _proc.motion.character import render as CR      # noqa: E402
from _proc.motion import run as R         # noqa: E402
from _proc.shape import line as L         # noqa: E402
from _proc.tests import harness as HS     # noqa: E402

W, HH = 540, 960
FPS = 24.0
BODY_H = 1.70
OUT = PROC


def _cam():
    """固定透视相机：相机高 1.60m，Z=5 处人物约 300px。"""
    return C.Cam(W, HH, cx=W / 2.0, v_h=0.30 * HH, f=882.0, hc=1.60, W=1.0)


def _bg():
    """纯背景：上半天空、下半地面，用于差分取掩膜。"""
    img = Image.new("RGB", (W, HH), (232, 226, 214))
    px = np.asarray(img).astype(np.int16)
    px[int(0.30 * HH):, :] = (198, 186, 160)
    return Image.fromarray(px.astype(np.uint8))


def _render_mask(bg_arr, frame_arr):
    """与背景差分 → 人物掩膜。"""
    d = np.abs(frame_arr.astype(np.int16) - bg_arr.astype(np.int16)).sum(2)
    return d > 18


def _gt_mask(Jp, caps, body_h):
    """由屏幕胶囊重建几何真值掩膜（渲染管线的输入，不是输出）。"""
    gy, gx = np.mgrid[0:HH, 0:W]
    PX = gx.astype(np.float32)
    PY = gy.astype(np.float32)
    d = np.full((HH, W), 1e6, np.float32)
    for ax, ay, bx, by, r in caps:
        d = np.minimum(d, L.sd_capsule(PX, PY, ax, ay, bx, by, r))
    hx, hy, hs = Jp["head"]
    from _proc.motion.character import proportions as _PP
    rx = max(_PP.PROP["head_r"] * 0.86 * body_h * hs, 1.0)
    ry = max(_PP.PROP["head_r"] * 1.12 * body_h * hs, 1.0)
    d = np.minimum(d, L.sd_ellipse(PX, PY, hx, hy, rx, ry))
    return d < 0.0


def render_case(name, pose_fn, n, out_prefix, yaw=90.0, Zc=5.0,
                lane=0.0, t_end=None, palette=None, hand_lod=1,
                extra=None):
    """pose_fn(t) -> J（归一化身高单位）。逐帧渲染并量剪影。"""
    cam = _cam()
    bg = _bg()
    bg_arr = np.asarray(bg).astype(np.int16)
    frames = []
    worst = {"silhouette_gap_px": 0.0, "silhouette_span_ratio": 9.9,
             "mask_iou": 1.0}
    for i in range(n):
        t = (t_end or (n / FPS)) * i / max(n - 1, 1)
        J = pose_fn(t)
        Xc = lane
        cv = R.CV(W, HH)
        cv.set_arr(bg_arr.astype(np.float32))
        Jp = R.draw_actor(cv, cam, J, Xc=Xc, Zc=Zc, yaw=yaw,
                          body_h=BODY_H, template="humanoid",
                          hand_lod=hand_lod, palette=palette)
        # 剪影判据只针对人物：extra 画的球/道具是附加元素，
        # 若先画再取掩膜，飞出人体的球会被算进人物剪影，
        # 在头顶与球之间留出空白行 → silhouette_gap_px 虚高(B10 曾报 23px)。
        # GT 掩膜同样只含人物胶囊，故也必须在 extra 之前取。
        m = _render_mask(bg_arr, np.asarray(cv.img).astype(np.int16))
        if extra is not None:
            extra(t, cv, cam)
        joints, caps, _ = L.build_body("humanoid", hand_lod, BODY_H)
        from _proc.shape import hand as _H
        J2 = _H.attach(dict(J), hand_lod)
        Jp2 = CR.project_body(J2, cam, Xc=Xc, Zc=Zc, yaw=yaw, body_h=BODY_H)
        by_reg, _ell = R._screen_caps(caps, Jp2, BODY_H)
        allcaps = [c for v in by_reg.values() for c in v]
        if allcaps and m.any():
            gt = _gt_mask(Jp2, allcaps, BODY_H)
            top = min(p[1] for p in Jp2.values())
            bot = max(p[1] for p in Jp2.values())
            worst["silhouette_gap_px"] = max(worst["silhouette_gap_px"],
                                             HS.silhouette_gap_px(m))
            worst["silhouette_span_ratio"] = min(
                worst["silhouette_span_ratio"],
                HS.silhouette_span_ratio(m, top, bot))
            worst["mask_iou"] = min(worst["mask_iou"], HS.mask_iou(m, gt))
        frames.append(cv.img.copy())
    mp4 = os.path.join(OUT, "%s.mp4" % out_prefix)
    R.to_mp4(frames, mp4, int(FPS))
    png = os.path.join(OUT, "%s_索引.png" % out_prefix)
    _index(frames, png, 6)
    checks = [(k, v) for k, v in worst.items()]
    txt, ok = HS.report(checks)
    return {"name": name, "mp4": mp4, "png": png, "ok": ok,
            "report": txt, "vals": worst}


def _index(frames, path, k=6):
    if not frames:
        return
    k = min(k, len(frames))
    idx = [int(round(i * (len(frames) - 1) / (k - 1))) for i in range(k)]
    tiles = [frames[i].resize((W // 2, HH // 2)) for i in idx]
    cw, ch = tiles[0].size
    sheet = Image.new("RGB", (cw * k, ch), (250, 250, 250))
    for i, t in enumerate(tiles):
        sheet.paste(t, (i * cw, 0))
    sheet.save(path)


# ---------------------------------------------------------------- 用例姿态
def _mod(name):
    import importlib
    return importlib.import_module("." + name,
                                      "_proc.motion.character")


def _pose_walk(t):
    d = 0.67 * t
    ph = (d / 0.561) % 1.0
    return _mod("gait").gait(ph, "natural")


def _pose_jump(t):
    return _mod("jump").jump(t)


def _pose_turn(t):
    TN = _mod("turn")
    dur = TN.turn_duration(180.0)
    u = min(t / dur, 1.0)
    J = _mod("gait").gait(0.0, "natural")
    TN.turn_legs(J, u)
    TN.turn_torso(J, u, 180.0)
    return J


def _pose_wave(t):
    GS = _mod("gesture")
    J = {k: np.asarray(v, dtype=float) for k, v in
         _mod("gait").gait(0.0, "natural").items()}
    u = (t % 2.0) / 2.0
    res = GS.wave(u, None)
    for k, v in res["J"].items():
        if k in J:
            J[k] = np.asarray(J[k]) + np.asarray(v)
    return J


def _ball_extra(t, cv, cam):
    """额外绘制球：世界坐标(米) → 归一化身高 → 投影 → 画圆"""
    from _proc.motion.character import ball as _B
    from _proc.motion.character import render as _CR
    p = _mod("kick").ball_center(min(t / _mod("kick").T_TOTAL, 1.0))
    P0 = _CR.project_body({"b": (p[0] / BODY_H, p[1] / BODY_H, 0.0)},
                          cam, Xc=0.0, Zc=5.0, yaw=90.0, body_h=BODY_H)["b"]
    P1 = _CR.project_body({"b": ((p[0] + _B.R_BALL) / BODY_H, p[1] / BODY_H, 0.0)},
                          cam, Xc=0.0, Zc=5.0, yaw=90.0, body_h=BODY_H)["b"]
    r = max(abs(P1[0] - P0[0]), 2.0)
    gy, gx = np.mgrid[0:HH, 0:W]
    d = np.sqrt((gx - P0[0]) ** 2 + (gy - P0[1]) ** 2) - r
    m = d < 0
    a = np.asarray(cv.img).astype(np.float32)
    shade = np.clip(0.72 + 0.28 * (-d / max(r, 1e-6)), 0, 1)[..., None]
    a[m] = a[m] * (1 - 1) + np.array([226, 224, 218], np.float32) * shade[m]
    a[np.abs(d) < 1.2] = np.array([70, 66, 60], np.float32)
    cv.set_arr(a)


def _pose_kick(t):
    return _mod("kick").kick(min(t / _mod("kick").T_TOTAL, 1.0))


def _pose_crouch(t):
    q = min(t / 1.5, 1.0)
    return _mod("crouch").crouch(q, with_arms=True)


CASES = [
    ("A1", _pose_walk, 48, "A1_走路", 2.0),
    ("A3", _pose_jump, 26, "A3_跳跃", None),
    ("A4", _pose_turn, 15, "A4_转身180", 0.6),
    ("A5", _pose_wave, 36, "A5_挥手", 1.5),
    ("A6", _pose_kick, 36, "A6_踢球", None),
    ("A7", _pose_crouch, 36, "A7_下蹲捡物", 1.5),
]


def main():
    rows = []
    for cid, fn, n, pre, tend in CASES:
        ex = _ball_extra if cid == "A6" else None
        r = render_case(cid, fn, n, pre, t_end=tend, extra=ex)
        rows.append(r)
        print("=" * 60)
        print(cid, "->", os.path.basename(r["mp4"]))
        print(r["report"])
    print("\n渲染剪影总判定:", "PASS" if all(r["ok"] for r in rows) else "FAIL")
    return rows


if __name__ == "__main__":
    main()
