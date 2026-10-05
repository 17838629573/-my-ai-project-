# -*- coding: utf-8 -*-
"""道具交接模块（动作层·道具）

契约: proc/motion/character/prop
  一句话: 道具交接 —— pickup→held→release→recovery 四相位，所有权 world↔hand 显式切换
  完整契约见 motion/character/__init__.py

  输入: 道具尺寸/颜色/握持手、四相时长、相位进度 u、骨架关节 J(归一化身高)、
        各相位的手部目标点(归一化身高, 身体坐标系)
  输出: {'phase':str, 'owner':str, 'J':{关节:(u,v,w)}, 'events':[str]}
  依赖: numpy, motion.character.leg(两骨IK)
  被依赖: motion.cafe, motion.beat
  约束: 所有权切换只在 pickup 末(attach) 与 release 末(detach) 两个事件点发生，
        各只触发一次(不重复 release)；detach 瞬间道具世界位置连续无跳变；
        pivot 取道具底面中心(UE5: 放下需补偿 pivot→bounds)；
        交接前后道具恰好可见一次；未知握持手报错不静默
  校验: python -m motion.character.prop
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

from .body import leg
from .body.joints import ARM_SEG as SEG, SOLE_LIFT
from ..beat import CAP, capability

# 四相位时长（占交接总时长），和为 1
#   出处 FrameSprite《Carry and Throw Sprites: Define the Release Point》(2026-09-30)
SPANS = (0.30, 0.15, 0.30, 0.25)          # pickup / held / release / recovery
PHASES = ("pickup", "held", "release", "recovery")
ATTACH_AT, DETACH_AT = 0.30, 0.75         # = SPANS 前缀和：两个所有权切换点
GRIP_ZONE = 0.18                          # 双手握持判定半径(米)，出处 PropHandoff(Blender)
REACH_FRAC = 0.98                         # 最大伸展占臂展比，留 2% 余量避免肘完全锁死
                                          # 出处 two_bone_ik 余弦定理解：|d| > L1+L2 无解
SIDES = ("right", "left", "both")

__all__ = ["SPANS", "PHASES", "GRIP_ZONE", "REACH_FRAC", "Prop", "phase_of", "pivot_offset",
           "grip_offset", "ease_target", "reach_arm", "clamp_arm", "Handoff", "draw_prop",
           "world_to_body", "body_to_world", "grab_point_world", "grab_target",
           "drop_point_world", "can_transfer", "transfer"]


# ------------------------------------------------------------ 相位
def phase_of(u, spans=SPANS):
    """归一化进度 u∈[0,1] → 相位名。u 已被调用方保证在 [0,1]。"""
    if not (0.0 <= u <= 1.0):
        raise ValueError("phase_of: u 越界 %r（应为 0~1）" % (u,))
    acc, cum = PHASES[0], 0.0
    for name, sp in zip(PHASES, spans):
        cum += sp
        if u < cum - 1e-12:
            return name
        acc = name
    return acc


def ease_target(a, b, t):
    """smoothstep 缓动：3t²−2t³。出处 FrameSprite（手接近/回位均需缓动，忌线性）。"""
    t = float(np.clip(t, 0.0, 1.0))
    k = t * t * (3.0 - 2.0 * t)
    a, b = np.asarray(a, float), np.asarray(b, float)
    return a + (b - a) * k


def pivot_offset(size):
    """pivot(底面中心) → 几何中心的偏移（归一化身高）。

    出处 UE5 程序化拾取教程：pivot 不在网格底部时，放下会浮空/陷入，
    需补偿 pivot→bounds 偏移。我们一律把 pivot 定在底面中心。
    """
    wm, hm, dm = size
    return np.array([0.0, hm * 0.5, 0.0])      # 中心在 pivot 之上 hm/2


def grip_offset(size, side="right"):
    """抓取点相对手腕的偏移（归一化身高）：手在道具侧面中上部。"""
    if side not in SIDES:
        raise ValueError("grip_offset: 未知握持手 %r（应为 %s）" % (side, SIDES))
    wm, hm, dm = size
    lat = (wm * 0.5 + 0.02) * (-1.0 if side == "left" else 1.0)
    return np.array([0.0, hm * 0.35, lat]) if side != "both" else \
        np.array([0.0, hm * 0.35, 0.0])


# ------------------------------------------------------------ 世界 ↔ 身体坐标
# project_body(render.py) 的旋转矩阵是正交阵，转置即逆，可精确反算：
#     X = Xc + U*sinθ + W*cosθ      U = dX*sinθ + dZ*cosθ
#     Z = Zc + U*cosθ - W*sinθ  ⇒   W = dX*cosθ - dZ*sinθ
# 世界坐标一律 (X, Y, Z)，Y = 离地高度(米)；身体坐标 (u, v, w)，归一化身高。
def world_to_body(P, Xc, Zc, yaw, body_h=1.70):
    """世界 (X,Y,Z) → 身体 (u,v,w)。手要抓地上的杯子，就得先把它换算到身体坐标。"""
    th = math.radians(float(yaw))
    st, ct = math.sin(th), math.cos(th)
    P = np.asarray(P, float)
    dX, dZ = P[0] - float(Xc), P[2] - float(Zc)
    U = dX * st + dZ * ct
    W = dX * ct - dZ * st
    return np.array([U / body_h, P[1] / body_h - SOLE_LIFT, W / body_h])


def body_to_world(p, Xc, Zc, yaw, body_h=1.70):
    """身体 (u,v,w) → 世界 (X,Y,Z)。world_to_body 的逆。"""
    th = math.radians(float(yaw))
    st, ct = math.sin(th), math.cos(th)
    u, v, w = (float(x) for x in np.asarray(p, float))
    U, V, W = u * body_h, (v + SOLE_LIFT) * body_h, w * body_h
    return np.array([Xc + U * st + W * ct, V, Zc + U * ct - W * st])


def grab_point_world(prop, Xc, Zc, yaw, side=None):
    """抓取时手腕应在的世界位置（米）。

    出处 UE5 程序化拾取教程：IK 目标不应直接等于物体位置，而要反算手骨位置，
    使"手上的抓取点"落在物体上。这里腕 = 底面中心上方 0.35·高，
    再沿身体的"右"方向偏出半个宽 —— 于是手指正好环住杯壁。
    """
    side = side or (prop.grip if prop.grip != "both" else "right")
    if side not in SIDES:
        raise ValueError("grab_point_world: 未知握持手 %r（应为 %s）" % (side, SIDES))
    th = math.radians(float(yaw))
    st, ct = math.sin(th), math.cos(th)
    wm, hm, dm = prop.size
    lat = (wm * 0.5 + 0.02) * (-1.0 if side == "left" else 1.0)
    # 身体"右"在世界 XZ 平面的方向 = (cosθ, -sinθ)
    return np.asarray(prop.pivot, float) + np.array([lat * ct, hm * 0.35, -lat * st])


def grab_target(prop, Xc, Zc, yaw, body_h=1.70, side=None):
    """抓取目标（身体坐标，归一化身高）：手腕该伸到哪里。"""
    return world_to_body(grab_point_world(prop, Xc, Zc, yaw, side),
                         Xc, Zc, yaw, body_h)


def drop_point_world(prop, surface_h, Xc, Zc, yaw, side=None):
    """放下时道具底面中心该落在的世界位置：给定台面高度，贴着台面放。"""
    p = grab_point_world(prop, Xc, Zc, yaw, side)
    wm, hm, dm = prop.size
    return np.array([p[0], float(surface_h), p[2]])


# ------------------------------------------------------------ 左右手交接
def can_transfer(J, body_h=1.70, threshold=GRIP_ZONE):
    """双手是否进入交接区（米）。出处 PropHandoff(Blender)：
    左右手交棒必须在"双手接触"的那几帧切换 owner，不能凭空换手。
    """
    wl, wr = J.get("wri_l"), J.get("wri_r")
    if wl is None or wr is None:
        return False
    d = np.linalg.norm((np.asarray(wl, float) - np.asarray(wr, float)) * body_h)
    return float(d) <= float(threshold)


def transfer(prop, to_side="right", require_zone=True, J=None, body_h=1.70):
    """换手：owner 从一只手切到另一只手。

    to_side ∈ {"right","left","both"}；require_zone=True 时必须先双手靠拢。
    出处 PropHandoff(Blender)：timeline 中改 parent bone 实现 hand-to-hand。
    """
    if to_side not in SIDES:
        raise ValueError("transfer: 未知目标手 %r（应为 %s）" % (to_side, SIDES))
    if not prop.owner.startswith("hand_"):
        raise ValueError("transfer: 道具当前不在手上（owner=%r），无从交接" % prop.owner)
    if require_zone:
        if J is None:
            raise ValueError("transfer: require_zone 需要传入关节 J")
        if not can_transfer(J, body_h):
            raise ValueError("transfer: 双手未进入交接区（>%.2fm），此时换手会瞬移" % GRIP_ZONE)
    prop.owner = "both" if to_side == "both" else "hand_" + to_side[0]
    return prop.owner


# ------------------------------------------------------------ 手臂 IK
def reach_arm(J, side, target, body_h=1.70):
    """两骨 IK 解手臂：肩→目标，出肘与腕。复用 leg.two_bone_ik（余弦定理解析解）。

    side ∈ {"left","right"}；target 为归一化身高坐标系下的手部目标点。
    出处 ADAPT(Rutgers TVCG 2013) ReachFor(target) 能力函数。
    """
    if side not in ("left", "right"):
        raise ValueError("reach_arm: side 应为 left/right，收到 %r" % (side,))
    sh, elb, wri = "sh_" + side[0], "elb_" + side[0], "wri_" + side[0]
    root = np.asarray(J[sh], float)
    tgt = np.asarray(target, float)
    L1, L2 = SEG["upperarm"], SEG["forearm"]
    # 硬约束：目标超出臂展时先收回到臂展球面，禁止拉伸骨骼
    d = float(np.linalg.norm(tgt - root))
    dmax = (L1 + L2) * REACH_FRAC
    if d > dmax:
        tgt = root + (tgt - root) * (dmax / d)
    bend = np.array([1.0, 0.0, 0.0])            # 肘朝前
    knee = leg.two_bone_ik(root, tgt, L1, L2, bend=bend[:2] if len(root) == 2 else bend)
    J = dict(J)
    J[elb] = tuple(np.asarray(knee, float))
    J[wri] = tuple(tgt)
    return J


def clamp_arm(J, side, frac=REACH_FRAC):
    """把任一来源（gait/sit/gesture）给出的肩→腕距离收进臂展球面，并重解肘。

    任何绕过 reach_arm 的姿态都可能把前臂拉长；本函数是最后一道硬约束。
    返回新的关节字典（不改原对象）。
    """
    if side not in ("right", "left"):
        raise ValueError("clamp_arm: side 应为 right/left，收到 %r" % (side,))
    sh, elb, wri = "sh_" + side[0], "elb_" + side[0], "wri_" + side[0]
    if sh not in J or wri not in J:
        return J
    root = np.asarray(J[sh], float)
    wr = np.asarray(J[wri], float)
    L1, L2 = SEG["upperarm"], SEG["forearm"]
    d = float(np.linalg.norm(wr - root))
    dmax = (L1 + L2) * frac
    if d <= dmax or d < 1e-12:
        return J
    wr = root + (wr - root) * (dmax / d)
    bend = np.array([1.0, 0.0, 0.0])
    knee = leg.two_bone_ik(root, wr, L1, L2,
                           bend=bend[:2] if len(root) == 2 else bend)
    J = dict(J)
    J[elb] = tuple(np.asarray(knee, float))
    J[wri] = tuple(wr)
    return J


# ------------------------------------------------------------ 所有权状态机
class Prop:
    """一件道具。owner ∈ {"world","hand_r","hand_l","both"}。"""

    def __init__(self, name, size=(0.08, 0.10, 0.08), color=(235, 232, 226),
                 grip="right", pivot=(0.0, 0.0, 0.0)):
        self.name = name
        self.size = tuple(float(x) for x in size)
        self.color = tuple(int(c) for c in color)
        if grip not in SIDES:
            raise ValueError("Prop: 未知握持手 %r（应为 %s）" % (grip, SIDES))
        self.grip = grip
        self.pivot = np.asarray(pivot, float)    # 底面中心的世界位置 (X, Y, Z)
        self.owner = "world"

    def center(self):
        """几何中心（世界，米）：pivot + pivot→center 偏移。"""
        off = pivot_offset(self.size)
        return self.pivot + np.array([off[2], off[1], off[0]])

    def attach(self, to=None):
        to = to or ("both" if self.grip == "both" else "hand_" + self.grip[0])
        self.owner = to

    def detach(self):
        self.owner = "world"


class Handoff:
    """一次交接的推进器。事件各只触发一次，杜绝重复 release。

    出处 FrameSprite 责任表：
      Pickup   手接近，世界对象待挂接
      Held     握持姿态，跟随锚点
      Release  手张开，移交世界运动
      Recovery 手臂回位，且不重复 release
    """

    def __init__(self, prop, spans=SPANS):
        s = np.asarray(spans, float)
        if abs(s.sum() - 1.0) > 1e-9:
            raise ValueError("Handoff: 四相时长和应为 1，实为 %.6f" % s.sum())
        self.prop, self.spans = prop, tuple(s)
        self.attach_at = float(s[0])
        self.detach_at = float(s[0] + s[1] + s[2])
        self._fired = set()

    def advance(self, u):
        """推进到进度 u，返回 {'phase','owner','events'}。"""
        u = float(np.clip(u, 0.0, 1.0))
        ev = []
        if u >= self.attach_at and "attach" not in self._fired:
            self._fired.add("attach")
            self.prop.attach()
            ev.append("attach")
        if u >= self.detach_at and "detach" not in self._fired:
            self._fired.add("detach")
            self.prop.detach()
            ev.append("detach")
        if u >= 1.0 - 1e-12 and "done" not in self._fired:
            self._fired.add("done")
            ev.append("done")
        return {"phase": phase_of(u, self.spans),
                "owner": self.prop.owner, "events": ev}

    def target_at(self, u, rest, grab, drop):
        """手部目标点：pickup rest→grab，held=grab，release grab→drop，recovery drop→rest。"""
        u = float(np.clip(u, 0.0, 1.0))
        a, b, c, d = self.spans
        if u < a:
            return ease_target(rest, grab, u / max(a, 1e-9))
        if u < a + b:
            return np.asarray(grab, float)
        if u < a + b + c:
            return ease_target(grab, drop, (u - a - b) / max(c, 1e-9))
        return ease_target(drop, rest, (u - a - b - c) / max(d, 1e-9))


# ------------------------------------------------------------ 绘制
def draw_prop(cv, cam, prop, anchor_px=None, s=None):
    """画道具（立方体线框+面）。anchor_px 给定时用它（握持中），否则世界投影。"""
    wm, hm, dm = prop.size
    if anchor_px is None:
        X, Y, Z = prop.pivot
        bx, by, sc = cam.proj(X, Z, Y)
        bx, by = bx, by
        s = sc
    else:
        bx, by = float(anchor_px[0]), float(anchor_px[1])
        s = float(s if s else 1.0)
    hp = hm * s
    wp = wm * s
    x0, y1 = bx - wp * 0.5, by
    x1, y0 = bx + wp * 0.5, by - hp
    d = cv.d
    pts = [(int(round(x0)), int(round(y0))), (int(round(x1)), int(round(y0))),
           (int(round(x1)), int(round(y1))), (int(round(x0)), int(round(y1)))]
    d.polygon(pts, fill=prop.color)
    d.rectangle([pts[0], pts[2]], outline=(60, 50, 42), width=1)
    return (bx, by)


# ================================================================
# 自检
# ================================================================
if __name__ == "__main__":
    from .joints import REST_ARM
    ok = True

    def chk(name, cond, extra=""):
        global ok
        ok = ok and bool(cond)
        print("  %-28s %s %s" % (name, "OK" if cond else "FAIL", extra))

    print("=" * 64)
    print("  prop 自检   (出处: FrameSprite 责任表 / PropHandoff / UE5 / ADAPT)")
    print("=" * 64)

    # 1 四相位时长和为 1，顺序正确
    chk("四相时长和=1", abs(sum(SPANS) - 1.0) < 1e-12, "sum=%.3f" % sum(SPANS))
    seq = [phase_of(u) for u in (0.05, 0.35, 0.60, 0.90)]
    chk("相位顺序", seq == list(PHASES), str(seq))

    # 2 交接全程：attach / detach / done 各只触发一次
    cup = Prop("cup", size=(0.08, 0.10, 0.08), grip="right")
    ho = Handoff(cup)
    fires = {"attach": 0, "detach": 0, "done": 0}
    owners = []
    for i in range(101):
        r = ho.advance(i / 100.0)
        for e in r["events"]:
            fires[e] += 1
        owners.append(r["owner"])
    chk("事件各触发一次", all(v == 1 for v in fires.values()), str(fires))

    # 3 交接前后道具恰好可见一次（owner 全程唯一，无重复实例）
    chk("所有者全程唯一", len(set(owners)) == 2 and "world" in owners,
        str(sorted(set(owners))))

    # 4 detach 瞬间世界位置连续无跳变（release 末手已到 drop 点）
    rest, grab, drop = REST_ARM, np.array([0.30, 0.62, 0.12]), np.array([0.22, 0.42, 0.10])
    eps = 1e-4
    p_before = ho.target_at(ho.detach_at - eps, rest, grab, drop)
    p_after = ho.target_at(ho.detach_at + eps, rest, grab, drop)
    jump = float(np.linalg.norm(np.asarray(p_after) - np.asarray(p_before)))
    chk("detach 无跳变", jump < 5e-3, "跳变 %.2e" % jump)

    # 5 目标点轨迹：pickup 末到 grab，release 末到 drop
    chk("pickup 末=grab",
        np.allclose(ho.target_at(ho.attach_at, rest, grab, drop), grab, atol=2e-3))
    chk("release 末=drop",
        np.allclose(ho.target_at(ho.detach_at, rest, grab, drop), drop, atol=2e-3))

    # 6 pivot 在底面 → 中心上移 hm/2
    off = pivot_offset((0.08, 0.10, 0.08))
    chk("pivot 补偿 = hm/2", abs(off[1] - 0.05) < 1e-12, "dy=%.4f" % off[1])

    # 7 两骨 IK 骨长守恒（手臂）
    J = {"sh_r": (0.0, 0.82, 0.115), "elb_r": (0.05, 0.70, 0.12),
         "wri_r": (0.10, 0.58, 0.12),
         "sh_l": (0.0, 0.82, -0.115), "elb_l": (0.05, 0.70, -0.12),
         "wri_l": (0.10, 0.58, -0.12)}
    J2 = reach_arm(J, "right", (0.16, 0.62, 0.14))
    e1 = abs(np.linalg.norm(np.array(J2["elb_r"]) - np.array(J2["sh_r"])) - SEG["upperarm"])
    e2 = abs(np.linalg.norm(np.array(J2["wri_r"]) - np.array(J2["elb_r"])) - SEG["forearm"])
    chk("上臂骨长守恒", e1 < 1e-9, "误差 %.2e" % e1)
    chk("前臂骨长守恒", e2 < 1e-9, "误差 %.2e" % e2)

    # 8 未知握持手 / 未知 side 报错，不静默
    errs = 0
    caught = 0
    for fn in (lambda: Prop("x", grip="middle"),
               lambda: grip_offset((1, 1, 1), "middle"),
               lambda: reach_arm(J, "mid", (0, 0, 0)),
               lambda: phase_of(1.5)):
        try:
            fn(); errs += 1          # 没抛异常 = 漏报
        except (ValueError, KeyError):
            caught += 1              # 抛了才是正确行为，显式计数不留裸 pass
    chk("未知参数报错不静默", errs == 0 and caught == 4,
        "漏报 %d 处 / 已捕获 %d 处" % (errs, caught))

    # --- 世界↔身体反算（抓点对齐的前提）---
    for yaw in (0.0, 90.0, 180.0, 143.0):
        p = np.array([0.12, 0.55, -0.07])
        w = body_to_world(p, -1.6, 4.2, yaw, 1.70)
        back = world_to_body(w, -1.6, 4.2, yaw, 1.70)
        chk("yaw=%.0f 往返一致" % yaw, float(np.max(np.abs(back - p))) < 1e-9,
            "偏差 %.3g" % float(np.max(np.abs(back - p))))

    # 抓点反算：手伸到 grab_target 时，抓取点必须落在道具上
    cup = Prop("cup", size=(0.08, 0.10, 0.08), grip="right",
               pivot=(-1.55, 0.42, 4.55))
    for yaw in (0.0, 180.0, 90.0):
        tgt = grab_target(cup, -1.60, 4.20, yaw, 1.70)
        wrist_w = body_to_world(tgt, -1.60, 4.20, yaw, 1.70)
        gp_w = grab_point_world(cup, -1.60, 4.20, yaw)
        d = float(np.linalg.norm(wrist_w - gp_w))
        chk("yaw=%.0f 抓点落在道具上" % yaw, d < 1e-9, "腕与抓取点差 %.4fm" % d)

    # 关键：抓点必须随人物位置走 —— 人物走远后不能还指向原地（否则手被拉长）
    tgt_a = grab_target(cup, -1.60, 4.20, 0.0, 1.70)
    tgt_b = grab_target(cup, -1.70, 5.40, 0.0, 1.70)
    chk("抓点随人物位置更新", float(np.max(np.abs(tgt_a - tgt_b))) > 1e-6,
        "人物走了抓点却没变（手会被拉长）")

    # --- 左右手交接 ---
    cup.attach()
    chk("attach 后 owner 为右手", cup.owner == "hand_r", cup.owner)
    far = {"wri_l": (0.10, 0.30, -0.25), "wri_r": (0.10, 0.30, 0.25)}
    near = {"wri_l": (0.10, 0.30, -0.02), "wri_r": (0.10, 0.30, 0.02)}
    chk("双手远离时不可交接", not can_transfer(far, 1.70), "误判为可交接")
    chk("双手靠拢时可交接", can_transfer(near, 1.70), "漏判")
    try:
        transfer(cup, "left", J=far, body_h=1.70)
        chk("远离换手应报错", False, "竟然换成了")
    except ValueError:
        chk("远离换手应报错", True, "")
    chk("靠拢后才换手", transfer(cup, "left", J=near, body_h=1.70) == "hand_l",
        cup.owner)
    try:
        cup.detach()
        transfer(cup, "right", J=near, body_h=1.70)
        chk("不在手上不可交接", False, "竟然换成了")
    except ValueError:
        chk("不在手上不可交接", True, "")

    print("-" * 64)
    print("  prop 自检:", "PASS" if ok else "FAIL")


@capability("carry_prop", "FrameSprite 责任表 / ADAPT ReachFor", "action")
def _cap_carry():
    """握持：pickup 末 attach 到手，held 期间所有权唯一。"""
    return "pickup->held"


@capability("prop_release", "FrameSprite 责任表 / UE5 pivot 补偿", "action")
def _cap_release():
    """放下：release 末 detach 回世界，pivot 补偿底面->中心。"""
    return "release->recovery"
