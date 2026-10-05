#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""qc_all —— 视频质检【唯一入口】。一次跑完全部检查。

归档约定（2026-10-04 定）：
  所有质检相关工具，无论原本建在 _tools/ 还是 _tools/qcheck/，
  一律归档到 _tools/qcheck/ 下，由本文件统一调度。
  例外：qc_run 保留为像素层的独立入口（历史接口），qc_all 覆盖它。

为什么要唯一入口：
  工具散在两处时，测一遍要记住并敲 5 条命令，漏一条就等于没测。
  ——这正是"工具建了却没用"的常见原因。

四层检查（缺一层就漏掉一整类问题，见 QC_SCENE_EVIDENCE.json）：

  L0 素材层  sheet_audit  图集网格/顺序/绿边（业界连通域互证 + Aksoy 反解）
  L0 素材层  grid_check   切分结果（每格有主体、绿边达标）
  L0 素材层  spec_probe   场景几何三方一致（声明/检测/反解）
  L1 像素层  freeze/flicker/flow/ssim   帧间连不连贯
  L2 物理层  phys         运动自不自然（需传求解器参数）
  L3 场景层  scene        该不该在这个位置 / 图层是否同一层

用法:
  python3 -m _tools.qcheck.qc_all --video 成片.mp4 --bg _生成/城墙背景.png \\
      --sheets _生成/玄奘_图集.png _生成/旗_图集.png
  python3 -m _tools.qcheck.qc_all --video 成片.mp4 --bg ... --json report.json
