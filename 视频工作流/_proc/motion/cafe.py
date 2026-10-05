# 契约: proc/motion/cafe
#   一句话: 咖啡馆 12 秒时间线：四段动作（坐姿→抬头→起身走→落座沙发）
#   完整契约见 motion/__init__.py

import os
import sys

# 路径自举：锚定 __file__ 的绝对路径，保证从任意 cwd 直接跑都能导入。
_HERE = os.path.dirname(os.path.abspath(__file__))   # .../视频工作流/_proc/motion
_PROC = os.path.dirname(_HERE)                       # .../视频工作流/_proc
_ROOT = os.path.dirname(_PROC)                       # .../视频工作流
for _p in (_ROOT, _PROC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import math
import numpy as np
from PIL import ImageDraw
from scene import kit
from scene.kit import indoor, props
from motion import camera, run
from motion.character import sit
from motion.character.gait import gait
from motion.character import prop as PROP, joints as JN
from motion.character import gesture as G
from motion.character import turn as T
from shape import line
from color import paint

W, H, FPS = 540, 960, 24
BODY_H = 1.68
STEP = 0.414 * BODY_H                  # 0.696 m/步（文献步长，与骨架交叉校验）

# ---- 世界锚点 ----
ST = (-1.60, 4.20)                     # 凳子（世界 X,Z）
SF = (-1.70, 5.40)                     # 沙发
CUP_W0 = (-1.55, 1.05, 4.55)           # 吧台桌面（table 锚点 1.05m，配高脚椅）
CUP_W1 = (-1.62, 0.46, 5.30)           # 沙发矮桌

# ---- 时序（段3 内部细分：站起 → 拿杯 → 转身 → 走 → 放杯 → 落座）----
T_STAND = (6.0, 6.8)
T_HO = (6.8, 11.8)                     # 道具交接窗口
T_TURN = (8.3, 9.3)                    # 转身：面向镜头 → 背对镜头走向沙发
T_WALK = (9.3, 11.1)
T_SITDN = (11.5, 12.0)
YAW0, YAW1 = 180.0, 0.0                # 180 正对镜头 / 0 背对镜头走远

HO_SPANS = (0.30, 0.55, 0.07, 0.08)    # pickup/held/release/recovery
T_ATTACH = T_HO[0] + (T_HO[1] - T_HO[0]) * HO_SPANS[0]
T_DETACH = T_HO[0] + (T_HO[1] - T_HO[0]) * sum(HO_SPANS[:3])

CUP = PROP.Prop("cup", size=(0.08, 0.10, 0.08), color=(238, 234, 226), grip="right")
HO = PROP.Handoff(CUP, spans=HO_SPANS)
_HOLD = {"p": None}                    # attach 瞬间的持杯腕位（身体坐标，跟随身体）


def _bg():
    cv = kit.Canvas(W, H)
    g = indoor.make_geom(W, H)
    indoor.draw_shell(cv, g)
    indoor.draw_floor(cv, g)
    props.draw_window(cv, g)
    props.draw_bookshelf(cv, g)
    props.draw_photos(cv, g)
    props.draw_props(cv, g)
    return cv.img, g


def _lerp_pose(a, b, t):
    t = float(max(0.0, min(1.0, t)))
    return {k: np.asarray(a[k]) * (1 - t) + np.asarray(b[k]) * t for k in a}


def _seg(t):
    """四段：0-3 坐姿 / 3-6 抬头 / 6-9 站起+拿杯+转身 / 9-12 走+放杯+落座

    返回 (坐势, Xc, Zc, 是否在走, yaw)。yaw 连续插值，不做 180/0 硬切。
    """
    if t < 6.0:                                  # 段1-2 坐姿 / 抬头
        return 0.5, ST[0], ST[1], False, YAW0
    if t < T_STAND[1]:                           # 段3a 站起（6.0-6.8）
        u = (t - T_STAND[0]) / (T_STAND[1] - T_STAND[0])
        return 0.5 + 0.5 * sit._ease(u), ST[0], ST[1], False, YAW0
    if t < T_WALK[0]:                            # 段3b 拿杯 + 转身（原地）
        u = (t - T_TURN[0]) / (T_TURN[1] - T_TURN[0]) if t >= T_TURN[0] else 0.0
        return 0.0, ST[0], ST[1], False, T.turn_yaw(YAW0, YAW1 - YAW0, u)
    if t < T_WALK[1]:                            # 段4a 走向沙发（9.1-10.9）
        u = (t - T_WALK[0]) / (T_WALK[1] - T_WALK[0])
        return (0.0, ST[0] + (SF[0] - ST[0]) * u,
                ST[1] + (SF[1] - ST[1]) * u, True, YAW1)
    u = (t - T_SITDN[0]) / (T_SITDN[1] - T_SITDN[0])   # 段4b 落座（11.4-12）
    return 0.5 * sit._ease(min(1.0, u)), SF[0], SF[1], False, YAW1


def _pose_add(J, delta):
    """把 additive 增量 {"J": {关节: (dx,dy,dz)}} 叠加到绝对姿态 J。

    依据: UE Layered Blend per Bone——增量层不改绝对层的根与下肢
    """
    for k, v in delta["J"].items():
        if k in J:
            J[k] = np.asarray(J[k]) + np.asarray(v)
    return J


def _pose_magazine(J, t):
    """杂志相关姿态：段1 食指敲桌 → 段2 抬头+注视+翻页 → 段4 重翻。

    从 pose_at 抽出（原函数 51 行 > R3 上限 50），三段均为 additive 叠加。
    """
    if t < 3.0:
        return _pose_add(J, G.finger_tap((t % 1.0), {"side": "right", "reps": 1}))
    if 3.0 <= t < 6.0:
        u = (t - 3.0) / 3.0
        lift = 0.030 * math.sin(math.pi * u)
        for k in ("head", "chest", "neck"):
            if k in J:
                J[k] = np.asarray(J[k]) + np.array([0.0, lift, 0.0])
        if u < 0.8:                              # 视线移向窗外（注视转移）
            _pose_add(J, G.gaze_shift(min(1.0, u / 0.8), {"dir": 1.0}))
        if 0.35 <= u < 0.95:                     # 翻过一页书
            _pose_add(J, G.page_flip((u - 0.35) / 0.60, {"side": "right"}))
        return J
    if t >= 10.2:                                # 段4 重新翻开杂志
        return _pose_add(J, G.page_flip(min(1.0, (t - 10.2) / 1.6), {"side": "right"}))
    return J


def pose_at(t):
    sp, Xc, Zc, walk, yaw = _seg(t)
    J = sit.sit_pose(max(0.0, min(1.0, sp)))
    if walk:                                     # 相位由里程驱动，脚才不打滑
        dist = math.hypot(Xc - ST[0], Zc - ST[1])
        J = gait((dist / (2.0 * STEP)) % 1.0)
    if T_TURN[0] <= t < T_TURN[1]:               # 原地转身：换步抬脚 + 躯干滞后
        u = (t - T_TURN[0]) / (T_TURN[1] - T_TURN[0])
        J = T.turn_legs(J, u)
    J = _pose_magazine(J, t)                     # 敲桌 / 抬头 / 翻页：全 additive
    yaw = _seg(t)[4]
    if CUP.owner == "world":                     # 杯在世界中：桌面 / 矮桌
        CUP.pivot = np.array(CUP_W1 if t >= T_DETACH else CUP_W0, float)
    if T_HO[0] <= t <= T_HO[1]:                  # 道具交接：右臂 IK 追踪手部目标
        u = (t - T_HO[0]) / (T_HO[1] - T_HO[0])
        HO.advance(u)
        if u >= HO_SPANS[0] and _HOLD["p"] is None:
            _HOLD["p"] = PROP.grab_target(CUP, Xc, Zc, yaw, BODY_H)  # 锁定持杯位
        grab_b = _HOLD["p"] if _HOLD["p"] is not None else \
            PROP.grab_target(CUP, Xc, Zc, yaw, BODY_H)
        _sv, CUP.pivot = CUP.pivot, np.array(CUP_W1, float)
        drop_b = PROP.grab_target(CUP, Xc, Zc, yaw, BODY_H)
        CUP.pivot = _sv
        J = PROP.reach_arm(J, "right",
                           HO.target_at(u, JN.REST_ARM, grab_b, drop_b))
    return J, Xc, Zc, yaw


def frame(t, bg, cam, palette):
    J, Xc, Zc, yaw = pose_at(t)
    cv = kit.Canvas(W, H)
    cv.img = bg.copy()
    cv.d = ImageDraw.Draw(cv.img)
    # 手指弯曲：段1 食指敲击（包络 +1 抬起 → -1 落下），其余放松握曲
    val = G.tap_envelope(t % 1.0)[0] if t < 3.0 else 0.0
    curl = {"r": {i: (0.30 + 0.18 * val if i == 1 else 0.30) for i in range(5)},
            "l": {i: 0.30 for i in range(5)}}
    Jp = run.draw_actor(cv, cam, J, Xc=Xc, Zc=Zc, yaw=yaw,
                        body_h=BODY_H, template="humanoid", palette=palette,
                        hand_lod=1, hand_curl=curl)
    if CUP.owner != "world" and "wri_r" in Jp:    # 握持中 → 锚在腕关节
        PROP.draw_prop(cv, cam, CUP, anchor_px=Jp["wri_r"][:2], s=Jp["wri_r"][2])
    else:                                          # 在世界中 → 桌面/矮桌二选一
        CUP.pivot = np.array(CUP_W1 if t >= T_DETACH else CUP_W0, float)
        PROP.draw_prop(cv, cam, CUP)
    return cv.img


def main():
    bg, g = _bg()
    cam = camera.fit(g, cam_h=g["eye"], f=g["f"])
    palette = {"skin": paint.hex2rgb(paint.FITZPATRICK["III"][0]),
               "hair": paint.hex2rgb("#2b2118"),
               "robe": paint.hex2rgb("#f0e6d2"),
               "sole": paint.hex2rgb("#2f3b57")}
    n = 12 * FPS
    _HOLD["p"] = None                            # 防 frame 复用
    fr = [frame(i / float(FPS), bg, cam, palette) for i in range(n)]
    run.to_mp4(fr, "咖啡馆_12秒.mp4", fps=FPS)
    for i in (0, 3, 6, 9, 11):
        fr[i * FPS].save("咖啡馆_t%02ds.png" % i)
    print("相机:", cam.info())
    print("段位抽样:")
    for t in (1.5, 4.5, 6.5, 8.0, 8.7, 10.0, 11.6):
        sp, X, Z, w, y = _seg(t)
        print("  t=%.1fs 坐势=%.2f X=%.2f Z=%.2f yaw=%.0f" % (t, sp, X, Z, y))
    print("saved 咖啡馆_12秒.mp4 (%d 帧)" % n)


if __name__ == "__main__":
    main()
