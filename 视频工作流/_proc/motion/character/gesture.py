# -*- coding: utf-8 -*-
"""手势与头部动作模块（动作层·手势）

契约: proc/motion/character/gesture
  一句话: 注视转移 / 手指敲击 / 翻页 —— 头部与手部的短促动作
  完整契约见 motion/character/__init__.py

  输入: 相位进度 u∈[0,1]、params{方向/重复次数/幅度}、基准关节 J
  输出: {'J': {关节: (u,v,w)}, 'phase': str, 'detail': dict}
  依赖: numpy
  被依赖: motion.beat, motion.cafe
  约束: 眼睛先于头到达（Pejsa: 眼到 OMR 后头才追上，VOR 锁定）；
        敲击用 anticipation→strike→settle 三段（Lango: 5/2/3 帧）；
        翻页纸张变形用 cos(πu) 镜像 + sin(πu) 起弧，中线不动；
        未知动作名报错不静默
  校验: python -m motion.character.gesture
"""
import math

import numpy as np

from ..beat import CAP, capability

# --- 注视：Pejsa 2016《Effective Directed Gaze》-------------------------
# 眼动峰值速度 V_MAX = (2/75·A_MIN + 1/6)·V0，V0 默认 150 deg/s
# 眼先动、到 OMR 后被阻挡，头追上，VOR 把眼锁定在目标上
GAZE_V0 = 150.0          # deg/s，用户可改的默认峰值速度基准
GAZE_EYE_FRAC = 0.35     # 眼在前 35% 时长内到达（头用剩余时长）
GAZE_HEAD_ALIGN = 0.75   # α_H：头对齐目标的比例，0=几乎不转头 1=完全对齐

# --- 敲击：Keith Lango snappy animation --------------------------------
# 上臂 anticipation 5 帧 / 到极限 2 帧 / settle 3 帧；
# 手肘比上臂晚 1 帧，手指晚 2 帧（依次展开，避免整条手臂同时动）
TAP_SPANS = (0.5, 0.2, 0.3)      # anticipation / strike / settle
TAP_FRAME_LAG = {"wri": 2, "elb": 1, "sh": 0}
TAP_FRAMES = 10.0                # 一个敲击循环的参考总帧数

# --- 翻页 ---------------------------------------------------------------
# 书页绕书脊转：x 分量乘 cos(π·u) 从 1 镜像到 -1；y 用 sin(π·u) 起半圆弧；
# 靠书脊一侧不动（权重 = |x|），阴影在 progress≈0（中途）最强
CURL_SCALE = 0.30

__all__ = ["GAZE_V0", "GAZE_EYE_FRAC", "GAZE_HEAD_ALIGN", "TAP_SPANS", "CURL_SCALE",
           "gaze_shift", "finger_tap", "page_flip", "eye_velocity", "tap_envelope",
           "page_curl", "page_shadow", "self_check"]


def _sstep(x):
    x = 0.0 if x < 0 else (1.0 if x > 1 else x)
    return x * x * (3 - 2 * x)


def eye_velocity(a_min_deg, v0=GAZE_V0):
    """注视峰值速度 V_MAX = (2/75·A_MIN + 1/6)·V0 —— Pejsa 2016 式(1)。

    A_MIN 取两眼到目标角距的最小值与 OMR 的较小者（度）。
    """
    return (2.0 / 75.0 * float(a_min_deg) + 1.0 / 6.0) * float(v0)


def _lag(u, frames, span=1.0):
    """把部件延迟若干帧：在 [0,1] 上按帧滞后重映射进度。"""
    d = frames / TAP_FRAMES * span
    return _sstep((u - d) / max(1e-9, 1.0 - d)) if u > d else 0.0


