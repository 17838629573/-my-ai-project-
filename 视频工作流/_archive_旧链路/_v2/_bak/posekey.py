# -*- coding: utf-8 -*-
"""posekey —— 物理相位 → 精确生图提示词。

为什么要有这个模块（曾经的缺陷）：
  keygen.phase_desc 用手写的 4 段文字描述相位
  （"左脚跟刚着地，右腿在后蹬地"）—— 只有两个接触态来回接力，
  中间的摆动过程全是想象，生图自然只画出左右脚接力的两张脸。
  用户实测反馈：「图集只有左脚右脚接力状态，中间态没做出来」。

正确做法：用 pose.solve 把每个相位的关节算出来，再把数值翻译成提示词。
物理可算，不靠猜。

为什么必须减去骨盆 x（原地循环）：
  pose.solve 返回世界坐标，人整体一直往前走。
  但图集是「跑步机视图」——人物固定在画面中央，只有四肢相对身体动。
  不减骨盆 x，提示词会描述成整个人平移，生图就画出位移而非迈步。
  实测：不减时相邻相位最大关节位移 0.613m（整体前进占绝大部分），
        减掉后真实摆动幅度才暴露出来。

虚影的根因与对策（用户实测：「摆动幅度太大导致虚影」）：
  相邻相位关节位移越大，光流越糊。
  stride_m=1.5 → 0.427m   1.2 → 0.342m   1.0 → 0.287m   0.8 → 0.231m
  默认降到 1.0（比原设定降 33%），并允许继续下调。
"""
from __future__ import annotations

import json
import math
import os

import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import pose  # noqa: E402
import spec as SPEC  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SPEC_PATH = os.path.join(ROOT, "scene_spec.json")

# 默认步幅：比原 spec 的 1.5 小，用于抑制插帧虚影
DEFAULT_STRIDE_M = 1.0
DEFAULT_SPEED_MPS = SPEC.DEFAULT_SPEED_MPS
DEFAULT_KEYS = 8


def _rig() -> dict:
    if not os.path.exists(SPEC_PATH):
        raise SystemExit(f"缺 scene_spec.json: {SPEC_PATH}")
    sp = json.load(open(SPEC_PATH, encoding="utf-8"))
    rig = sp["biped_rig"]
    return {"anthro": rig["anthro"], "poses": rig["poses"],
            "height_m": rig["身高m"], "face": rig["face"]}


def subspec(stride_m: float = DEFAULT_STRIDE_M,
            speed_mps: float = DEFAULT_SPEED_MPS) -> dict:
    """构造传给 pose.solve 的最小 spec。

    铁律69: speed == stride / cycle，必须成立否则 pose 抛错。
    """
    if stride_m <= 0 or speed_mps <= 0:
        raise ValueError("stride_m / speed_mps 必须 > 0")
    d = _rig()
    gait = {
        "speed_m_s": speed_mps,
        "stride_m": stride_m,
        "cycle_s": stride_m / speed_mps,      # 铁律69
        "stance_ratio": 0.6,
        "swing_height_m": 0.12,
        "bob_m": 0.042,
        "arm_swing_deg": 24.6,
        "elbow_bend_deg": 25.0,
        "torso_lean_deg": 5.0,
        "pelvis_rot_deg": 5.0,
        "knee_land_bend_deg": 15.0,
    }
    d["gait"] = gait
    return d


def relpose(t: float, stride_m: float = DEFAULT_STRIDE_M,
            speed_mps: float = DEFAULT_SPEED_MPS) -> dict:
    """某时刻相对骨盆的关节坐标（原地循环视图）。

    返回米制：原点=地面脚下，y 向上，x 以骨盆为中心（负=在后，正=在前）。
    """
    ss = subspec(stride_m, speed_mps)
    cyc = ss["gait"]["cycle_s"]
    j = pose.solve(ss, "walk", t=t % cyc)["joints"]
    cx = (j["l_hip"][0] + j["r_hip"][0]) / 2.0
    hip_y = (j["l_hip"][1] + j["r_hip"][1]) / 2.0

    def rel(key):
        return [round(float(j[key][0]) - cx, 4), round(float(j[key][1]), 4)]

    return {
        "t": round(t % cyc, 4),
        "phase": round((t % cyc) / cyc, 4),
        "hip_y": round(hip_y, 4),
        "l_ankle": rel("l_ankle"), "r_ankle": rel("r_ankle"),
        "l_knee": rel("l_knee"), "r_knee": rel("r_knee"),
        "l_wrist": rel("l_wrist"), "r_wrist": rel("r_wrist"),
        "nose": rel("nose"),
    }


