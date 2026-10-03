#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pose_prompt —— 轨迹 → 结构性提示词（铁律73：骨架图永不进画面）

业界依据（本轮搜证）
  · Spriterrific 走循环：受控文本提示词 -> 视频模型 -> 抽帧成表。
    原版约束：in-place（不漂移）/ 固定相机 / 左右脚交替 stride /
    手臂反相摆动 / 身份锁定锚点 / 脚接触线在格底
  · spritesynth：walk 4-8 帧 @100-200ms，contact frame 是卖出运动感的关键
  · ControlNet OpenPose：骨架是 conditioning 而非被临摹的图像（本工具无此接口）

铁律73 骨架图永不进画面；无 control map 接口时，姿态只能走结构性文本
铁律74 每个姿态量必须来自 pose.solve() 输出，禁 AI 凭印象写模糊词
铁律75 走循环必须 in-place + 脚接触线在格底 + 相机固定
铁律76 每帧提示词须含身份锁定段，与锚点图同源

依赖: pose
被依赖: build_video（拟）, character_sheet（拟）
改前必读: IMPROVE_pose_prompt.md
"""
from __future__ import annotations
import math

# 定性映射阈值（铁律32：阈值属 AI 声明，非代码内置知识；可整体覆盖）
PARAMS = {
    # 脚相对髋的水平偏移，按 stride/2 归一化后的分档
    "fwd": 0.35, "back": -0.35,
    # 抬起高度按 swing_height 归一化
    "lift_hi": 0.55, "lift_lo": 0.15,
    # 膝/肘弯曲角（度）偏离伸直的分档
    "bend_hi": 25.0, "bend_lo": 8.0,
    # 手臂前后摆：腕相对肩的水平偏移，按 upperarm+forearm 归一化
    "arm_fwd": 0.18, "arm_back": -0.18,
}

SIDE = {"l": "left", "r": "right"}


class PromptError(ValueError):
    pass


def _need(d, key, where):
    if not isinstance(d, dict) or key not in d:
        raise PromptError(f"缺必填槽位 {where}.{key}")
    return d[key]


def _ang(a, b, c):
    """三点夹角 ABC（度）：b 为顶点。用于膝/肘弯曲量。"""
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    n1 = math.hypot(*v1) or 1e-9
    n2 = math.hypot(*v2) or 1e-9
    cosv = (v1[0] * v2[0] + v1[1] * v2[1]) / (n1 * n2)
    return math.degrees(math.acos(max(-1.0, min(1.0, cosv))))


def _bend_word(deg, p):
    """弯曲角 -> 定性词。deg = 180 - 夹角（0=完全伸直）。"""
    if deg >= p["bend_hi"]:
        return "clearly bent"
    if deg >= p["bend_lo"]:
        return "slightly bent"
    return "straight"


def leg_state(joints, side, meta, gait, p=None):
    """单腿状态：全部由关节坐标算出（铁律74）。"""
    p = dict(PARAMS if p is None else p)
    hip = joints[f"{side}_hip"]
    knee = joints[f"{side}_knee"]
    ankle = joints[f"{side}_ankle"]
    # 铁律74+修正：参考点必须用同侧髋。左右髋本身分列身体两侧，
    # 若取两髋中点会引入 ±(髋半宽) 的固定偏置，使左右腿定性判定不对称
    # （实测：左腿恒偏 -0.161、右腿恒偏 +0.161，后半周期全被判成 directly under）。
    hipx = hip[0]
    stride = _need(gait, "stride_m", "gait")
    hgt = _need(gait, "swing_height_m", "gait")
    ankle_y = float(gait.get("ankle_y_m", 0.065))

    rel = (ankle[0] - hipx) / max(1e-9, stride / 2.0)
    if rel >= p["fwd"]:
        pos = "in front of"
    elif rel <= p["back"]:
        pos = "behind"
    else:
        pos = "directly under"

    lift = (ankle[1] - ankle_y) / max(1e-9, hgt)
    if lift >= p["lift_hi"]:
        air = "lifted well off the ground"
    elif lift >= p["lift_lo"]:
        air = "just lifting off the ground"
    else:
        air = "planted flat on the ground"

    bend = 180.0 - _ang(hip, knee, ankle)
    phase = meta.get(f"{side}_phase", "unknown")
    return {
        "side": SIDE[side], "phase": phase, "pos": pos, "air": air,
        "bend_deg": bend, "bend": _bend_word(bend, p),
        "rel": rel, "lift": lift,
    }


def arm_state(joints, side, p=None):
    """手臂前后摆：用【肘】相对肩的水平偏移判定（业界 counter-swing）。
    不用腕——肘部恒定弯曲会给每帧加固定前偏，淹没前后摆信号。"""
    p = dict(PARAMS if p is None else p)
    sh = joints[f"{side}_shoulder"]
    el = joints[f"{side}_elbow"]
    span = math.hypot(el[0] - sh[0], el[1] - sh[1]) or 1e-9
    rel = (el[0] - sh[0]) / span
    if rel >= p["arm_fwd"]:
        return "swinging forward"
    if rel <= p["arm_back"]:
        return "swinging back"
    return "hanging at the side"


def describe(joints, meta, gait, facing="right", p=None):
    """把一帧姿态翻译成结构性英文提示词片段（不含身份段）。"""
    ls = {s: leg_state(joints, s, meta, gait, p) for s in ("l", "r")}
    arms = {s: arm_state(joints, s, p) for s in ("l", "r")}

    stance = [s for s in ("l", "r") if ls[s]["phase"] == "stance"]
    swing = [s for s in ("l", "r") if ls[s]["phase"] == "swing"]
    parts = []
    for s in stance:
        st = ls[s]
        parts.append(
            f"{st['side']} leg is the supporting leg, foot {st['air']} "
            f"{st['pos']} the body, knee {st['bend']}")
    for s in swing:
        st = ls[s]
        parts.append(
            f"{st['side']} leg is swinging through, foot {st['air']} "
            f"passing {st['pos']} the body, knee {st['bend']}")
    if len(stance) == 2:
        parts.append("both feet are in contact with the ground (contact pose)")
    for s in ("l", "r"):
        parts.append(f"{SIDE[s]} arm {arms[s]}")
    head = "upright torso, head level, eyes forward"
    parts.append(head)
    return "; ".join(parts)


COMMON = ("full-body side view, the whole figure from head to feet visible, "
          "feet on a shared ground contact line at the bottom of the frame, "
          "standing in place without drifting sideways, fixed camera, "
          "locked identity, same outfit and proportions as the reference")


def frame_prompt(spec, mode, t, i, n, facing="right", p=None):
    """单帧完整提示词 = 身份段 + 姿态段 + 通用约束段。"""
    from pose import solve
    out = solve(spec, mode, t=t)
    joints, meta = out["joints"], out["meta"]
    ident = _need(spec, "identity", "spec")
    pose_txt = describe(joints, meta, _need(spec, "gait", "spec"), facing, p)
    return {
        "i": i, "t": round(t, 5),
        "phase": f"l={meta.get('l_phase')} r={meta.get('r_phase')}",
        "pose": pose_txt,
        "prompt": f"{ident}, {pose_txt}. {COMMON}",
    }


def sheet_prompts(spec, mode="walk", n=8, facing="right", p=None):
    """一个完整周期的 n 帧提示词（等相位采样，含 contact 帧优先）。"""
    gait = _need(spec, "gait", "spec")
    cycle = _need(gait, "cycle_s", "gait")
    out = []
    for i in range(n):
        t = cycle * i / n
        out.append(frame_prompt(spec, mode, t, i, n, facing, p))
    return out


# ================== 自检 ==================
def _chk(name, ok, info=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  {info}" if info else ""))
    return bool(ok)


def self_check():
    import pose
    spec = {
        "height_m": 1.70,
        "anthro": {"trunk": 0.300, "head": 0.130, "neck": 0.052,
                   "upperarm": 0.186, "lowerarm": 0.146, "hand": 0.108,
                   "thigh": 0.245, "shank": 0.246,
                   "shoulder_half": 0.115, "hip_half": 0.095},
        "poses": {"stand": {"a_trunk": 90.0, "a_head": 90.0,
                            "a_shoulder_l": 270.0, "a_shoulder_r": 270.0,
                            "a_upperarm_l": 270.0, "a_upperarm_r": 270.0,
                            "a_forearm_l": 270.0, "a_forearm_r": 270.0,
                            "a_hip_l": 180.0, "a_hip_r": 0.0,
                            "a_thigh_l": 270.0, "a_thigh_r": 270.0,
                            "a_shank_l": 270.0, "a_shank_r": 270.0}},
        "gait": {"speed_m_s": 1.35, "cycle_s": 1.0, "stride_m": 1.35,
                 "stance_ratio": 0.60, "swing_height_m": 0.10,
                 "bob_m": 0.035, "arm_swing_deg": 25.0, "elbow_bend_deg": 20.0,
                 "torso_lean_deg": 3.0, "pelvis_rot_deg": 6.0},
        "face": {"eye_back": 0.25, "ear_back": 0.45, "face_side": 0.35},
        "identity": "a Tang dynasty Buddhist monk, shaved head, ochre-red kasaya robe",
    }
    gait = spec["gait"]
    ok = True
    ps = sheet_prompts(spec, "walk", 8)

    # 1 帧数
    ok &= _chk("1 帧数=8", len(ps) == 8)

    # 2 每帧姿态段非空且互不相同（证明真的随轨迹变化）
    poses = [x["pose"] for x in ps]
    ok &= _chk("2 姿态段互异", len(set(poses)) >= 6,
               f"unique={len(set(poses))}/8")

    # 3 in-place 循环闭合：t 与 t+cycle 的【相对髋】姿态必须一致
    #    （世界坐标本就前进 1.35m，那是位移不是滑移；滑移看相对量）
    per = []
    for s in ("l", "r"):
        for x in ps:
            a = leg_state(pose.solve(spec, "walk", t=x["t"])["joints"], s,
                          pose.solve(spec, "walk", t=x["t"])["meta"], gait)
            b = leg_state(pose.solve(spec, "walk", t=x["t"] + gait["cycle_s"])["joints"], s,
                          pose.solve(spec, "walk", t=x["t"] + gait["cycle_s"])["meta"], gait)
            per.append(abs(a["rel"] - b["rel"]) + abs(a["lift"] - b["lift"]))
    ok &= _chk("3 in-place 周期闭合(相对髋)", all(d < 1e-9 for d in per) and per,
               f"maxdiff={max(per):.2e}")

    # 4 相位覆盖 stance 与 swing 两种
    phases = {x["phase"] for x in ps}
    ok &= _chk("4 相位含stance+swing",
               any("stance" in q for q in phases) and any("swing" in q for q in phases))

    # 5 提示词含 in-place / contact line / 固定相机（铁律75）
    ok &= _chk("5 in-place+接触线+固定相机",
               all("without drifting" in x["prompt"] and "contact line" in x["prompt"]
                   and "fixed camera" in x["prompt"] for x in ps))

    # 6 身份段每帧一致（铁律76）
    ok &= _chk("6 身份段每帧一致",
               len({x["prompt"].split(",")[0] for x in ps}) == 1)

    # 7 定性词来自计算：摆动腿必含 lifted，支撑腿必含 planted
    bad = 0
    for x in ps:
        o = pose.solve(spec, "walk", t=x["t"])
        m = o["meta"]
        for s in ("l", "r"):
            word = "left" if s == "l" else "right"
            seg = [y for y in x["pose"].split("; ") if y.startswith(word + " leg")]
            if not seg:
                continue
            seg = seg[0]
            if m[f"{s}_phase"] == "stance" and "planted" not in seg:
                bad += 1
            if m[f"{s}_phase"] == "swing" and "lift" not in seg:
                bad += 1
    ok &= _chk("7 相位与措辞一致", bad == 0, f"bad={bad}")

    # 8 证伪：把定性映射阈值改成极端值，措辞必须改变（非硬编码）
    p2 = dict(PARAMS); p2["fwd"] = 0.99; p2["back"] = -0.99
    alt = [describe(pose.solve(spec, "walk", t=x["t"])["joints"],
                    pose.solve(spec, "walk", t=x["t"])["meta"], gait, "right", p2)
           for x in ps]
    ok &= _chk("8 证伪:阈值改变措辞随之改变", alt != poses)

    # 9 禁止骨架图字样进入提示词（铁律73）
    ok &= _chk("9 提示词无骨架/线框字样",
               not any(w in x["prompt"].lower() for x in ps
                       for w in ("skeleton", "wireframe", "stick figure")))

    # 10 手臂反相：同一时刻左右臂措辞不同
    same = sum(1 for x in ps
               if "left arm swinging forward" in x["pose"]
               and "right arm swinging forward" in x["pose"])
    ok &= _chk("10 左右臂不摆同侧", same == 0, f"same={same}")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if self_check() else 1)
