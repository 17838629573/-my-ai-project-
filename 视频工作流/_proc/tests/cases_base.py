#   契约: A 组（走跑跳转踢蹲）与 B 组（抓放道具）用例体。
#   完整契约见 tests/__init__.py
#   依据: 用例体与驱动分离，避免 run_all 单文件超纲（R2 >500）；
#         拆出后每层各自 <500 行，判据与实现同处一文件便于核对。
# -*- coding: utf-8 -*-
from .common import *          # noqa: F401,F403  常量
from .common import _world, _align_n   # 下划线名不随 * 导出，必须显式
from base.metrics import foot_skate_ratio

def _a1_leg_skates(W, N):
    """按腿分段量滑步峰值：跨换脚比较位移会把"换脚"误判成跳变

    注：原实现另算了每腿的 frame_jump_ratio(jumps) 但从未使用（死变量），
    拆分时删除，不影响任何判据。
    """
    skates = []
    for side, lo, hi in (("l", 0.0, 0.5), ("r", 0.5, 1.0)):
        seg = []
        for i in range(N):
            ph = i / N
            if not (lo <= ph < hi):
                continue
            f = W[i]["heel_" + side]
            seg.append((f[0], f[2], f[1]))
        m, mx = H.skate_cm_frame(seg)
        skates.append(mx)
    return skates


def _a1_skate_ratio(W, N):
    """打滑帧占比：业界按 ratio 报告（Motion Toolbox good<0.40），与峰值互补。

    左右腿支撑相不同，不能合成一个帧级接触序列——必须逐腿算再合并计数。
    up_axis=1：_world 输出 (x=前进, h=高度, z=侧向)，竖直轴是 index 1
    """
    nc_t, ns_t = 0, 0
    for side, lo, hi in (("l", 0.0, 0.5), ("r", 0.5, 1.0)):
        cs = [(lo <= i / N < hi) for i in range(N)]
        _r, _nc, _ns = foot_skate_ratio(
            W, ["heel_" + side], contact_seq=cs, thresh_m=0.01, up_axis=1)
        nc_t += _nc
        ns_t += _ns
    return ((ns_t / float(nc_t)) if nc_t else None), nc_t, ns_t


def _a1_lowests(W):
    """每帧最低关节高度序列（判浮空用）。"""
    return [min(v[1] for v in w.values()) for w in W]


def _a1_pelvis_disp(W):
    """骨盆逐帧前向位移绝对值序列（判时间连续性用）。"""
    return [abs(W[i + 1]["pelvis"][0] - W[i]["pelvis"][0])
            for i in range(len(W) - 1)]


def case_A1():
    """直线行走：滑步 / 浮空 / 双脚互穿 / 时间连续性"""
    from motion.character.body.gait import gait
    N = 48
    RAW = [gait(i / N) for i in range(N)]
    # 地面基准: 整个周期里最低关节的 v（脚跟着地点）
    GROUND_V = min(float(a[1]) for J in RAW for a in J.values())
    W = [_world(RAW[i], i / N, GROUND_V) for i in range(N)]

    # 按腿分段：左腿支撑 ph∈[0,0.5)，右腿 ph∈[0.5,1)
    # 跨换脚比较位移会把"换脚"误判成跳变
    lows = _a1_lowests(W)
    # 取最坏腿的峰值，不取均值：均值会被多数好帧稀释，掩盖最坏帧。
    # 原写法 mean/max 两个变量都取 max，名不副实（mean 实为 peak）——统一命名。
    skate_peak = max(_a1_leg_skates(W, N))
    disp = _a1_pelvis_disp(W)

    # 双脚水平距离（x=前进, z=侧向），两维都要，不能只取一维
    fa = [(w["heel_l"][0], w["heel_l"][2]) for w in W]
    fb = [(w["heel_r"][0], w["heel_r"][2]) for w in W]

    skate_ratio, nc_t, ns_t = _a1_skate_ratio(W, N)

    return [
        ("skate_cm_frame", skate_peak),
        ("foot_skate_ratio", 1.0 if skate_ratio is None else skate_ratio),
        ("float_m", H.float_m(lows)),
        ("feet_clip_m", H.feet_clip_m(fa, fb)),
        ("frame_jump_ratio", H.frame_jump_ratio(disp)),
    ], {"帧数": N, "周期行程_m": CYCLE, "skate_max_cm": round(skate_peak, 4),
         "最坏帧最低关节_m": round(max(lows), 4),
         "打滑帧占比": (None if skate_ratio is None else round(skate_ratio, 4)),
         "接触帧数": nc_t, "打滑帧数": ns_t}