"""
import argparse
import json
import os
import sys

from .qc_common import Seq


def _layer0(sheets=None, bg=None, spec=None):
    """素材层：图集 / 几何。任一 FAIL 则不必往下测。"""
    out = {}
    sys.path.insert(0, os.getcwd())
    if sheets:
        from .grid_check import check as gcheck
        from .sheet_audit import audit as saudit
        gs, ss = [], []
        for p in sheets:
            try:
                gs.append(gcheck(p))
            except Exception as e:
                gs.append({"path": p, "ok": False,
                           "reason": "%s: %s" % (type(e).__name__, str(e)[:80])})
            try:
                ss.append(saudit(p))
            except Exception as e:
                ss.append({"path": p, "ok": False,
                           "reason": "%s: %s" % (type(e).__name__, str(e)[:80])})
        out["sheet_cells"] = gs
        out["sheet_grid"] = ss
    try:
        from .spec_probe import probe
        r = probe(spec, bg)
        out["geometry"] = {k: r.get(k) for k in
                           ("horizon_ok", "horizon_verdict",
                            "perspective_ok", "perspective_verdict")}
    except Exception as e:
        out["geometry"] = {"ok": False,
                           "reason": "%s: %s" % (type(e).__name__, str(e)[:80])}
    # 注意（实测逼出）：不能写 `not x.get("ok")` —— sheet_audit 的返回里
    # 没有 "ok" 键，get 返回 None，not None = True，会把两条 PASS 的
    # 记录误判成 FAIL（L0_assets 因此误报）。必须按各工具的【实际字段名】判。
    def _bad(item):
        if "grid_agree" in item:          # sheet_audit
            return not item.get("grid_agree")
        if "verdict" in item:             # grid_check
            return not item.get("ok", True)
        if "reason" in item and "ok" in item:
            return not item.get("ok")
        return not item.get("ok", True)
    bad = [k for k, v in out.items()
           if isinstance(v, list) and any(_bad(x) for x in v)]
    bad += [k for k, v in out.items()
            if isinstance(v, dict) and v.get("ok") is False]
    out["ok"] = not bad
    out["failed"] = bad
    return out


def run(video, bg=None, sheets=None, spec=None, phys=None, max_frames=None):
    res = {"video": os.path.abspath(video), "layers": {}}

    # ---- L0 素材 ----
    res["layers"]["L0_assets"] = _layer0(sheets, bg, spec)

    seq = Seq(video)

    # ---- L1 像素 ----
    from . import qc_freeze, qc_flicker, qc_flow, qc_ssim
    L1 = {}
    try:
        ev = qc_freeze.detect(seq)   # 该模块不支持 max_frames（实测 TypeError）
        L1["freeze"] = {"events": len(ev) if hasattr(ev, "__len__") else None,
                        "frames": sum(int(e.get("frames", 0)) for e in ev)
                        if isinstance(ev, (list, tuple)) else None}
    except Exception as e:
        L1["freeze"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:60])}
    try:
        r = qc_flicker.detect(seq, fps=seq.fps)
        if isinstance(r, dict):
            L1["flicker"] = {k: v for k, v in r.items()
                             if k in ("pulse_count", "fail", "threshold")}
        else:
            L1["flicker"] = {"raw": str(r)[:80]}
    except Exception as e:
        L1["flicker"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:60])}
    try:
        r = qc_flow.analyze(seq, max_frames=max_frames)
        if isinstance(r, dict):
            L1["flow"] = {k: v for k, v in r.items()
                          if not isinstance(v, list)}
        else:
            L1["flow"] = {"raw": str(r)[:80]}
    except Exception as e:
        L1["flow"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:60])}
    try:
        r = qc_ssim.analyze(seq, max_frames=max_frames)
        pf = r.get("per_frame", []) if isinstance(r, dict) else []
        import numpy as np
        arr = [x.get("ssim_raw") for x in pf if x.get("ssim_raw") is not None]
        L1["ssim"] = {"min": round(float(min(arr)), 4) if arr else None,
                      "mean": round(float(sum(arr) / len(arr)), 4) if arr else None,
                      "jump_frames": [x["frame"] for x in pf if x.get("jump")][:20]}
    except Exception as e:
        L1["ssim"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:60])}
    res["layers"]["L1_pixel"] = L1

    # ---- L2 物理 ----
    from . import qc_phys
    try:
        if phys:
            r = qc_phys.analyze(phys, max_frames=max_frames)
        else:
            r = {"skipped": "未传求解器参数"}
        res["layers"]["L2_physics"] = r if isinstance(r, dict) else {"raw": str(r)[:80]}
    except Exception as e:
        res["layers"]["L2_physics"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:80])}

    # ---- L3 场景 ----
    from . import qc_scene
    try:
        # 必须用像素版（foot_y_px_seq）；米版与 horizon_y 单位不一致
        foot = (phys or {}).get("foot_y_px_seq") or (phys or {}).get("foot_y_seq")
        r = qc_scene.analyze(seq, bg_path=bg, max_frames=max_frames,
                             foot_y_seq=foot)
        res["layers"]["L3_scene"] = {k: v for k, v in r.items() if k != "per_frame"}
    except Exception as e:
        res["layers"]["L3_scene"] = {"error": "%s: %s" % (type(e).__name__, str(e)[:80])}

    # ---- 总判定 ----
    fails = []
    if not res["layers"]["L0_assets"].get("ok", True):
        fails.append("L0_assets")
    if L1.get("flicker", {}).get("fail"):
        fails.append("L1_flicker")
    if (L1.get("ssim", {}).get("min") or 1.0) < 0.85:
        fails.append("L1_ssim")
    if res["layers"].get("L3_scene", {}).get("verdict") == "FAIL":
        fails.append("L3_scene")
    res["failed_layers"] = fails
    res["verdict"] = "FAIL" if fails else "PASS"
    return res


def _jsonable(o):
    """numpy 标量/数组混进结果会让 json.dumps 直接崩（实测 float32）。"""
    import numpy as np
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--bg")
    ap.add_argument("--sheets", nargs="*")
    ap.add_argument("--spec")
    ap.add_argument("--phys-json", help="求解器参数 JSON（含 foot_y_seq 等）")
    ap.add_argument("--phys", choices=["auto"],
                    help="auto=由 scene_spec 自动生成求解器真值（P14 接线）")
    ap.add_argument("--max-frames", type=int, default=180)
    ap.add_argument("--json")
    a = ap.parse_args()
    phys = None
    if a.phys == "auto":
        try:
            from .qc_run import build_phys_from_spec
            phys = build_phys_from_spec(a.spec, a.max_frames or 480)
        except Exception as e:
            print("[warn] phys 自动注入失败: %s: %s" % (type(e).__name__, str(e)[:120]))
    elif a.phys_json:
        phys = json.load(open(a.phys_json, encoding="utf-8"))
    r = run(a.video, a.bg, a.sheets, a.spec, phys, a.max_frames)
    r = _jsonable(r)
    print(json.dumps(r, ensure_ascii=False, indent=2)[:4000])
    if a.json:
        json.dump(_jsonable(r), open(a.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        print("\n[报告] %s" % a.json)
    return 0 if r["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