# ---------------------------------------------------------------- 注视
@capability("gaze_shift", "Pejsa 2016 Effective Directed Gaze (eye-then-head, VOR)", "face")
def gaze_shift(u, params=None):
    """转移注视：眼先动 → 头追上 → VOR 锁定。

    params: yaw(左右, +右) pitch(上下, +上) align(头对齐度) amp(幅度, 归一化身高)
    """
    p = dict(params or {})
    yaw = float(p.get("yaw", 1.0))
    pitch = float(p.get("pitch", 0.0))
    align = float(p.get("align", GAZE_HEAD_ALIGN))
    amp = float(p.get("amp", 0.020))
    u = float(np.clip(u, 0.0, 1.0))

    # 眼在前段到达，头用整段时长 —— 眼到 OMR 后头继续转，眼被 VOR 反向锁住
    eye = _sstep(u / GAZE_EYE_FRAC) if u < GAZE_EYE_FRAC else 1.0
    head = _sstep(u)
    # VOR：头追上之后眼在眼眶内回退，维持视线落在目标上
    vor = 0.0 if u < GAZE_EYE_FRAC else (u - GAZE_EYE_FRAC) / (1 - GAZE_EYE_FRAC)

    off_u = amp * yaw * head * align
    off_v = -amp * pitch * head * align          # 画面 y 向下，抬头取负
    j = {
        "head": (off_u, off_v, amp * 0.4 * eye),
        "neck": (off_u * 0.55, off_v * 0.55, 0.0),
        "chest": (off_u * 0.22, off_v * 0.22, 0.0),
    }
    return {"J": j, "phase": "gaze",
            "detail": {"eye": float(eye), "head": float(head), "vor": float(vor),
                       "v_max_deg_s": eye_velocity(20.0)}}


# ---------------------------------------------------------------- 敲击
def tap_envelope(u, spans=TAP_SPANS):
    """Lango 三段包络：anticipation 抬 → strike 落 → settle 回。返回 (值, 段名)。"""
    a, s, r = spans
    if u < a:                                   # 抬起蓄势 0 → +1
        return _sstep(u / a), "anticipation"
    if u < a + s:                               # 落下击打 +1 → -1
        return 1.0 - 2.0 * _sstep((u - a) / s), "strike"
    return -1.0 + _sstep((u - a - s) / r), "settle"   # 回位 -1 → 0


@capability("finger_tap", "Keith Lango snappy animation (5/2/3 frames, per-part lag)", "arm")
def finger_tap(u, params=None):
    """手指敲击：手腕上下，部件依次滞后（手指最晚）。

    params: reps(段内敲几下) amp(幅度) side(right/left)
    """
    p = dict(params or {})
    reps = max(1, int(p.get("reps", 2)))
    amp = float(p.get("amp", 0.014))
    side = str(p.get("side", "right"))
    if side not in ("right", "left"):
        raise ValueError("未知手别 %r（应为 right/left）" % side)
    suf = "_r" if side == "right" else "_l"

    u = float(np.clip(u, 0.0, 1.0))
    local = (u * reps) % 1.0                      # 段内重复
    val, ph = tap_envelope(local)
    # 依次滞后：肩 0 帧、肘 1 帧、腕 2 帧
    lag_e = _lag(local, TAP_FRAME_LAG["elb"])
    lag_w = _lag(local, TAP_FRAME_LAG["wri"])
    j = {
        "wri" + suf: (0.0, -amp * val * lag_w, 0.0),
        "elb" + suf: (0.0, -amp * 0.4 * val * lag_e, 0.0),
        "sh" + suf: (0.0, -amp * 0.15 * val, 0.0),
    }
    return {"J": j, "phase": ph, "detail": {"rep": int(u * reps), "side": side}}


# ---------------------------------------------------------------- 挥手
WAVE_RAISE_U = 0.30     # 前 30% 抬臂，之后左右摆（Utween 低层序列 t=0.2~0.6 抬起）
WAVE_RAISE_DEG = 115.0  # 肘抬起终角（Utween: 30°→60°→115°）
WAVE_SWING_DEG = 60.0   # 左右摆幅（Utween: x 轴 ±40°~±60°）
WAVE_WRIST_FRAC = 0.25  # 腕跟随比例（Utween: 腕 ±15° ≈ 肘 ±60° 的 1/4）
WAVE_WRIST_LAG = 1      # 腕滞后帧数（腕比肘晚，才有甩动感）