def _A2_collect(RAW, BRAW, NR, SPS):
    """跑段 + 制动段并轨采样：地面余隙 / 水平位置 / 接触标志 / 髋高。"""
    from motion.character import run as R
    g0 = R.GROUND_V                        # 脚底基准=最低关节触地高度，非踝高
    lows, pxs, contact, hips = [], [], [], []
    for i, J in enumerate(RAW):
        lows.append(min(a[1] for a in J.values()) - g0)
        pxs.append(J["pelvis"][0] * H_M)
        contact.append(((i / SPS) % 0.5) < R.DUTY_RUN)
        hips.append(J["pelvis"][1])
    for Jd in BRAW:
        J = Jd["J"]
        lows.append(min(a[1] for a in J.values()) - g0)
        pxs.append(J["pelvis"][0] * H_M)
        # 制动段仍有腾空帧，接触不能一律置 True，否则把正常腾空判成漂浮
        ph = Jd.get("ph", 0.0)
        contact.append((ph < R.BETA) or (0.5 <= ph < 0.5 + R.BETA))
        hips.append(J["pelvis"][1])
    return lows, pxs, contact, hips


def _A2_flight_windows(contact, NR):
    """腾空窗口：把连续的非接触帧分组（只取跑段）。"""
    wins, cur = [], []
    for i in range(NR):
        if not contact[i]:
            cur.append(i)
        elif cur:
            wins.append(cur); cur = []
    if cur:
        wins.append(cur)
    return wins


def _A2_apex(wins, hips, dt):
    """最大腾空升高及其腾空时长（用于抛体解析对照）。"""
    rise, tf = 0.0, 0.0
    for w in wins:
        r = (max(hips[i] for i in w) - hips[w[0]]) * H_M
        if r > rise:
            rise, tf = r, len(w) * dt
    return rise, tf


def case_A2():
    """跑步急停：跑 2 个完整步周期 → 匀减速急停至 0

    依据: 占空比 β=0.35（Novacheck 1998），腾空占比 1-2β；
    腾空顶点升高 = g·T_F²/8（抛体解析）；急停匀减速 a=v0²/2D，
    D=2.39m 取 5m sprint-to-stop 制动距离（Graham-Smith）
    """
    from motion.character import run as R
    SPS = 200
    dt = R.T_STRIDE / SPS
    NR = 2 * SPS
    NB = int(round(R.T_BRAKE / dt)) + 1
    RAW = [R.run((i / SPS) % 1.0) for i in range(NR)]
    BRAW = [R.brake(i * dt) for i in range(NB)]
    lows, pxs, contact, hips = _A2_collect(RAW, BRAW, NR, SPS)
    hgt = [v * H_M for v in lows]
    wins = _A2_flight_windows(contact, NR)
    rise, tf = _A2_apex(wins, hips, dt)
    disp = [abs(pxs[i + 1] - pxs[i]) for i in range(len(pxs) - 1)]
    return [
        ("ground_penetration_m", H.ground_penetration_m(hgt)),
        ("contact_float_m", H.contact_float_m(hgt, contact)),
        ("flight_apex_err", H.flight_apex_err(rise, tf)),
        ("frame_jump_ratio", H.frame_jump_ratio(disp)),
    ], {"跑帧数": NR, "急停帧数": NB, "跑速_mps": R.V_RUN,
         "步周期_s": round(R.T_STRIDE, 4),
         "腾空时长_s": round(R.T_FLIGHT, 4),
         "实测升高_m": round(rise, 5),
         "理论升高_m": round(9.80665 * R.T_FLIGHT ** 2 / 8, 5),
         "制动距离_m": round(BRAW[-1]["d"], 3)}


