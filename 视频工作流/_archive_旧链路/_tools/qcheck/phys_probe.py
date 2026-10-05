#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""phys_probe —— 从【求解器真值】生成物理层质检参数，注入 qc_phys / qc_all。

为什么要有这个工具（P14 的实质）：
  qc_phys 里 check_gait_lock / check_foot_sliding / check_gait_footlock /
  check_balance / check_slip 五个函数【早就写好且自检通过】，
  但 qc_run 需要调用方手工拼 phys dict，没人拼 -> 恒 skipped。
  有工具不用 = 没有工具。本工具就是那个"接线的人"。

业界对照（搜证 2026-10-04，详见 QC_SCENE_EVIDENCE.json）：
  MORPHEUS(arXiv 2504.02918)：用 SAM-2 提轨迹 + 中心差分求速度 + Savitzky-Golay
    平滑，再拟合 PINN 判物理一致性。
    —— 但那是【没有真值时被迫反推】。本项目运动是求解器算出来的，
       直接比对渲染结果 vs 求解器期望值即可，无需 SAM-2 反推。
  PhysStream：traj-ADE + failure rate（偏离 >30px 记失败）。
  ECCV 2020 "Contact and Human Dynamics from Monocular Video"：
    给出【可直接用的量化步态指标】（这是本工具采纳的核心）：
      Floating    = 该触地时脚离地 > 3cm 的比例
      Penetration = 陷入地面 > 3cm 的比例
      Skate       = 接触期间移动 > 2cm 的比例（脚滑）
    三者越低越好，且都给了明确阈值。
  MORPHEUS 另有 Discard Rate：物体消失/复制/不动（"stillness trap"）。

  综合：本工具输出
    A) 注入参数：gait / contacts_seq / links_seq / force_seq / env / foot_y_seq
    B) 真值判据：foot_metrics（Floating/Penetration/Skate，用 ECCV2020 阈值）
    C) 真值判据：discard（物体消失/静止不动）

用法:
  python3 -m _tools.qcheck.phys_probe --spec scene_spec.json --frames 480 --fps 60
  python3 -m _tools.qcheck.phys_probe --self-check
