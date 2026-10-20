#   契约: B 组抓放道具用例体（拿杯子 / 放下杯子）。
#   完整契约见 tests/__init__.py
#   依据: 用例体与驱动分离（R2 >500 防超纲）；原属 cases_base.py，
#         该文件 510 行超 R2 上限 500，按"同组用例同文件"原则将抓放一组
#         整体迁出，判据与实现一字未改。
#   输入: 无（用例体，由 run_all 驱动）
#   输出: (checks, meta)
#   依赖: motion（prop / crouch）
#   约束: 判据名与 harness.CRIT 一致，不得自造
#   校验: python _proc/tools/batchgate.py
# -*- coding: utf-8 -*-
from .common import *          # noqa: F401,F403  常量: np / H
from motion.character.prop import grab_point_world


def _grip_hand(cup, Xc=0.0, Zc=0.0, yaw=0.0):
    """手心应到的位置(米)：物体中心 + 抓握方向 × (物体半径 + 腕到抓握点)

    出处 crouch.py：手心到物体中心 = 物体半径 + 腕到抓握点
    """
    from motion.character.crouch import WRIST_TO_GRIP
    G = np.asarray(grab_point_world(cup, Xc, Zc, yaw), float)
    c = np.asarray(cup.center(), float)
    d = G - c
    r = 0.5 * float(cup.size[0])
    return c + d / np.linalg.norm(d) * (r + WRIST_TO_GRIP)

def _b8_hand(u, G, rest):
    """B8 单帧手位：pickup 段由体侧缓动到握点，之后水平随行。

    从 case_B8 主循环抽出（原函数 CCN 12 > design 阈值 10，被债务棘轮判为
    新增真问题）。相位划分与插值口径逐条照搬，判据未改。
    """
    from motion.character import prop as P
    if P.phase_of(u) == "pickup":
        return np.asarray(P.ease_target(rest, G, u / P.SPANS[0]), float)
    return G + np.array([0.6 * (u - P.SPANS[0]) / (1 - P.SPANS[0]), 0.0, 0.0])


def _b8_meta(cens, owners, att):
    """B8 输出元信息：attach 帧、握持期高度漂移、随行距离、末帧归属。"""
    ys = [cens[i][1] for i in att]
    return {"attach帧": att[0] if att else None,
            "杯心高度漂移_m": round(max(ys) - min(ys), 6) if ys else None,
            "持杯随行_m": round(float(np.linalg.norm(cens[-1] - cens[att[0]])), 4)
            if att else 0.0,
            "末帧owner": owners[-1]}


def case_B8():
    """拿杯子：手伸向杯子→手指闭合(attach)→杯固定在手中→移动时不掉落

    依据: FrameSprite 四相位责任表，attach 在 u=SPANS[0]；
    手心到杯心 = 杯半径 + 腕到抓握点 0.038m（出处 crouch.py）
    """
    from motion.character import prop as P
    from motion.character.crouch import WRIST_TO_GRIP
    FPS = 60.0
    surf = 1.05
    cup = P.Prop("cup", size=(0.08, 0.10, 0.08), grip="right", pivot=(0.0, surf, 1.20))
    G = _grip_hand(cup)
    rel = np.asarray(cup.pivot, float) - G          # 杯底中心相对手心的偏移(握持期恒定)
    rest = np.array([0.24, 1.02, 0.0])
    ho = P.Handoff(cup)
    N = int(1.6 * FPS)
    hands, cens, owners = [], [], []
    for i in range(N):
        u = min(i / (N - 1), 0.999)
        hand = np.asarray(_b8_hand(u, G, rest), float)
        ho.advance(u)
        if cup.owner.startswith("hand"):
            cup.pivot = hand + rel
        hands.append(hand)
        cens.append(np.asarray(cup.center(), float).copy())
        owners.append(cup.owner)
    pen = [(float(np.linalg.norm(h - c)), WRIST_TO_GRIP, 0.5 * cup.size[0])
           for h, c in zip(hands, cens)]
    att = [i for i, o in enumerate(owners) if o.startswith("hand")]
    return [
        ("penetration_m", H.penetration_m(pen)),
        ("frame_jump_ratio", H.frame_jump_ratio(
            [float(np.linalg.norm(cens[i + 1] - cens[i])) for i in range(len(cens) - 1)])),
    ], _b8_meta(cens, owners, att)