def _a3_states(hips, air, dt):
    """腾空段逐帧状态：中点差分求速度，供机械能守恒判定"""
    st = []
    for k in range(1, len(air) - 1):
        i = air[k]
        v = (hips[air[k + 1]] - hips[air[k - 1]]) / (2 * dt)
        st.append((1.0, (0.0, v), hips[i]))
    return st


def _a3_air_metrics(hips, air, N):
    """腾空升高（起跳帧→顶点）与逐帧髋部位移"""
    apex = max(hips[i] for i in air) - hips[air[0]]
    disp = [abs(hips[i + 1] - hips[i]) for i in range(N - 1)]
    return apex, disp


def case_A3():
    """原地跳跃：下蹲→蹬伸→腾空（严格抛物线）→落地缓冲→回升

    依据: 腾空段机械能守恒（ΔE≤0）；顶点升高 = g·T_F²/8
    """
    from motion.character import jump as Jm
    FPS = 60.0
    # 采样栅格必须让相位边界落在整数帧上, 否则首帧已离地 τ>0,
    # 顶点升高会被系统性低估(实测曾虚高 6.9%), 属离散化误差非物理错误
    N = _align_n(Jm.T_TOTAL, [Jm.T_CROUCH + Jm.T_PUSH,
                              Jm.T_CROUCH + Jm.T_PUSH + Jm.FT], FPS)
    tn = [i / (N - 1) for i in range(N)]
    ts = [t * Jm.T_TOTAL for t in tn]
    RAW = [Jm.jump(t) for t in tn]
    g0 = Jm.ANK_N                             # 地面基准=踝（腾空绷脚尖会低于它）
    f0 = (Jm.T_CROUCH + Jm.T_PUSH) / Jm.T_TOTAL
    f1 = (Jm.T_CROUCH + Jm.T_PUSH + Jm.FT) / Jm.T_TOTAL
    flight = [f0 <= t < f1 for t in tn]
    hgt = [(min(a[1] for a in Jd.values()) - g0) * H_M for Jd in RAW]
    hips = [Jd["pelvis"][1] * H_M for Jd in RAW]
    dt = Jm.T_TOTAL / (N - 1)
    air = [i for i in range(N) if flight[i]]
    st = _a3_states(hips, air, dt)
    apex, disp = _a3_air_metrics(hips, air, N)       # apex: 起跳帧→顶点
    return [
        ("contact_float_m", H.contact_float_m(hgt, [not f for f in flight])),
        ("flight_apex_err", H.flight_apex_err(apex, Jm.FT)),
        ("flight_g_err", H.flight_g_err([ts[i] - ts[air[0]] for i in air],
                                        [hips[i] for i in air])),
        ("energy_gain", H.energy_gain(st)),
        ("frame_jump_ratio", H.frame_jump_ratio(disp)),
    ], {"腾空帧数": len(air), "最高离地_m": round(max(hgt), 4),
         "实测升高_m": round(apex, 5),
         "理论升高_m": round(9.80665 * Jm.FT ** 2 / 8, 5)}


def _a7_obj_at(C, q, obj, carry):
    """抓稳后物体跟随肩（肩→物方向固定、距离恒定）；未抓稳时停在原位"""
    if carry is None:
        return obj
    sh = np.array(C.crouch(q, with_arms=False)["chest"][:2])
    sh[1] -= 0.02
    return list(sh + carry[0] * carry[1])


def _a7_grasp(C, Jd, obj, arm, k, n1, n2, carry):
    """伸手末帧建立抓握：记下肩→物单位方向与距离，之后恒持"""
    if carry is not None or arm < 1.0 or k < n1 + n2 - 1:
        return carry
    sh = np.array(Jd["sh_r"][:2])
    d = np.array(obj) - sh
    L0 = float(np.linalg.norm(d))
    return (d / L0, L0)