def wave_envelope(u):
    """挥手包络：返回 (抬起进度, 摆动值)。抬起 smoothstep，摆动正弦。"""
    u = float(np.clip(u, 0.0, 1.0))
    raise_u = _sstep(min(1.0, u / WAVE_RAISE_U))
    if u <= WAVE_RAISE_U:
        return raise_u, 0.0
    s = (u - WAVE_RAISE_U) / (1.0 - WAVE_RAISE_U)
    return 1.0, math.sin(2.0 * math.pi * s)


@capability("wave", "Utween ECA wave low-level: elbow 30→60→115 raise, x ±60 swing, wrist ±15 lag", "arm")
def wave(u, params=None):
    """挥手：抬右臂 → 手掌左右摆动，肩肘腕联动。

    出处: Embodied Conversational Agent Toolkit (Utween) 低层序列
          t=0.2~0.6 抬臂(肘 y 30→60→115, z 90 掌心朝前)
          t=0.8~2.0 左右摆(肘 x ±40/±60, 腕 x ±15)
    这里转成关节位移：肩抬得最少、肘最多、腕摆动最大且滞后一帧。
    params: side(right/left) amp(归一化幅度) reps(摆动次数)
    """
    p = dict(params or {})
    side = str(p.get("side", "right"))
    if side not in ("right", "left"):
        raise ValueError("未知手别 %r（应为 right/left）" % side)
    suf = "_r" if side == "right" else "_l"
    amp = float(p.get("amp", 0.075))
    reps = max(1, int(p.get("reps", 2)))

    u = float(np.clip(u, 0.0, 1.0))
    ru, sw = wave_envelope(u)
    # 摆动段内按 reps 重复，并让腕滞后
    lag_w = _lag(u, WAVE_WRIST_LAG)
    sw_w = math.sin(2.0 * math.pi * reps * (u - WAVE_RAISE_U) / (1.0 - WAVE_RAISE_U)) \
        if u > WAVE_RAISE_U else 0.0
    sw_w *= (1.0 - 0.25 * (1.0 - lag_w))          # 滞后→幅度略减，避免僵直

    # 抬臂：腕 > 肘 > 肩（末端位移最大）
    dy_w = amp * ru
    dy_e = amp * 0.62 * ru
    dy_s = amp * 0.18 * ru
    # 摆动：横向位移，腕最大
    dz_w = amp * WAVE_WRIST_FRAC * sw_w * 1.0
    dz_e = amp * 0.35 * sw
    dz_s = amp * 0.10 * sw
    j = {
        "wri" + suf: (0.0, dy_w, dz_w),
        "elb" + suf: (0.0, dy_e, dz_e),
        "sh" + suf: (0.0, dy_s, dz_s),
    }
    return {"J": j, "phase": "raise" if u <= WAVE_RAISE_U else "swing"}


# ---------------------------------------------------------------- 翻页
@capability("page_flip", "page curl: x*cos(πu) mirror + y*sin(πu) arc, spine fixed", "arm")
def page_flip(u, params=None):
    """翻页：手带过书页中线，纸张绕书脊镜像。params: side(right/left) amp"""
    p = dict(params or {})
    side = str(p.get("side", "right"))
    if side not in ("right", "left"):
        raise ValueError("未知手别 %r（应为 right/left）" % side)
    suf = "_r" if side == "right" else "_l"
    amp = float(p.get("amp", 0.030))
    u = float(np.clip(u, 0.0, 1.0))

    arc = np.sin(np.pi * u)                       # 手走半圆：起落都在书面上
    sweep = (2.0 * u - 1.0) * (1.0 if side == "right" else -1.0)
    j = {
        "wri" + suf: (amp * sweep, -amp * 0.6 * arc, amp * 0.5 * arc),
        "elb" + suf: (amp * 0.5 * sweep, -amp * 0.2 * arc, 0.0),
        "sh" + suf: (amp * 0.2 * sweep, 0.0, 0.0),
    }
    return {"J": j, "phase": "flip", "detail": {"curl": page_curl(u), "side": side}}


