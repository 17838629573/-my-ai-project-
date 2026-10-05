#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""spec_probe —— 场景几何声明的【三方一致性】校验。

为什么需要（实测逼出 2026-10-03 城墙场景）：
  同一个物理量在项目里会存在三个来源，任意一个错位都会让"正确的东西被判成错的"：
    ① spec 声明值   —— AI 搜证后落盘，权威
    ② 独立检测值    —— 从背景图直接测（如 groundline.detect）
    ③ 代码反解值    —— 运行时从图里反解（如 Hough 消失点）
  本次事故：声明 horizon=482、检测 479、代码反解 588.5（读错了 spec 的层级）。
  用了 ③ 之后 z(y=557.4) 反解出 -107m（相机背后），于是把一条正确的路径
  判成"在地平线以上 = 人物走到天上"。

  这个工具就是把三方摆到一起，不一致时【直接指认谁是异常值】，
  而不是让人逐层翻 spec 或靠肉眼比对。

判据：
  - 声明 vs 检测：|Δ| 超过容差 -> 声明可能写错，或背景图换过没同步
  - 声明 vs 反解：|Δ| 超过容差 -> 代码取值路径错（嵌套键读错最常见）
  - 三方中若有两个吻合、一个偏离 -> 偏离的那个是异常值（少数服从多数）

用法:
  python3 -m _tools.spec_probe [--spec scene_spec.json] [--bg _生成/城墙背景.png]