def _a7_hgt(RAW):
    """以全程最低关节为基准的高度序列"""
    g0 = min(min(a[1] for a in Jd.values()) for Jd in RAW)
    return [(min(a[1] for a in Jd.values()) - g0) * H_M for Jd in RAW]


def _a7_scan(C, seq, RAW, objs):
    """逐帧量手物穿透；臂展只在伸手/持物帧量（站立时物体在地≠拉长手臂）"""
    pen, reach = [], []
    for (q, arm), Jd, ob in zip(seq, RAW, objs):
        w = np.array(Jd["wri_r"][:2])
        pen.append((float(np.linalg.norm(w - np.array(ob))),
                    C.WRIST_TO_GRIP, C.OBJ_R_N))
        if arm >= 1.0:
            reach.append(H.arm_reach(np.array(Jd["sh_r"][:2]) * H_M,
                                     np.array(ob) * H_M, H_M))
    return pen, reach


def case_A7():
    """下蹲捡物：蹲下→伸手接触地面物体→拿起到手中→站起（物体随手上升）

    依据: 抓握点 = 物体表面（手心到物体中心 = 物体半径 + 腕到抓握点）；
    站起段物体跟随手，不得把手臂拉长去够留在地上的物体
    """
    import math
    from motion.character import crouch as C
    FPS = 60.0
    n1, n2, n3 = int(0.5 * FPS), int(0.25 * FPS), int(0.5 * FPS)
    seq = ([(i / n1, 0.0) for i in range(n1)]
           + [(1.0, i / n2) for i in range(n2)]
           + [(1.0 - i / n3, 1.0) for i in range(n3)])
    obj = [C.OBJ_U, C.OBJ_V]
    RAW, objs = [], []
    carry = None                               # 抓稳后：肩→物方向固定，距离恒定
    for k, (q, arm) in enumerate(seq):
        obj = _a7_obj_at(C, q, obj, carry)
        Jd = C.reach_pose(q, obj[0], obj[1], C.OBJ_R_N, arm=arm)
        RAW.append(Jd)
        objs.append(tuple(obj))
        carry = _a7_grasp(C, Jd, obj, arm, k, n1, n2, carry)
    hgt = _a7_hgt(RAW)
    pen, reach = _a7_scan(C, seq, RAW, objs)
    heel = [(Jd["heel_l"][0] * H_M, Jd["heel_l"][2] * H_M, 0.0) for Jd in RAW]
    skate_mean, skate_max = H.skate_cm_frame(heel, fps=FPS)
    return [
        ("float_m", H.float_m(hgt)),
        ("penetration_m", H.penetration_m(pen)),
        ("skate_cm_frame", skate_mean),
        ("arm_reach", max(reach)),
    ], {"物体初始高_m": round(C.OBJ_V * H_M, 4),
         "物体终止高_m": round(objs[-1][1] * H_M, 4),
         "最小手物距_m": round(min(p[0] for p in pen), 4),
         "臂展峰值": round(max(reach), 4)}


def case_A4():
    """转身180：头-躯干-脚顺序自然，无瞬间翻转

    顺序依据: 骨盆优先 → 脊柱逐节延迟 → 头部最后跟上（头比肩晚 8~12 帧）
    """
    from motion.character.turn import (turn_yaw, turn_stance, turn_torso,
                                       turn_duration)
    N = 96
    dur = turn_duration(180.0)                 # 180° 转身耗时（秒）
    ys = [turn_yaw(0.0, 180.0, i / (N - 1)) for i in range(N)]
    d = [abs(ys[i + 1] - ys[i]) for i in range(N - 1)]
    # 顺序：头部滞后 > 躯干滞后，且中途最大、首尾回正
    seq = []
    for i in range(N):
        t, h = turn_torso(None, i / (N - 1), 180.0)
        seq.append((t, h))
    lag_ok = max(s[1] for s in seq) > max(s[0] for s in seq)   # 头 > 躯干
    # 支撑脚不滑：转身换步期间，抬起侧之外的那只脚位移应为 0
    stance = [turn_stance(i / (N - 1)) for i in range(N)]
    both = [1 for ll, lr, _c in stance if ll > 1e-9 and lr > 1e-9]
    # 端点
    end_ok = abs(ys[-1] - 180.0) < 1e-9
    max_step = max(d)
    return [
        ("frame_jump_ratio", H.frame_jump_ratio(d)),
        ("peak_rate_dps", H.peak_rate_dps([x / (dur / (N - 1)) for x in d])),
    ], {"转身耗时_s": round(dur, 3), "单帧最大转角": round(max_step, 3),
        "峰值角速度_dps": round(max(d) / (dur / (N - 1)), 1),
        "头滞后>躯干": bool(lag_ok), "双脚同时抬起帧数": len(both),
        "终点到位": bool(end_ok)}