def page_curl(u):
    """书页变形量：返回 (x_scale, y_lift)。x 从 1 镜像到 -1，y 起半圆弧。"""
    u = float(np.clip(u, 0.0, 1.0))
    return float(np.cos(np.pi * u)), float(np.sin(np.pi * u) * CURL_SCALE)


def page_shadow(u):
    """翻页阴影强度：中途（u≈0.5，页垂直）最深，两端为 0。"""
    u = float(np.clip(u, 0.0, 1.0))
    return float(1.0 - abs(2.0 * u - 1.0))


# ---------------------------------------------------------------- 自检
def _asserts():
    """汇总全部断言，返回 [(名称, 判定, 说明)]。分组子函数各管一组。"""
    out = []

    def chk(name, cond, info=""):
        out.append((name, bool(cond), info))

    _chk_gaze(chk)
    _chk_tap(chk)
    _chk_page(chk)
    _chk_continuity(chk)
    return out


def _chk_gaze(chk):
    v = eye_velocity(20.0)
    chk("眼速随角距增大", eye_velocity(40.0) > v > 0, "%.1f→%.1f deg/s" % (v, eye_velocity(40.0)))
    g0, g1 = gaze_shift(0.0, {}), gaze_shift(1.0, {})
    chk("注视起点无偏移", abs(g0["J"]["head"][0]) < 1e-12)
    chk("注视终点有偏移", abs(g1["J"]["head"][0]) > 1e-6, "%.4f" % g1["J"]["head"][0])
    eye_h, head_h = gaze_shift(0.2, {})["detail"]["eye"], gaze_shift(0.2, {})["detail"]["head"]
    chk("眼先于头", eye_h > head_h, "eye %.3f > head %.3f" % (eye_h, head_h))
    chk("头滞后于颈再胸",
        abs(g1["J"]["head"][0]) > abs(g1["J"]["neck"][0]) > abs(g1["J"]["chest"][0]))

def _chk_tap(chk):
    a = tap_envelope(0.25)[0]                       # 抬起
    lo = min(tap_envelope(x)[0] for x in np.linspace(0.5, 0.9, 41))
    chk("敲击先抬后落", a > 0 > lo, "抬 %.3f → 最低 %.3f" % (a, lo))
    chk("敲击段名三态", {tap_envelope(x)[1] for x in (0.2, 0.55, 0.9)} ==
        {"anticipation", "strike", "settle"})
    try:
        finger_tap(0.5, {"side": "mid"})
        chk("未知手别报错", False)
    except ValueError:
        chk("未知手别报错", True)

def _chk_page(chk):
    x0, y0 = page_curl(0.0)
    xm, ym = page_curl(0.5)
    x1, y1 = page_curl(1.0)
    chk("翻页 x 由1镜像到-1", abs(x0 - 1) < 1e-9 and abs(x1 + 1) < 1e-9,
        "%.2f→%.2f" % (x0, x1))
    chk("翻页中途起弧最大", ym > y0 and ym > y1, "%.3f" % ym)
    chk("阴影中途最深", page_shadow(0.5) > page_shadow(0.0),
        "%.2f vs %.2f" % (page_shadow(0.5), page_shadow(0.0)))

def _chk_continuity(chk):
    """任一动作相邻帧位移有界（防闪烁）"""
    for fn, kw in ((gaze_shift, {"yaw": 1.0}), (finger_tap, {"reps": 3}),
                   (page_flip, {})):
        mx = 0.0
        prev = None
        for i in range(61):
            j = fn(i / 60.0, kw)["J"]
            cur = np.array([c for v in j.values() for c in v])
            if prev is not None:
                mx = max(mx, float(np.abs(cur - prev).max()))
            prev = cur
        chk("%s 无跳变" % fn.__name__, mx < 0.01, "max Δ %.5f" % mx)


def self_check():
    rows = _asserts()
    ok = all(c for _, c, _ in rows)
    for name, cond, info in rows:
        print("  %-22s %s  %s" % (name, "PASS" if cond else "FAIL", info))
    print("SELF_CHECK: %s" % ("PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    self_check()
