#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qcheck 主入口：对一段视频跑全套无参考质量检测，输出 JSON + 判定。

用法:
    python3 -m _tools.qcheck.qc_run <video> [--json out.json] [--quiet]

分层:
  像素层  冻结 / 闪烁 / 光流一致性 / 帧间 SSIM   —— 测【一致性】
  物理层  步态锁相 / 足锁 / 平衡 / 滑移          —— 测【自然度】
          物理层需要求解器参数（gait / contacts / forces），
          命令行不传则跳过（生成流水线里由调用方注入）。

阈值原则：不照搬业界默认值（那些是给压缩视频定的）。
  本文件给出初值并标注 [未标定]，实测分布后用 --calib 校准。
"""
import argparse
import json
import os
import sys

from .qc_common import Seq  # 无 open_video：Seq 直接读目录/列表/视频
from . import qc_freeze, qc_flicker, qc_flow, qc_ssim, qc_phys

# 判定阈值初值（来源标注，未标定的需实测校准）
THRESH = {
    "freeze_ratio":      (0.10, "取 10% 冻结帧为上限；EBU 只给事件定义不给占比阈值 [未标定]"),
    "flicker_fail":      (False, "ITU-R BT.1702 / Ofcom：1 秒内 >=3 次亮暗反转即不合格"),
    "min_ssim_aligned":  (0.90, "SSIM 0.90 常用作'结构相似'门槛 [未标定，帧间场景待校准]"),
    "mean_occlusion":    (0.15, "双向光流不一致区域占比；越高说明 warp 失败越多 [未标定]"),
    "flow_consistency":  (None, "光流与时间邻帧的偏差 std，越低越平滑；无绝对阈值 [未标定]"),
    "gait_lock_tol":     (1e-6, "speed == stride/cycle，恒等式不成立必 foot sliding"),
    "foot_slide_max":    (1e-6, "支撑期脚的世界坐标位移上限（米）"),
    "balance_fail_ratio": (0.0, "ZMP 出界帧占比，>0 即失衡"),
    "slip_fail_ratio":   (0.0, "不该滑的时候滑了，>0 即异常"),
}


def _ok(name, val, limit, cmp):
    """cmp: 'le' 越小越好 | 'ge' 越大越好 | 'eq' 必须等于"""
    if limit is None:
        return None          # 未标定：只报测量值，不判定
    if cmp == "le":
        return bool(val <= limit)
    if cmp == "ge":
        return bool(val >= limit)
    return bool(val == limit)


def run(path, phys=None, max_frames=None):
    """phys: 可选 dict，含 gait / contacts / forces / env，用于物理层。"""
    src = Seq(path)
    n = len(src)
    out = {"video": os.path.abspath(path), "frames": n,
           "fps": round(src.fps, 3), "layers": {}}

    # ---------- 像素层 ----------
    # 冻结：detect 返回 list（_Events），判定用 score
    ev = qc_freeze.detect(src)
    fr = qc_freeze.score(ev, n)
    out["layers"]["freeze"] = {
        "frozen_frames": fr["frozen_frames"],
        "frozen_ratio": round(fr["ratio"], 4),
        "events": fr["events"],
        "thresh": getattr(ev, "thresh", {}),
        "ok": _ok("freeze", fr["ratio"],
                  THRESH["freeze_ratio"][0], "le")}

    # 闪烁：detect 返回 dict，自带 fail
    fk = qc_flicker.detect(src, fps=src.fps)
    out["layers"]["flicker"] = {
        "pulse_count": fk["pulse_count"],
        "worst_window_count": fk["worst_window_count"],
        "worst_window_at": fk["worst_window_at"],
        "threshold": fk["threshold"],
        "ok": not fk["fail"]}

    # 光流一致性
    fl = qc_flow.analyze(src, max_frames=max_frames)
    fs = fl["summary"]
    out["layers"]["flow"] = {
        "flow_consistency_std": round(fs["flow_consistency_std"], 4),
        "motion_smoothness_std": round(fs["motion_smoothness_std"], 4),
        "mean_occlusion_ratio": round(fs["mean_occlusion_ratio"], 4),
        "max_occlusion_ratio": round(fs["max_occlusion_ratio"], 4),
        "ok": _ok("flow", fs["mean_occlusion_ratio"],
                  THRESH["mean_occlusion"][0], "le")}

    # 帧间 SSIM
    ss = qc_ssim.analyze(src, max_frames=max_frames)
    ssum = ss["summary"]
    out["layers"]["ssim"] = {
        "mean_ssim_aligned": round(ssum["mean_ssim_aligned"], 4),
        "min_ssim_aligned": round(ssum["min_ssim_aligned"], 4),
        "mean_ssim_raw": round(ssum["mean_ssim_raw"], 4),
        "jump_frames": ssum["jump_frames"],
        "ok": _ok("ssim", ssum["min_ssim_aligned"],
                  THRESH["min_ssim_aligned"][0], "ge")}

    # ---------- 物理层（可选）----------
    ph = {}
    if phys:
        if "gait" in phys:
            g = phys["gait"]
            ph["gait_lock"] = qc_phys.check_gait_lock(
                g["speed_m_s"], g["stride_m"], g["cycle_s"],
                THRESH["gait_lock_tol"][0])
            ph["foot_sliding"] = qc_phys.check_foot_sliding(
                g, t_max=phys.get("t_max", 2.0), fps=phys.get("fps", 60.0))
            ph["gait_footlock"] = qc_phys.check_gait_footlock(
                g, t_max=phys.get("t_max", 2.0), fps=phys.get("fps", 60.0))
        if "contacts_seq" in phys and "links_seq" in phys:
            ph["balance"] = qc_phys.check_balance(
                phys["links_seq"], phys["contacts_seq"])
        if "force_seq" in phys and "env" in phys:
            ph["slip"] = qc_phys.check_slip(
                phys["force_seq"], phys["env"])
        out["layers"]["phys"] = {"ok": True, **ph}
    else:
        out["layers"]["phys"] = {"ok": None, "skipped": "未传求解器参数"}

    # ---------- 总判定 ----------
    judged = {k: v.get("ok") for k, v in out["layers"].items()}
    unknown = [k for k, v in judged.items() if v is None]
    failed = [k for k, v in judged.items() if v is False]
    out["summary"] = {
        "failed": failed,
        "unknown(未标定/跳过)": unknown,
        "verdict": "FAIL" if failed else ("UNKNOWN" if unknown else "PASS")}
    return out


METRICS = [
    ("freeze",  "frozen_ratio",          "le"),
    ("flicker", "worst_window_count",    "le"),
    ("flow",    "flow_consistency_std",  "le"),
    ("flow",    "motion_smoothness_std", "le"),
    ("flow",    "mean_occlusion_ratio",  "le"),
    ("ssim",    "min_ssim_aligned",      "ge"),
    ("ssim",    "jump_frames",           "le"),
]


def _get(layers, layer, key):
    v = layers.get(layer, {})
    return v.get(key)


def calib(good_path, others, max_frames=None):
    """标定：以一段公认正常的视频为基准，给出各指标的建议阈值。

    绝对值阈值在生成视频上没有意义 —— 必须相对自己的成片标定。
    建议值 = 基准视频该指标的 max（'ge' 型取 min）再放宽 margin。
    """
    margin = 1.5
    base = run(good_path, max_frames=max_frames)["layers"]
    rows = []
    for layer, key, cmp in METRICS:
        b = _get(base, layer, key)
        if b is None:
            continue
        # 基准为 0 时 margin 无意义（0*1.5=0）—— 直接取 0，标注"严格"
        if float(b) == 0.0:
            limit, note = 0.0, "基准为 0，取严格值 0"
        elif cmp == "le":
            limit, note = float(b) * margin, "基准 x%.1f" % margin
        else:
            limit, note = float(b) / margin, "基准 /%.1f" % margin
        rows.append({"layer": layer, "metric": key, "cmp": cmp,
                     "base": round(float(b), 4),
                     "suggested": round(float(limit), 4), "note": note})
    # 对照：其它视频在该建议阈值下是否会被判为异常
    for o in others:
        r = run(o, max_frames=max_frames)["layers"]
        name = os.path.basename(o)
        for row in rows:
            v = _get(r, row["layer"], row["metric"])
            if v is None:
                continue
            bad = (v > row["suggested"]) if row["cmp"] == "le" \
                else (v < row["suggested"])
            row.setdefault("others", {})[name] = \
                ("%.4f%s" % (v, " ✗超阈" if bad else ""))
    return {"baseline": os.path.abspath(good_path), "margin": margin,
            "metrics": rows}


def build_phys_from_spec(spec_path=None, n_frames=480, fps=60.0):
    """自动注入求解器真值（P14）—— 让 phys 层不再 skipped。

    用法: python3 -m _tools.qcheck.qc_run --phys auto
    """
    import json, os, sys
    from .phys_probe import build_phys
    sp = spec_path or os.path.join(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))), "scene_spec.json")
    spec = json.load(open(sp, encoding="utf-8"))
    return build_phys(spec, n_frames, fps)


def main():
    ap = argparse.ArgumentParser(description="无参考视频质量检测")
    ap.add_argument("video")
    ap.add_argument("--json", help="写出 JSON 报告")
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--phys", help="物理层参数 JSON（含 gait/contacts_seq/...）")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--calib", nargs="*", default=None,
                    help="标定模式：--calib 其它视频...（当前 video 视为基准）")
    a = ap.parse_args()

    phys = None
    if a.phys:
        phys = json.load(open(a.phys, encoding="utf-8"))

    if a.calib is not None:
        c = calib(a.video, a.calib, max_frames=a.max_frames)
        print("=" * 62)
        print("标定：以 %s 为基准（margin=%.1f）"
              % (os.path.basename(c["baseline"]), c["margin"]))
        print("=" * 62)
        for row in c["metrics"]:
            print("\n  %s.%s  (%s)" % (row["layer"], row["metric"], row["cmp"]))
            print("    基准值 %.4f  ->  建议阈值 %.4f   (%s)"
                  % (row["base"], row["suggested"], row.get("note", "")))
            for k, v in row.get("others", {}).items():
                print("      %-16s %s" % (k, v))
        if a.json:
            json.dump(c, open(a.json, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
        return 0

    r = run(a.video, phys=phys, max_frames=a.max_frames)
    if a.json:
        json.dump(r, open(a.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)

    if not a.quiet:
        print("=" * 62)
        print("qcheck  %s  (%d 帧 @ %.2f fps)"
              % (os.path.basename(r["video"]), r["frames"], r["fps"]))
        print("=" * 62)
        for k, v in r["layers"].items():
            ok = v.get("ok")
            tag = "PASS" if ok else ("FAIL" if ok is False else " - ")
            print(f"\n[{tag}] {k}")
            for kk, vv in v.items():
                if kk in ("ok", "events", "per_frame", "luma", "pulses"):
                    continue
                print(f"    {kk}: {vv}")
        print("\n" + "-" * 62)
        s = r["summary"]
        print("verdict:", s["verdict"])
        if s["failed"]:
            print("  FAIL:", ", ".join(s["failed"]))
        if s["unknown(未标定/跳过)"]:
            print("  未标定/跳过:", ", ".join(s["unknown(未标定/跳过)"]))
    return 0 if r["summary"]["verdict"] != "FAIL" else 1


if __name__ == "__main__":
    sys.exit(main())