def _b9_hand(u, G0, land_hand):
    """B9 单帧手位：抬起→水平运到落点上方→垂直下放→收回。

    从 case_B9 主循环抽出（原函数 54 行 > R3 上限 50）。
    相位划分与插值口径逐条照搬，未改判据。
    """
    from motion.character import prop as P
    over = land_hand + np.array([0.0, 0.25, 0.0])   # 落点正上方的提运高度
    ph = P.phase_of(u)
    if ph == "pickup":                              # 抬起
        k = u / P.ATTACH_AT
        return G0 + (over - G0) * float(np.clip(k, 0.0, 1.0))
    if ph == "held":                                # 水平运到落点上方
        k = (u - P.ATTACH_AT) / P.SPANS[1]
        return over + (land_hand + np.array([0.0, 0.25, 0.0]) - over) * float(np.clip(k, 0, 1))
    if ph == "release":                             # 垂直下放
        k = (u - P.ATTACH_AT - P.SPANS[1]) / P.SPANS[2]
        hi = land_hand + np.array([0.0, 0.25, 0.0])
        return hi + (land_hand - hi) * float(np.clip(k, 0, 1))
    k = (u - P.ATTACH_AT - P.SPANS[1] - P.SPANS[2]) / P.SPANS[3]
    return land_hand + (np.array([0.24, 1.02, 0.0]) - land_hand) * float(np.clip(k, 0, 1))

def case_B9():
    """放下杯子：手移到桌面→张开手指(detach)→杯留在桌面→不穿透桌面

    依据: UE5 程序化拾取——放下补偿 pivot→bounds 偏移，底面中心贴台面(prop.py)
    """
    from motion.character import prop as P
    from motion.character.crouch import WRIST_TO_GRIP
    FPS = 60.0
    surf = 1.05
    cup = P.Prop("cup", size=(0.08, 0.10, 0.08), grip="right", pivot=(0.0, surf + 0.25, 1.20))
    cup.attach()
    G0 = _grip_hand(cup)
    rel = np.asarray(cup.pivot, float) - G0
    land = np.array([0.15, surf, 1.15])
    land_hand = land - rel                           # 落点对应的手位（保证 detach 无跳变）
    ho = P.Handoff(cup)
    N = int(1.4 * FPS)
    hands, cens, owners = [], [], []
    for i in range(N):
        u = i / (N - 1)
        hand = np.asarray(_b9_hand(u, G0, land_hand), float)
        ho.advance(u)
        cup.pivot = (hand + rel) if cup.owner.startswith("hand") else land
        hands.append(hand.copy())
        cens.append(np.asarray(cup.center(), float).copy())
        owners.append(cup.owner)
    ys = [c[1] - 0.5 * cup.size[1] for c in cens]    # 杯底高度
    below = max(0.0, surf - min(ys))
    pen = [(float(np.linalg.norm(h - c)), WRIST_TO_GRIP, 0.5 * cup.size[0])
           for h, c in zip(hands, cens)]
    return [
        ("penetration_m", H.penetration_m(pen)),
        ("frame_jump_ratio", H.frame_jump_ratio(
            [float(np.linalg.norm(cens[i + 1] - cens[i]))
             for i in range(len(cens) - 1) if owners[i].startswith("hand")])),
    ], {"穿透台面_m": round(below, 6),
        "落定杯底高_m": round(ys[-1], 4),
        "末帧手物距_m": round(float(np.linalg.norm(hands[-1] - cens[-1])), 4),
        "末帧owner": owners[-1]}