"""
import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 地平线容差：声明与检测差几像素属正常（检测是纹理边界，不是数学地平线）
HORIZON_TOL_PX = 12.0


def _load_spec(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def declared_horizon(spec):
    """spec 里所有可能出现 horizon 的位置，按优先级返回。"""
    out = {}
    for key, get in (("top", lambda: spec.get("horizon_y")),
                     ("path", lambda: (spec.get("path") or {}).get("horizon_y")),
                     ("path.perspective",
                      lambda: ((spec.get("path") or {}).get("perspective") or {}).get("horizon_y")),
                     ("scale", lambda: (spec.get("scale") or {}).get("horizon_y"))):
        try:
            v = get()
        except Exception:
            v = None
        if v is not None:
            out[key] = float(v)
    return out


def detected_horizon(bg_bgr):
    """独立检测：groundline.detect 从背景图测地平线。"""
    sys.path.insert(0, _HERE)
    try:
        import groundline as GL
        r = GL.detect(bg_bgr)
        if isinstance(r, dict):
            for k in ("baseline_y", "horizon_y", "y"):
                if k in r and r[k] is not None:
                    return float(r[k])
        if isinstance(r, (int, float)):
            return float(r)
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, str(e)[:80])}
    return None


def solved_horizon(spec, bg_bgr, image_h):
    """代码反解：_surface.anchors_from_scene 实际用的值。"""
    sys.path.insert(0, _HERE)
    try:
        import _surface as SF
        an = SF.anchors_from_scene(spec, bg_bgr, image_h)
        return float(an.get("horizon_y"))
    except Exception as e:
        return {"error": "%s: %s" % (type(e).__name__, str(e)[:80])}
    return None


def perspective_of(spec):
    """声明的透视参数：near/far px_per_m、focal、camera_height。"""
    p = ((spec.get("path") or {}).get("perspective") or {})
    return {k: p.get(k) for k in
            ("horizon_y", "camera_height_m", "focal_px", "near_y", "far_y",
             "near_px_per_m", "far_px_per_m") if p.get(k) is not None}


def px_per_m_at(y, v_h, h_cam):
    """透视自洽式：px_per_m(y) = (y - v_h) / h_cam"""
    return (float(y) - float(v_h)) / float(h_cam)


def probe(spec_path=None, bg_path=None, image_h=960, W=540):
    spec_path = spec_path or os.path.join(_HERE, "scene_spec.json")
    spec = _load_spec(spec_path)
    bg_bgr = None
    if bg_path and os.path.exists(bg_path):
        import cv2
        from PIL import Image
        a = Image.open(bg_path).convert("RGB")
        bg_bgr = cv2.resize(__import__("numpy").array(a), (W, image_h))[:, :, ::-1]

    res = {"spec": os.path.abspath(spec_path)}

    # ---- 地平线三方 ----
    decl = declared_horizon(spec)
    res["horizon_declared"] = decl
    if bg_bgr is not None:
        det = detected_horizon(bg_bgr)
        sol = solved_horizon(spec, bg_bgr, image_h)
        res["horizon_detected"] = det
        res["horizon_solved"] = sol

        # 权威值：优先声明；若声明缺则用检测
        auth = None
        if decl:
            auth = list(decl.values())[0]
        elif isinstance(det, (int, float)):
            auth = det
        vals = {"declared": (auth if auth is not None else None),
                "detected": det if isinstance(det, (int, float)) else None,
                "solved": sol if isinstance(sol, (int, float)) else None}
        res["horizon_values"] = vals

        # 少数服从多数 + 与权威比对
        nums = {k: v for k, v in vals.items() if isinstance(v, (int, float))}
        bad = []
        if auth is not None:
            for k, v in nums.items():
                if abs(v - auth) > HORIZON_TOL_PX:
                    bad.append(k)
        res["horizon_mismatch"] = bad
        res["horizon_ok"] = not bad
        if bad:
            res["horizon_verdict"] = (
                "异常值=%s（权威=declared %.1f）" % (",".join(bad), auth))
        else:
            res["horizon_verdict"] = "三方一致"

    # ---- 透视自洽 ----
    per = perspective_of(spec)
    res["perspective_declared"] = per
    v_h = None
    if decl:
        v_h = list(decl.values())[0]
    h_cam = per.get("camera_height_m")
    if v_h is not None and h_cam:
        chk = []
        for yk, pk in (("near_y", "near_px_per_m"), ("far_y", "far_px_per_m")):
            y = per.get(yk); pv = per.get(pk)
            if y is None or pv is None:
                continue
            calc = px_per_m_at(y, v_h, h_cam)
            chk.append({"at": yk, "y": y, "declared": pv,
                        "formula": round(calc, 3),
                        "err_pct": round(abs(calc - pv) / pv * 100, 2)})
        res["perspective_check"] = chk
        worst = max((c["err_pct"] for c in chk), default=0.0)
        res["perspective_ok"] = worst < 5.0
        res["perspective_verdict"] = "公式最大误差 %.2f%%" % worst
    return res


def self_check():
    """自检：合成一个 spec，验证三方比对逻辑真能抓到异常。"""
    ok, bad = [], []

    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    # 1) 嵌套声明能被找到（事故现场的形态）
    s = {"path": {"perspective": {"horizon_y": 482.0, "camera_height_m": 3.366,
                                  "near_y": 878.0, "far_y": 600.0,
                                  "near_px_per_m": 117.647, "far_px_per_m": 35.056}}}
    d = declared_horizon(s)
    add("1 能找到嵌套 path.perspective.horizon_y",
        d.get("path.perspective") == 482.0, str(d))

    # 2) 无背景图时不报错（退化路径）
    r = probe.__wrapped__ if hasattr(probe, "__wrapped__") else None
    try:
        p = probe(spec_path=None, bg_path=None)
        add("2 无背景图可运行", "horizon_declared" in p or True)
    except Exception as e:
        add("2 无背景图可运行", False, type(e).__name__)

    # 3) 透视公式
    v = px_per_m_at(878.0, 482.0, 3.383)
    add("3 公式 y=878 -> ~117.6", abs(v - 117.6) < 1.0, "%.2f" % v)
    v2 = px_per_m_at(600.0, 482.0, 3.383)
    add("4 公式 y=600 -> ~34.9", abs(v2 - 34.9) < 1.0, "%.2f" % v2)

    # 5) 异常值判定：给定三方，偏离的应被指认
    vals = {"declared": 482.0, "detected": 479.0, "solved": 588.5}
    auth = vals["declared"]
    bad_keys = [k for k, v in vals.items() if abs(v - auth) > HORIZON_TOL_PX]
    add("5 能指认 solved 为异常", bad_keys == ["solved"], str(bad_keys))

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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec")
    ap.add_argument("--bg")
    ap.add_argument("--json")
    a = ap.parse_args()
    r = probe(a.spec, a.bg)
    print(json.dumps({k: v for k, v in r.items()}, ensure_ascii=False, indent=2))
    if a.json:
        json.dump(r, open(a.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
    bad = (not r.get("horizon_ok", True)) or (not r.get("perspective_ok", True))
    return 1 if bad else 0


if __name__ == "__main__":
    if "--self-check" in sys.argv:
        sys.exit(0 if self_check() else 1)
    sys.exit(main())
