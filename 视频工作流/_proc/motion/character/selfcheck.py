# 契约: proc/motion/character/selfcheck
#   一句话: 自检脚本：python -m character.selfcheck
#   完整契约见 motion/character/__init__.py

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
from .body.sdf import *
from .body.proportions import *
from .body.joints import *
from .body.leg import *
from .body.gait import *
from .body.render import *
from .body.cloth import *
from PIL import Image, ImageDraw



# ================================================================
# 自检
# ================================================================

if __name__ == "__main__":
    from scene import kit

    ok = True

    def chk(name, cond, extra=""):
        global ok
        ok = ok and bool(cond)
        print("  %-28s %s %s" % (name, "OK" if cond else "FAIL", extra))

    print("=" * 62)
    print("  character 自检")
    print("=" * 62)

    # 1 SDF 原语
    d = sd_circle(np.array([0.0, 1.0, 5.0]), np.array([0.0, 0.0, 0.0]),
                  0.0, 0.0, 1.0)
    chk("圆 SDF 内外符号", d[0] < 0 and d[2] > 0, "内%.1f 外%.1f" % (d[0], d[2]))

    a = np.array([1.0, 1.0]); b = np.array([1.0, 1.0])
    k = smin(a, b, 0.5)
    # smin(1,1,k) = 1 - k/4，故 k=0.5 → 0.875（交界处比 min 低 k/4，即圆滑内凹）
    chk("smin 交界平滑", abs(float(k[0]) - 0.875) < 1e-6, "%.4f" % float(k[0]))

    # 2 步态连续性
    P = gait_params("natural")
    worst = 0.0
    for i in range(60):
        p0, p1 = i / 60.0, (i + 1) / 60.0
        A, B = gait(p0), gait(p1)
        for kk in JOINTS:
            worst = max(worst, float(np.linalg.norm(A[kk] - B[kk])))
    chk("步态逐帧连续", worst < 0.05, "最大关节位移 %.4f" % worst)

    # 3 周期闭合
    A, B = gait(0.0), gait(0.9999)
    close = max(float(np.linalg.norm(A[kk] - B[kk])) for kk in JOINTS)
    chk("周期闭合", close < 0.01, "首尾差 %.5f" % close)

    # 4 膝盖真的弯曲（不总是直的）
    kn = [abs(_knee_curve(i / 24.0, math.radians(50.34))) for i in range(24)]
    chk("膝角有屈伸变化", max(kn) > 0.5 and min(kn) < 0.05,
        "max %.2f min %.2f" % (max(kn), min(kn)))

    # 5 三种预设不同
    g1 = gait(0.25, "natural"); g2 = gait(0.25, "march")
    diff = max(float(np.linalg.norm(g1[kk] - g2[kk])) for kk in JOINTS)
    chk("预设产生不同姿态", diff > 0.02, "差异 %.4f" % diff)

    # 6 形体场（3D 关节 → 正交相机 → 屏幕 SDF）
    J = gait(0.25)
    cam_o = camera.OrthoCam(s=100.0, cx=100.0, y0=700.0)
    Jp = project_body(J, cam_o, Xc=0.0, Zc=10.0, yaw=90.0)
    caps, ell, sm = body_geometry(Jp)
    d, _o, dh = field_px(caps, ell, sm)
    neg = float((d < 0).mean())
    chk("形体场有主体", 0.02 < neg < 0.60, "占比 %.3f 尺寸%s" % (neg, d.shape))
    chk("头有独立场(肤色蒙版)", np.any(dh < 0.0),
        "头像素 %d" % int((dh < 0).sum()))

    # 7 着色：中心亮于边缘（球感）
    col = shade_sdf(d, (128, 74, 52))
    ins = d < 0
    lum = col.mean(axis=2)
    cen = lum[ins].max(); edge = lum[ins & (d > -0.02)].mean()
    chk("中心亮于边缘(立体感)", cen > edge + 8,
        "中心%.0f 边缘%.0f" % (cen, edge))

    # 8 Verlet 链收敛
    vc = VerletChain([[0, 0], [0, 20], [0, 40], [0, 60]])
    for _ in range(120):
        vc.step(dt=1 / 60.0, anchor=(0, 0))
    seg = np.linalg.norm(vc.p[1:] - vc.p[:-1], axis=1)
    chk("Verlet 链不发散", np.all(np.isfinite(vc.p)) and seg.max() < 25.0,
        "最大段长 %.2f" % seg.max())

    # 9 脚底不穿地：任意相位下最低点 ≥ 0（SOLE_LIFT 抬起脚胶囊底）
    lo = 1e9
    for i in range(48):
        jj = gait(i / 48.0)
        for kk in JOINTS:
            lo = min(lo, float(jj[kk][1]) + SOLE_LIFT)
    chk("脚底不穿地", lo > -0.004, "最低 v=%.4f" % lo)

    # 9b 脚掌绝不翻转：全周期 |pitch| < 90°，脚尖永远在脚跟前方
    #    旧实现此处在 phs=0.75~0.95 外推到 -96°~-265°，脚翻过去再弹回来。
    _pmax, _flip, _behind = 0.0, 0, 0
    for i in range(64):
        _pit = foot_pitch(i / 64.0)
        _pmax = max(_pmax, abs(math.degrees(_pit)))
        if abs(math.degrees(_pit)) > 90.0:
            _flip += 1
        if math.cos(_pit) <= 0.0:      # 脚尖转到脚跟后方
            _behind += 1
    chk("脚掌不翻转", _flip == 0, "最大|pitch|=%.1f° 翻转帧%d/64" % (_pmax, _flip))
    chk("脚尖永朝前", _behind == 0, "脚尖跑到脚跟后 %d/64" % _behind)
    _pc = abs(foot_pitch(0.0) - foot_pitch(1.0))
    _tb = abs(_FP_DEG[0] - _FP_DEG[-1])
    chk("脚掌角周期闭合", _pc < 1e-9 and _tb < 1e-9,
        "f(0)≡f(1) 差%.1e；表首尾 %.1f°/%.1f°" % (_pc, _FP_DEG[0], _FP_DEG[-1]))

    # 10 侧向宽度：双腿/双臂真的分开了（3D 化生效）
    jm = gait(0.25)
    dw = abs(jm["ank_l"][2] - jm["ank_r"][2])
    chk("双腿有侧向宽度", dw > 0.05, "ank 间距 %.3f" % dw)

    # 11 透视相机：走远 → 身高单调变小、脚底单调升高、身高/路宽比恒定
    cam_p = camera.Cam(540, 960, 270, 499, 518.6, 1.60, 0.488)
    hs, gy, rt = [], [], []
    for Z in (2.0, 4.0, 8.0, 16.0, 32.0):
        Jz = project_body(gait(0.25), cam_p, Xc=0.0, Zc=Z, yaw=0.0)
        top = Jz["head"][1] - PROP["head_r"] * 1.12 * 1.70 * Jz["head"][2]
        bot = max(Jz["ank_l"][1], Jz["ank_r"][1])
        hs.append(bot - top)
        gy.append(cam_p.ground_y(Z))
        rt.append((Jz["hip_l"][1] - top) / cam_p.px_per_m(Z))
    mono_h = all(hs[i] > hs[i + 1] for i in range(len(hs) - 1))
    chk("走远身高单调变小", mono_h,
        " ".join("%.0f" % v for v in hs))
    chk("脚底随走远升高", all(gy[i] > gy[i + 1] for i in range(len(gy) - 1)),
        " ".join("%.0f" % v for v in gy))
    chk("身高随深度等比缩放", (max(rt) - min(rt)) / max(rt) < 0.05,
        "身高/米 %.3f~%.3f（各关节深度略异，非严格等比）" % (min(rt), max(rt)))

    # 12 朝向：yaw=0（背视走远）前向落在 Z 轴 → 屏幕上前后脚 y 拉开、x 几乎重叠
    jb = gait(0.0)      # 脚跟着地相位：前后脚张得最开
    Ja = project_body(jb, cam_p, Xc=0.0, Zc=2.5, yaw=0.0)
    Js = project_body(jb, cam_p, Xc=0.0, Zc=2.5, yaw=90.0)
    # 背视：前后脚差在"深度"上 → 屏幕上主要是 y 差（远的更高）
    dxb = abs(Ja["ank_l"][0] - Ja["ank_r"][0]); dyb = abs(Ja["ank_l"][1] - Ja["ank_r"][1])
    # 侧视：前后脚差在"横向"上 → 屏幕上主要是 x 差
    dxs = abs(Js["ank_l"][0] - Js["ank_r"][0]); dys = abs(Js["ank_l"][1] - Js["ank_r"][1])
    chk("背视:前后脚显为y差", dyb > dxb, "dx%.1f dy%.1f" % (dxb, dyb))
    chk("侧视:前后脚显为x差", dxs > dys, "dx%.1f dy%.1f" % (dxs, dys))

    # 8b 步态物理：IK 骨长守恒 / 不打滑 / 膝朝前 / 周期闭合 / 重心起伏
    L1_, L2_ = PROP["thigh"], PROP["shank"]
    e1_, e2_, cr_, sl_, hs_ = [], [], [], [], []
    for i in range(96):
        ph_ = i / 96.0
        J_ = gait(ph_); hs_.append(J_["hip_l"][1])
        for s_ in ("l", "r"):
            h_, k_, a_ = J_["hip_" + s_], J_["knee_" + s_], J_["ank_" + s_]
            e1_.append(abs(np.linalg.norm(k_ - h_) - L1_))
            e2_.append(abs(np.linalg.norm(a_ - k_) - L2_))
            dv_, kv_ = a_ - h_, k_ - h_
            cr_.append(dv_[0] * kv_[1] - dv_[1] * kv_[0])
            if (ph_ + (0.0 if s_ == "l" else 0.5)) % 1.0 < 0.62:
                sl_.append(abs(gait(ph_ + 1 / 96.0)["ank_" + s_][0] - a_[0]))
    e1_, e2_, cr_, sl_ = map(np.array, (e1_, e2_, cr_, sl_))
    chk("IK 骨长守恒", e1_.max() < 1e-6 and e2_.max() < 1e-6,
        "大腿%.1e 小腿%.1e" % (e1_.max(), e2_.max()))
    chk("膝盖一律朝前", bool((cr_ > 0).all()), "异常%d/%d" % ((cr_ <= 0).sum(), len(cr_)))
    cvsl = sl_.std() / max(sl_.mean(), 1e-9)
    chk("支撑脚不打滑", cvsl < 0.05, "CV %.4f" % cvsl)
    g0_, g1_ = gait(0.0), gait(1.0)
    chk("周期闭合(φ=0≡1)", np.allclose(g0_["hip_l"], g1_["hip_l"], atol=1e-6)
        and np.allclose(g0_["ank_l"], g1_["ank_l"], atol=1e-6), "hip/ank 均闭合")
    com = max(hs_) - min(hs_)
    chk("重心起伏合理", 0.02 < com < 0.06, "%.4f (真实≈0.03)" % com)

    # 9 画出人物（多相位居一格）
    cv = kit.Canvas(540, 960, (28, 34, 48))
    for i, ph in enumerate([0.0, 0.25, 0.5, 0.75]):
        draw_character(cv, {"w": 540, "h": 960}, phase0=ph,
                       x=90 + i * 120, y=880, height_px=300)
    cv.img.save("人物_四相位.png")
    chk("人物绘制成功", True, "→ 人物_四相位.png")

    # 10 走路序列（1 个周期 12 帧小图）
    tiles = []
    for i in range(12):
        c2 = kit.Canvas(180, 320, (28, 34, 48))
        draw_character(c2, {"w": 180, "h": 320}, phase0=i / 12.0,
                       x=90, y=300, height_px=250)
        tiles.append(c2.img)
    sheet = Image.new("RGB", (180 * 6, 320 * 2), (18, 22, 32))
    for i, im in enumerate(tiles):
        sheet.paste(im, ((i % 6) * 180, (i // 6) * 320))
    sheet.save("人物_走路12帧.png")
    chk("走路序列出图", True, "→ 人物_走路12帧.png")

    print("-" * 62)
    print("  SELF_CHECK:", "PASS" if ok else "FAIL")
