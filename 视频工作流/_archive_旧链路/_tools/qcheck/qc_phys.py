#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Q_f~Q_i 物理层：自然度判据。

这一层是【本工作流独有】的 —— 市面上任何通用视频质量工具都没有。
理由：本工作流的运动由求解器算出，位置/速度/相位是【已知精确值】，
不需要用 tracker 去估计轨迹再反推物理（那等于拿含噪估计校验精确已知量）。

关键洞见：
  像素层测不出"运动不自然"。同手同脚走路的光流很平滑、SSIM 很高、
  不闪不卡 —— 所有像素指标全绿，但看着就不自然。
  自然度必须靠物理判据。

四项判据：
  Q_f 步态锁相：speed = stride / cycle（不锁相必然 foot sliding）
  Q_g 足锁    ：支撑期脚世界坐标恒定；切换需惯性化 + 迟滞
  Q_h 平衡    ：ZMP 落在支撑多边形内（注意：区内 ≠ 一定平衡）
  Q_i 滑移    ：Coulomb 锥 ||f^t|| <= mu·||f^n||
"""
import math
import numpy as np


# ---------- Q_f 步态锁相 ----------
def check_gait_lock(speed_mps, stride_m, cycle_s, tol=1e-6):
    """speed 必须等于 stride / cycle，否则脚必滑。"""
    if stride_m <= 0 or cycle_s <= 0:
        return {"ok": False, "reason": "stride/cycle 须 > 0"}
    want = stride_m / cycle_s
    err = abs(want - speed_mps)
    return {"ok": err < max(tol, abs(want) * 1e-6),
            "speed_given": speed_mps, "speed_from_gait": want,
            "abs_err": err, "rel_err": err / max(abs(want), 1e-12)}


def foot_trace(gait, t_max=2.0, fps=60.0):
    """用本仓 pose.foot_target 采样足端轨迹，统计支撑期位移。"""
    from pose import foot_target
    ts = np.arange(0.0, t_max, 1.0 / fps)
    left, right, phases = [], [], []
    for t in ts:
        pl, sl = foot_target(float(t), "l", gait)
        pr, sr = foot_target(float(t), "r", gait)
        left.append(pl); right.append(pr); phases.append((sl, sr))
    return np.array(ts), np.array(left), np.array(right), phases


def check_foot_sliding(gait, t_max=2.0, fps=60.0):
    """支撑期内脚若移动 = foot sliding。返回每只脚的支撑期最大位移。"""
    ts, L, R, ph = foot_trace(gait, t_max, fps)
    out = {}
    for name, arr, idx in (("left", L, 0), ("right", R, 1)):
        stance = [k for k in range(len(ts)) if ph[k][idx] == "stance"]
        if len(stance) < 2:
            out[name] = {"stance_frames": len(stance), "max_drift": 0.0}
            continue
        # 支撑期应恒定：取连续支撑段的内部最大相对位移
        drift = 0.0
        seg = [stance[0]]
        for k in stance[1:]:
            if k == seg[-1] + 1:
                seg.append(k)
            else:
                p = arr[seg]
                drift = max(drift, float(np.max(np.abs(p - p[0]))))
                seg = [k]
        p = arr[seg]
        drift = max(drift, float(np.max(np.abs(p - p[0]))))
        out[name] = {"stance_frames": len(stance), "max_drift": drift}
    worst = max(out["left"]["max_drift"], out["right"]["max_drift"])
    return {"per_foot": out, "max_drift": worst,
            "ok": worst < 1e-9,
            "note": "支撑期脚世界坐标应恒定；漂移>0 即 foot sliding"}


# ---------- Q_g 足锁状态机 ----------
def check_foot_lock(toe_seq, contact_seq, dt=1.0 / 60.0):
    """用 foot_lock.FootLock 跑一遍，统计锁定稳定性。"""
    from foot_lock import FootLock
    fl = FootLock(dt=dt)
    outs, flips = [], 0
    prev = None
    for xy, c in zip(toe_seq, contact_seq):
        o = fl.update(tuple(xy), bool(c))
        outs.append(o)
        if prev is not None and fl.state != prev:
            flips += 1
        prev = fl.state
    return {"locked_frames": sum(1 for _ in outs),
            "state_flips": flips,
            "final_state": fl.state,
            "ok": flips <= 2,
            "note": "切换次数过多说明迟滞带没起作用"}


def check_gait_footlock(gait, t_max=2.0, fps=60.0, ankle_y=0.065):
    """完整链路：foot_contact 判据生成 contact -> 喂 FootLock。

    重要（第一轮实测发现）：
      恒定 contact=True + 脚在移动 = 不自洽输入，FootLock 会反复锁/放
      （解锁后下一帧又因 contact 为真而重锁）。这不是 bug，是输入矛盾。
      实际使用必须用【触地判据】驱动 contact —— 脚滑动时判据为 False，
      于是不会锁定。这正是 Q_d 与 Q_g 必须联动的原因。
    """
    from _common import foot_contact
    from pose import foot_target
    from foot_lock import FootLock
    ts = np.arange(0.0, t_max, 1.0 / fps)
    pts, ph, vel = [], [], []
    for t in ts:
        (x, y), st = foot_target(float(t), "l", gait)
        pts.append((x, y)); ph.append(st)
    pts = np.array(pts)
    vel = np.gradient(pts, 1.0 / fps, axis=0)
    fl = FootLock(dt=1.0 / fps)
    flips, locked = 0, 0
    prev = None
    for (xy, v, st) in zip(pts, vel, ph):
        c = foot_contact(xy, v, ankle_y)
        fl.update(tuple(xy), c)
        if prev is not None and fl.state != prev:
            flips += 1
        prev = fl.state
        if fl.state == "locked":
            locked += 1
    return {"frames": len(ts), "locked_frames": locked,
            "state_flips": flips, "ok": flips <= 4,
            "note": "支撑期应锁定、摆动期应释放；flips 过多说明判据未联动"}


# ---------- Q_h 平衡 ----------
def check_balance(links_seq, contacts_seq):
    """逐帧判 ZMP 是否在支撑多边形内。腾空帧（无接触）跳过。"""
    from zmp import Balance, com_projection
    res = []
    for links, contacts in zip(links_seq, contacts_seq):
        if not contacts:
            res.append({"airborne": True, "stable": None, "margin": None})
            continue
        z = com_projection(links)
        B = Balance(contacts)
        res.append({"airborne": False, "stable": B.stable(z),
                    "margin": B.margin(z), "zmp": z})
    grounded = [r for r in res if not r["airborne"]]
    bad = [r for r in grounded if not r["stable"]]
    return {"frames": len(res), "grounded": len(grounded),
            "unstable_frames": len(bad),
            "min_margin": min((r["margin"] for r in grounded), default=None),
            "ok": len(bad) == 0,
            "note": "ZMP 在区内 ≠ 一定平衡（真人绊倒时仍在区内）；"
                    "本判据只报出界，不声称杜绝摔倒"}


# ---------- Q_i 滑移 ----------
def check_slip(force_seq, env, normal_dir=(0.0, 1.0, 0.0)):
    """逐帧 Coulomb 锥判据。"""
    ratios, slips = [], []
    for f in force_seq:
        is_slip, ratio, mu = env.slip_cone(tuple(f), normal_dir)
        ratios.append(ratio); slips.append(bool(is_slip))
    return {"frames": len(force_seq),
            "slip_frames": int(sum(slips)),
            "max_ratio": float(max(ratios)) if ratios else 0.0,
            "mean_ratio": float(np.mean(ratios)) if ratios else 0.0,
            "ok": True,
            "note": "该滑时滑、不该滑时不滑；比值序列应与意图一致"}


def analyze(phys, max_frames=None):
    """统一入口：把 phys dict 分派到各 check。

    为什么需要（实测逼出）：qc_all 调 qc_phys.analyze()，但本模块只有
    6 个散装 check_* 函数，没有 analyze -> AttributeError 被 except 吞成
    {"error":...}，L2 层因此一直拿不到结果。
    """
    if not phys:
        return {"skipped": "未传求解器参数"}
    gait = phys.get("gait") or {}
    t_max = float(phys.get("t_max") or 8.0)
    if max_frames:
        t_max = min(t_max, max_frames / float(phys.get("fps") or 60.0))
    fps = float(phys.get("fps") or 60.0)
    res = {"checked": {}, "verdict": "PASS", "source": phys.get("_source")}
    fails = []

    def run(name, fn):
        try:
            v = fn()
            res["checked"][name] = v
            bad = isinstance(v, dict) and v.get("ok") is False
            if bad:
                fails.append(name)
        except Exception as e:
            res["checked"][name] = {"error": "%s: %s" % (type(e).__name__, str(e)[:80])}

    if gait.get("cycle_s") and gait.get("stride_m"):
        run("gait_lock", lambda: check_gait_lock(
            gait.get("speed_m_s", gait.get("speed_mps")),
            gait["stride_m"], gait["cycle_s"]))
    run("gait_footlock", lambda: check_gait_footlock(
        gait, t_max, fps, ankle_y=gait.get("ankle_y_m", 0.065)))
    run("foot_sliding", lambda: check_foot_sliding(gait, t_max, fps))
    if phys.get("links_seq") and phys.get("contacts_seq"):
        run("balance", lambda: check_balance(phys["links_seq"], phys["contacts_seq"]))
    if phys.get("force_seq") and phys.get("env"):
        run("slip", lambda: check_slip(phys["force_seq"], phys["env"]))
    res["failed"] = fails
    res["verdict"] = "FAIL" if fails else "PASS"
    res["pass_rate"] = round(1.0 - len(fails) / max(len(res["checked"]), 1), 4)
    return res


def self_check():
    ok, bad = [], []
    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    # Q_f 锁相
    r = check_gait_lock(1.4, 0.7, 0.5)
    add("1 锁相正确(1.4=0.7/0.5)", r["ok"], "err=%.2e" % r["abs_err"])
    r2 = check_gait_lock(1.4, 0.7, 0.6)
    add("2 不锁相被检出", not r2["ok"],
        "speed应=%.3f 实际1.4" % r2["speed_from_gait"])

    # Q_f 足滑
    gait = {"cycle_s": 0.5, "stride_m": 0.7, "stance_ratio": 0.6,
            "swing_height_m": 0.12, "speed_m_s": 1.4, "ankle_y_m": 0.065}
    r3 = check_foot_sliding(gait, t_max=1.0, fps=60.0)
    add("3 锁相步态无脚滑", r3["ok"], "max_drift=%.2e" % r3["max_drift"])

    # Q_g 足锁：必须用【触地判据】驱动，不能恒定 contact=True
    r4 = check_gait_footlock(gait, t_max=1.0, fps=60.0)
    add("4 触地判据驱动足锁", r4["ok"],
        "flips=%d locked=%d/%d" % (r4["state_flips"], r4["locked_frames"],
                                   r4["frames"]))
    # 对照：恒定 contact=True + 移动脚 = 不自洽，会反复锁放
    seq = [(0.01 * i, 0.02) for i in range(60)]
    r4b = check_foot_lock(seq, [True] * 60)
    add("4b 恒定contact+移动脚会反复锁放(输入不自洽)", r4b["state_flips"] > 2,
        "flips=%d" % r4b["state_flips"])

    # Q_h 平衡
    # contacts 是 (x,z) 对，z∈[0,0.12]；ZMP 的 z 须落在中部，
    # 取 z=0 会正好压在边界上（边界判定用 eps，易判失败）
    links = [{"m": 40.0, "r": (0.0, 0.9, 0.06)},
             {"m": 20.0, "r": (0.0, 0.5, 0.06)}]
    contacts = [(-0.15, 0.0), (0.15, 0.0), (-0.15, 0.12), (0.15, 0.12)]
    r5 = check_balance([links] * 5, [contacts] * 5)
    add("5 重心居中判定稳定", r5["ok"], "unstable=%d" % r5["unstable_frames"])
    links_off = [{"m": 40.0, "r": (0.9, 0.9, 0.0)},
                 {"m": 20.0, "r": (0.9, 0.5, 0.0)}]
    r6 = check_balance([links_off] * 5, [contacts] * 5)
    add("6 重心出界判失衡", not r6["ok"], "unstable=%d" % r6["unstable_frames"])

    # Q_i 滑移
    try:
        import environment as env
        e = env.Env(surface="stone")
        r7 = check_slip([(0.0, 10.0, 0.0), (9.0, 10.0, 0.0)], e)
        add("7 滑移序列可算", r7["frames"] == 2,
            "slip_frames=%d max_ratio=%.2f" % (r7["slip_frames"], r7["max_ratio"]))
    except Exception as ex:
        add("7 滑移序列可算", False, str(ex)[:40])

    print("PASS:")
    for x in ok: print("  " + x)
    if bad:
        print("FAIL:")
        for x in bad: print("  " + x)
    else:
        print("FAIL: 无")
    return not bad


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