def sequence(n: int = DEFAULT_KEYS, stride_m: float = DEFAULT_STRIDE_M,
             speed_mps: float = DEFAULT_SPEED_MPS) -> list:
    """一个周期内均匀取 n 个相位。"""
    if n < 3:
        raise ValueError("一个周期至少需要 3 个相位")
    cyc = subspec(stride_m, speed_mps)["gait"]["cycle_s"]
    return [relpose(cyc * i / n, stride_m, speed_mps) for i in range(n)]


def max_shift(seq: list) -> float:
    """相邻相位最大关节位移（米）—— 虚影风险的直接指标。"""
    keys = ("l_ankle", "r_ankle", "l_knee", "r_knee")
    m = 0.0
    for i in range(len(seq)):
        a, b = seq[i], seq[(i + 1) % len(seq)]
        for k in keys:
            m = max(m, math.dist(a[k], b[k]))
    return round(m, 4)


# ---------- 数值 → 自然语言 ----------
GROUND_Y = 0.065      # 贴地时踝高（pose 的足厚）
_FB_THR = 0.05


def _fb(x: float) -> str:
    """前后：负=身后，正=身前。"""
    if abs(x) < _FB_THR:
        return "在身体正下方"
    return "伸向身前" if x > 0 else "留在身后"


def _lift(y: float) -> str:
    h = max(0.0, y - GROUND_Y)
    return "抬起约%.0f厘米" % (h * 100) if h >= 0.015 else "贴地踩实"


def leg_desc(rp: dict, side: str) -> str:
    """一条腿：支撑/摆动 + 前后 + 抬起高度。

    措辞必须自洽：「向前迈出」不能同时说「在身体正下方」，
    所以摆动腿统一说「摆动、{抬起}、{前后}」。
    """
    name = "左腿" if side == "l" else "右腿"
    a = rp[f"{side}_ankle"]
    if a[1] < 0.08:
        return "%s贴地踩实、%s" % (name, _fb(a[0]))
    return "%s摆动、%s、%s" % (name, _lift(a[1]), _fb(a[0]))


def stance_span(rp: dict) -> float:
    """双支撑时两脚前后间距（米）。"""
    return abs(rp["l_ankle"][0] - rp["r_ankle"][0])


def arm_desc(rp: dict) -> str:
    """手臂摆动：真实步态左右臂对侧摆动，故用【相对关系】描述。

    不能用绝对阈值判断「摆向身前/身后」：
    pose 的侧视投影在周期端点(t=0、0.5)左右腕 x 完全重合（对称姿态），
    此时按绝对值判会得出「两臂都摆向身前」这种不存在的姿态。
    """
    lw, rw = rp["l_wrist"][0], rp["r_wrist"][0]
    if abs(lw - rw) < 0.06:
        return "双臂在体侧自然并拢"
    if lw > rw:
        return "左臂摆向身前、右臂留在身后"
    return "右臂摆向身前、左臂留在身后"


def pose_desc(rp: dict) -> str:
    """把一个相位的关节数据翻译成一段精确描述。

    双支撑相必须报出两脚间距，否则生图会画成两脚并拢的站姿，
    丢掉「迈步」的关键信息 —— 这也是此前只见接力态的原因之一。
    """
    l, r = leg_desc(rp, "l"), leg_desc(rp, "r")
    grounded = sum(1 for s in ("l", "r") if rp[f"{s}_ankle"][1] < 0.08)
    if grounded == 2:
        span = stance_span(rp)
        base = "%s，%s，两脚前后分开约%.0f厘米" % (l, r, span * 100)
    else:
        base = "%s，%s" % (l, r)
    return "%s；%s" % (base, arm_desc(rp))