"""
import argparse
import json
import os
import sys

import numpy as np

# 延迟导入（函数内），避免与 phys_metrics 的顶层 import 形成循环

_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ECCV 2020 步态指标阈值（业界给死，不自拟）
FLOAT_M = 0.03     # 离地超过 3cm 记 Floating
PENET_M = 0.03     # 陷入超过 3cm 记 Penetration
SKATE_M = 0.02     # 接触期移动超过 2cm 记 Skate


def _gait_of(spec):
    """从 spec 取步态参数，缺则报错（不许静默用默认值）。

    实测逼出（2026-10-04）：
      spec 顶层 gait 只有 {speed_mps, stride_m}，而 pose.foot_target 真正需要的是
      {cycle_s, stride_m, stance_ratio, swing_height_m, speed_m_s} ——
      完整参数在【spec.biped_rig.gait】下，不在顶层。
      且键名是 speed_m_s 不是 speed_mps；side 传 "l"/"r" 不是 "left"/"right"。
      第一版按顶层 + 英文名写，30 帧算出 0 个有效点（全部落 except 被吞）。
    """
    rig = spec.get("biped_rig") or {}
    g = rig.get("gait") or {}
    top = spec.get("gait") or {}
    # cycle_s 缺失时由 stride/speed 推（业界：周期 = 步幅 / 速度）
    stride = g.get("stride_m", top.get("stride_m"))
    speed = g.get("speed_m_s", top.get("speed_mps"))
    cycle = g.get("cycle_s")
    if cycle is None and stride and speed:
        cycle = float(stride) / float(speed)
    gait = {
        "stride_m": float(stride) if stride is not None else None,
        "speed_m_s": float(speed) if speed is not None else None,
        "cycle_s": float(cycle) if cycle is not None else None,
        "stance_ratio": float(g.get("stance_ratio", 0.6)),
        "swing_height_m": float(g.get("swing_height_m", 0.12)),
        "ankle_y_m": float(g.get("ankle_y_m", 0.065)),
    }
    miss = [k for k, v in gait.items() if v is None]
    if miss:
        raise ValueError("[phys_probe] 步态参数缺 %s —— 不许静默用默认值"
                         % miss)
    return gait


def foot_tracks(spec, n_frames, fps=60.0):
    """用求解器算逐帧脚部轨迹（真值，不是从视频反推）。"""
    sys.path.insert(0, _HERE)
    import pose
    gait = _gait_of(spec)
    out = {}
    for side in ("l", "r"):
        seq = []
        for i in range(n_frames):
            t = i / float(fps)
            try:
                r = pose.foot_target(t, side, gait)
                p = r[0] if isinstance(r, tuple) else r
                seq.append((float(p[0]), float(p[1])))
            except Exception:
                seq.append(None)
        out[{"l": "left", "r": "right"}[side]] = seq
    return out, gait


def contact_of(spec, n_frames, fps=60.0, tracks=None):
    """接触序列：由求解器的脚轨迹判定（业界用 penetration 检测 + 迟滞防抖）。"""
    if tracks is None:
        tracks, _ = foot_tracks(spec, n_frames, fps)
    sys.path.insert(0, _HERE)
    import _common
    spec_g = spec.get("biped_rig") or {}
    ankle_y = float(((spec_g.get("gait") or {}).get("ankle_y_m")) or 0.065)

    out = {}
    for side, seq in tracks.items():
        cs = []
        for i, p in enumerate(seq):
            if p is None:
                cs.append(False); continue
            # 速度用中心差分（业界 MORPHEUS 同法：轨迹再中心差分求速度）
            if 0 < i < len(seq) - 1 and seq[i-1] and seq[i+1]:
                dt = 2.0 / float(fps)
                vx = (seq[i+1][0] - seq[i-1][0]) / dt
                vy = (seq[i+1][1] - seq[i-1][1]) / dt
            else:
                vx = vy = 0.0
            try:
                # foot_contact(toe_xy, toe_vel, ground_y) —— 三参缺一不可。
                # 第一版只传 p[1]，TypeError 被 except 静默吞成 False，
                # 于是 contact_frames 恒为 0，三项指标永远 0.0（假通过）。
                cs.append(bool(_common.foot_contact(
                    (float(p[0]), float(p[1])), (vx, vy), ankle_y)))
            except Exception:
                cs.append(False)
        out[side] = cs
    return out








def build_phys(spec_path=None, n_frames=480, fps=60.0,
               px_per_m=117.647, ground_y=None):
    """生成可直接传给 qc_run / qc_all 的 phys dict —— 这就是 P14 的接线。

    【诚实边界，必须写清】
      foot_metrics 是【求解器 vs 求解器】，必然全 0 —— 这不叫通过，叫循环论证。
      它的真正价值有两处：
        ① 给 qc_scene 提供 foot_y_seq（渲染上报），让天空约束能硬判；
           不可替代 —— 实测若无上报，像素反推会把墙上的幡误判成飘天（12帧全误报）。
        ② 渲染层引入误差后，可用同一轨迹与渲染结果比对。
      定位是【提供真值基准】，不是【自己证明自己对】。
    """
    # spec_path 既可是路径，也可是已加载的 dict（实测逼出：
    # qc_run.build_phys_from_spec 传的是 dict，旧版只认路径 -> TypeError）
    if isinstance(spec_path, dict):
        spec = spec_path
    else:
        spec_path = spec_path or os.path.join(_HERE, "scene_spec.json")
        spec = json.load(open(spec_path, encoding="utf-8"))
    gait = _gait_of(spec)
    tracks, _ = foot_tracks(spec, n_frames, fps)
    contacts = contact_of(spec, n_frames, fps, tracks)

    # links_seq / force_seq：qc_phys 需要的最小结构（由脚轨迹构造）
    links_seq = []
    for i in range(n_frames):
        links_seq.append({"left": tracks["left"][i], "right": tracks["right"][i]})

    sys.path.insert(0, _HERE)
    try:
        import environment as ENV
        env = ENV.scene_env(spec) if hasattr(ENV, "scene_env") else {"mu": 0.85}
    except Exception:
        env = {"mu": 0.85}
    mass = float((spec.get("biped_rig") or {}).get("mass_kg", 60.0))
    g = 9.81
    force_seq = [{"tangent": 0.0, "normal": mass * g} for _ in range(n_frames)]

    foot_y = [p[1] for p in tracks["left"]]   # 米（物理层用）

    # foot_y_px_seq：屏幕像素（场景层天空约束用）。
    # 【实测逼出的单位陷阱】foot_y 是米(0.065)，horizon_y 是像素(482)，
    # 直接拿米去比像素会让 120 帧全被判"飘天"（min_y=0.2 max_y=0.1）。
    # 必须走与 build_video 相同的路径投影，得到像素坐标。
    foot_y_px = None
    try:
        import build_phase_setup as BPS
        import path as PA
        from PIL import Image
        import cv2
        import numpy as np
        bgp = os.path.join(_HERE, "_生成", "城墙背景.png")
        if os.path.exists(bgp):
            im = np.array(Image.open(bgp).convert("RGB"))
            bg = cv2.resize(im, (540, 960))[:, :, ::-1]
            near = float(((spec.get("path") or {}).get("perspective") or {})
                         .get("near_px_per_m", 117.647))
            info = BPS.setup_path(spec, bg, 540, 960, near)
            pts = info["pts"]
            speed = float(gait.get("speed_m_s", 1.5))
            # 【V8】必须与渲染端同一套推进：地面坐标按米积分。
            #   老代码用像素弧长 (speed*px_per_m*t)，导致上报的脚 y 与真实渲染
            #   完全对不上（渲染走到 y=675，上报却说 874）——天空约束数据不可信。
            import _ground_arc as GA
            _cam = GA.cam_of(spec)
            _wt = GA.world_arc_table(pts, _cam)
            foot_y_px = []
            for i in range(n_frames):
                t = i / float(fps)
                foot_y_px.append(
                    float(GA.at_world_distance(speed * t, _wt, _cam)["xy"][1]))
    except Exception as e:
        foot_y_px = None
        sys.stderr.write("[warn] foot_y_px 计算失败: %s: %s\n"
                         % (type(e).__name__, str(e)[:100]))

    return {
        "gait": gait,
        "contacts_seq": contacts,
        "links_seq": links_seq,
        "force_seq": force_seq,
        "env": env,
        "foot_y_seq": foot_y,
        "foot_y_px_seq": foot_y_px,
        "t_max": n_frames / float(fps),
        "fps": fps,
        "_source": "phys_probe（求解器真值，非视频反推）",
    }


def self_check():
    from .phys_metrics import foot_metrics, discard_rate  # 延迟：打破与 phys_metrics 的循环导入
    ok, bad = [], []

    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    # 1) gait 缺参数必须报错，不许静默默认值
    try:
        _gait_of({})
        add("1 spec.gait 缺失时报错", False, "居然没报错")
    except ValueError:
        add("1 spec.gait 缺失时报错", True)

    # 注意（实测修正）：周期 = stride / speed，不是 stride/speed*2。
    # stride_m 本就是"完整步幅"（双脚各迈一次），foot_target 里 k*stride 直接
    # 作为重复距离。实测 cycle=1.0s，与 build_video 打印的
    # "人8帧×0.1250s=1.0000s（=周期，循环无缝）" 完全吻合 —— 是交叉验证。
    g = _gait_of({"gait": {"speed_mps": 1.5, "stride_m": 1.5}})
    add("2 cycle_s = stride/speed = 1.0", abs(g["cycle_s"] - 1.0) < 1e-9,
        "cycle=%.4f" % g["cycle_s"])

    # 3) 真实 spec 能算出轨迹
    try:
        tr, _ = foot_tracks(None if False else
                            json.load(open(os.path.join(_HERE, "scene_spec.json"),
                                           encoding="utf-8")), 30, 60.0)
        nl = sum(1 for p in tr["left"] if p is not None)
        add("3 求解器能算脚轨迹", nl > 0, "有效点=%d/30" % nl)
    except Exception as e:
        add("3 求解器能算脚轨迹", False, "%s: %s" % (type(e).__name__, str(e)[:60]))

    # 4) phys dict 结构完整
    try:
        ph = build_phys(n_frames=30, fps=60.0)
        need = ("gait", "contacts_seq", "links_seq", "force_seq", "env",
                "foot_y_seq")
        miss = [k for k in need if k not in ph]
        add("4 phys dict 键完整", not miss, str(miss))
        add("5 foot_y_seq 长度正确", len(ph["foot_y_seq"]) == 30,
            str(len(ph["foot_y_seq"])))
    except Exception as e:
        add("4 phys dict 键完整", False, "%s: %s" % (type(e).__name__, str(e)[:80]))

    # 6) 三项步态指标可算（合成直线轨迹：贴地、接触、匀速 -> skate 应低）
    spec = {"gait": {"speed_mps": 1.5, "stride_m": 1.5}}
    try:
        m, _ = foot_metrics(spec, 30, 60.0, px_per_m=117.647)
        has = [k for k in ("left", "right") if k in m and "skate" in m[k]]
        add("6 三项步态指标可算", len(has) > 0,
            str({k: m[k].get("skate") for k in has}))
    except Exception as e:
        add("6 三项步态指标可算", False, "%s: %s" % (type(e).__name__, str(e)[:80]))

    # 7) discard rate
    try:
        d = discard_rate({"a": [(0.0, 0.0)] * 10})
        add("7 静止轨迹被判 stillness", d["a"]["stillness"] == 1.0, str(d["a"]))
    except Exception as e:
        add("7 静止轨迹被判 stillness", False, str(e)[:60])

    print("PASS:")
    for x in ok:
        print("  " + x)
    if bad:
        print("FAIL:")
        for x in bad:
            print("  " + x)
    else:
        print("FAIL: 无")
    return not bad


    from .phys_metrics import foot_metrics, discard_rate  # 延迟：打破与 phys_metrics 的循环导入
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec")
    ap.add_argument("--frames", type=int, default=480)
    ap.add_argument("--fps", type=float, default=60.0)
    ap.add_argument("--json")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        return 0 if self_check() else 1
    ph = build_phys(a.spec, a.frames, a.fps)
    info = {"gait": ph["gait"], "source": ph["_source"],
            "frames": a.frames,
            "foot_metrics": foot_metrics(
                json.load(open(a.spec or os.path.join(_HERE, "scene_spec.json"),
                               encoding="utf-8")), a.frames, a.fps)[0],
            "discard": discard_rate(foot_tracks(
                json.load(open(a.spec or os.path.join(_HERE, "scene_spec.json"),
                               encoding="utf-8")), a.frames, a.fps)[0])}
    print(json.dumps(info, ensure_ascii=False, indent=2))
    if a.json:
        json.dump(ph, open(a.json, "w", encoding="utf-8"), ensure_ascii=False)
        print("\n[phys 参数已写入] %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