def case_A5():
    """挥手：抬右臂 → 掌摆动，肩肘腕联动，肘不反折、臂不超伸"""
    from motion.character.gesture import wave
    N = 96
    W = [wave(i / (N - 1))["J"] for i in range(N)]
    # 摆动幅度：腕 > 肘 > 肩（末端最大）—— 联动的定量表达
    amp = {k: max(w[k][2] for w in W) - min(w[k][2] for w in W) for k in W[0]}
    # 抬起幅度：腕 > 肘 > 肩
    up = {k: max(w[k][1] for w in W) - min(w[k][1] for w in W) for k in W[0]}
    order_sw = amp["wri_r"] > amp["elb_r"] > amp["sh_r"]
    order_up = up["wri_r"] > up["elb_r"] > up["sh_r"]
    # 连续性：逐帧位移不得突变
    d = [abs(W[i + 1]["wri_r"][2] - W[i]["wri_r"][2]) for i in range(N - 1)]
    # 肘不反折：肘的位移方向必须与肩腕同侧（不得反向）
    reflex = min(W[i]["elb_r"][1] * W[i]["wri_r"][1] for i in range(N))
    return [
        ("frame_jump_ratio", H.frame_jump_ratio(d)),
    ], {"摆动幅度 腕/肘/肩": [round(amp["wri_r"], 4), round(amp["elb_r"], 4),
                          round(amp["sh_r"], 4)],
        "抬起幅度 腕/肘/肩": [round(up["wri_r"], 4), round(up["elb_r"], 4),
                          round(up["sh_r"], 4)],
        "摆动腕>肘>肩": bool(order_sw), "抬起腕>肘>肩": bool(order_up),
        "肘同向(最小积)": round(float(reflex), 6)}


def case_A6():
    """踢球：抬腿踢中球 → 球飞出；接触为接触非穿透、动量守恒、支撑脚不浮空

    依据: 触球点取踝前移 0.045m 的脚背(Bull-Andersen 1999 冲击点在踝与趾之间);
    恢复系数 0.572 取 0.463~0.681 中值; 有效击球质量 = 足质量/打击效率
    """
    from motion.character import kick as K
    fps = 60.0
    N = _align_n(K.T_TOTAL, [K.F_IMPACT], fps)
    ts = [i / (N - 1) for i in range(N)]
    W = [K.kick(t) for t in ts]
    lows = [min(v[1] for v in w.values()) * H_M for w in W]
    pairs = []
    for t in ts:
        c = K.contact_point(t)          # 米
        b = K.ball_center(t)            # 米
        pairs.append((float(np.linalg.norm(b - c)), 0.0, K.ball.R_BALL))
    vf = K.foot_vel(K.F_IMPACT)
    n = vf / np.linalg.norm(vf)
    m_eff = K.ball.strike_mass()
    vfa, vb = K.ball.impact(vf, n)
    return [
        ("penetration_m", H.penetration_m(pairs)),
        ("momentum_err", H.momentum_err([(m_eff, vf)],
                                        [(m_eff, vfa), (K.ball.M_BALL, vb)])),
        ("float_m", H.float_m(lows)),
    ], {"帧数": N, "触球速度_m/s": round(float(np.linalg.norm(vf)), 3),
        "球出速_m/s": round(float(np.linalg.norm(vb)), 3),
        "有效击球质量_kg": round(float(m_eff), 3),
        "最坏帧最低关节_m": round(float(max(lows)), 4)}