def keyframe_prompt(rp: dict, bg_desc: str, subject: str = "僧人") -> str:
    """组装一张关键帧提示词：背景锁 → 物理姿态 → 原地循环约束。"""
    from keygen import bg_block  # 延迟导入，避免与 keygen 循环依赖
    return "".join([
        bg_block(bg_desc),
        "【原地循环】%s站在画面正中固定位置，脚步为原地踏步式循环，"
        "身体不向画面任何一侧平移，只有四肢相对躯干摆动。" % subject,
        "【姿态精确】%s。" % pose_desc(rp),
    ])


def plan(bg_desc: str, n: int = DEFAULT_KEYS,
         stride_m: float = DEFAULT_STRIDE_M,
         speed_mps: float = DEFAULT_SPEED_MPS,
         subject: str = "僧人") -> dict:
    """生成一个周期全部关键帧的物理提示词。"""
    seq = sequence(n, stride_m, speed_mps)
    cyc = subspec(stride_m, speed_mps)["gait"]["cycle_s"]
    return {
        "period_s": round(cyc, 4),
        "n_keys": n,
        "key_interval_s": round(cyc / n, 4),
        "stride_m": stride_m,
        "speed_mps": speed_mps,
        "max_shift_m": max_shift(seq),
        "poses": seq,
        "prompts": [{"index": i, "phase": s["phase"],
                     "prompt": keyframe_prompt(s, bg_desc, subject)}
                    for i, s in enumerate(seq)],
    }


# ---------- 自检 ----------
def self_check() -> None:
    # 1) 相对坐标：骨盆居中，两踝一前一后
    rp = relpose(0.0)
    assert abs(rp["l_ankle"][0]) < 1e-6 or abs(rp["r_ankle"][0]) < 1e-6, rp

    # 2) 原地循环：任何相位，两踝 x 都不应同向大幅偏移（否则说明整体在平移）
    seq = sequence(8)
    for s in seq:
        xs = [s["l_ankle"][0], s["r_ankle"][0]]
        assert max(abs(x) for x in xs) < 0.5, f"出现整体平移: {xs}"

    # 3) 一个周期内必须出现「两脚同时贴地」的双支撑相（真实步态必有）
    ds = [s for s in seq
          if s["l_ankle"][1] < 0.08 and s["r_ankle"][1] < 0.08]
    assert len(ds) >= 1, "未出现双支撑相，步态不真实"

    # 4) 必须出现摆动腿（抬起）的相位 —— 这就是用户说的「中间态」
    sw = [s for s in seq if max(s["l_ankle"][1], s["r_ankle"][1]) > 0.09]
    assert len(sw) >= 2, f"缺少摆动中间态: {len(sw)}"

    # 5) 幅度下降：stride 越小相邻位移越小（用于抑制虚影）
    s15 = max_shift(sequence(8, 1.5))
    s10 = max_shift(sequence(8, 1.0))
    s08 = max_shift(sequence(8, 0.8))
    assert s08 < s10 < s15, (s08, s10, s15)
    assert abs(s15 - 0.427) < 0.02, f"stride1.5 位移应约0.427，实得{s15}"

    # 6) 提示词：含背景锁 + 原地循环 + 姿态数值
    pl = plan("唐代城墙，夕阳侧逆光", 8)
    assert len(pl["prompts"]) == 8
    for p in pl["prompts"]:
        t = p["prompt"]
        assert t.startswith("【背景严格锁定】"), t[:40]
        assert "原地循环" in t and "姿态精确" in t
        assert "飘动" not in t
    descs = {p["prompt"].split("【姿态精确】")[1] for p in pl["prompts"]}
    assert len(descs) >= 5, f"姿态描述种类太少(像接力态): {len(descs)}"

    # 7) 越界
    for fn in (lambda: sequence(2), lambda: subspec(0), lambda: subspec(1.0, 0)):
        try:
            fn()
            raise AssertionError("应当抛错")
        except (ValueError, SystemExit):
            pass

    print("posekey self_check OK  周期%.3fs 8相位 相邻位移%.3fm | "
          "姿态种类%d 双支撑%d 摆动%d | 幅度 1.5→%.3f 1.0→%.3f 0.8→%.3f"
          % (pl["period_s"], pl["max_shift_m"], len(descs),
             len(ds), len(sw), s15, s10, s08))


if __name__ == "__main__":
    self_check()
