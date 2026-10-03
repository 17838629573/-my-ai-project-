#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""scale_map.py — 比例尺层：把「米」换算成「像素」

业界依据（联网搜证）：
  · 图集交付必含 pixels per unit 导入说明      → px_per_m 一级输出
  · 尺度用 named reference object 锁定，不靠肉眼 → reference 唯一
  · AI 无内在尺度感，须注入米制参照             → prompt_block()
  · Baseline 锁定防弹跳                        → baseline_y 全局共用
  · Pivot 规则防脚/武器跳动                     → pivot 决定落位原点

本文件不含任何真实尺寸常量（铁律32）——所有米制由 AI 搜证后传入。
"""
import math

REQUIRED_CANVAS = ("w_px", "h_px")
REQUIRED_REF = ("name", "real_m", "px")
PIVOTS = ("bottom_center", "top_center", "center")

# 默认容差：由 AI 声明可覆盖（铁律32，不写死在逻辑里）
DEFAULT_TOL = {"rel": 0.15}


def _need(d, keys, where):
    miss = [k for k in keys if k not in d]
    if miss:
        raise KeyError("[scale_map] %s 缺必填槽 %s（铁律31：缺槽即报错，禁静默填默认）"
                       % (where, miss))


def build_scale_map(scene):
    """米 → 像素。所有部件对同一个命名参照物取尺度。"""
    _need(scene, ("canvas", "reference", "baseline_y", "objects"), "scene")
    cv = scene["canvas"]
    _need(cv, REQUIRED_CANVAS, "canvas")
    ref = scene["reference"]
    _need(ref, REQUIRED_REF, "reference")

    if ref["real_m"] <= 0 or ref["px"] <= 0:
        raise ValueError("[scale_map] 参照物 real_m/px 必须为正")

    px_per_m = float(ref["px"]) / float(ref["real_m"])
    base_y = int(scene["baseline_y"])
    tol = dict(DEFAULT_TOL)
    tol.update(scene.get("tolerance", {}))

    objs = []
    for o in scene["objects"]:
        _need(o, ("name", "real_m"), "objects[]")
        pivot = o.get("pivot", "bottom_center")
        if pivot not in PIVOTS:
            raise ValueError("[scale_map] %s pivot=%r 不在 %s" % (o["name"], pivot, PIVOTS))
        on_ground = bool(o.get("on_ground", False))
        if on_ground and not o.get("anchor_y_px") is None and pivot != "bottom_center":
            raise ValueError("[scale_map] %s 落地物 pivot 必须为 bottom_center" % o["name"])

        h_px = o["real_m"] * px_per_m
        w_m = o.get("real_w_m")
        w_px = (w_m * px_per_m) if w_m else h_px * float(o.get("aspect", 1.0))
        aspect = (float(o["real_m"]) / float(w_m)) if w_m else float(o.get("aspect", 1.0))

        # 落位：站立物底边贴 baseline；悬挂物用 anchor_y_px 作顶边
        if on_ground:
            bottom = base_y
            top = bottom - h_px
        elif "anchor_y_px" in o:
            top = float(o["anchor_y_px"])
            bottom = top + h_px
        else:
            top = float(o.get("top_y_px", 0))
            bottom = top + h_px

        objs.append({
            "name": o["name"],
            "real_m": float(o["real_m"]),
            "target_h_px": round(h_px, 2),
            "target_w_px": round(w_px, 2),
            "aspect_h_over_w": round(aspect, 4),
            "pivot": pivot,
            "on_ground": on_ground,
            "box": (round(top, 1), round(bottom, 1)),
            "ratio_to_ref": round(float(o["real_m"]) / float(ref["real_m"]), 4),
        })

    return {
        "px_per_m": round(px_per_m, 4),
        "reference": {"name": ref["name"], "real_m": float(ref["real_m"]),
                      "px": float(ref["px"])},
        "baseline_y": base_y,
        "canvas": {"w_px": int(cv["w_px"]), "h_px": int(cv["h_px"])},
        "tolerance": tol,
        "objects": objs,
    }


def verify(smap, measured):
    """AI 量出资产实际像素高 → 代码比对 target_px。超阈值即 FAIL（铁律64）。"""
    tol = smap["tolerance"]
    report, ok = [], True
    lut = {o["name"]: o for o in smap["objects"]}
    for m in measured:
        name = m.get("name")
        got = m.get("h_px")
        if name not in lut:
            report.append({"name": name, "status": "unknown", "detail": "未在 scale_map 登记"})
            ok = False
            continue
        tgt = lut[name]["target_h_px"]
        if not got or got <= 0:
            report.append({"name": name, "status": "fail", "detail": "未提供有效实测像素"})
            ok = False
            continue
        rel = abs(got - tgt) / tgt
        if rel > tol["rel"]:
            ok = False
            status = "fail"
        else:
            status = "pass"
        report.append({
            "name": name,
            "status": status,
            "target_px": tgt,
            "measured_px": round(float(got), 2),
            "rel_err": round(rel, 4),
            "suggest_scale": round(tgt / float(got), 4),
        })
    return ok, report


def prompt_block(smap):
    """生图用米制描述块（铁律65）。AI 无内在尺度感，必须显式注入。"""
    ref = smap["reference"]
    lines = [
        "【比例尺·必须体现在画面中】",
        "命名参照物：%s，身高 %.2f 米，在画面中占 %.0f 像素" % (ref["name"], ref["real_m"], ref["px"]),
        "全图比例：1 米 = %.1f 像素（px_per_m）" % smap["px_per_m"],
        "地平线：y = %d 像素，所有站立人物/动物的脚底必须落在这条线上" % smap["baseline_y"],
        "各物体真实尺寸与换算：",
    ]
    for o in smap["objects"]:
        lines.append("  · %s 实高 %.2f 米 = %.0f 像素（参照物的 %.2f 倍）%s"
                     % (o["name"], o["real_m"], o["target_h_px"],
                        o["ratio_to_ref"],
                        "，脚底贴地平线" if o["on_ground"] else "，悬挂物"))
    lines.append("禁止用『巨大/小巧』等形容词表达尺寸——模型无内在尺度感，"
                 "必须用上述米数与倍数关系构图。")
    return "\n".join(lines)


def self_check():
    fails = []

    def ck(name, cond, detail=""):
        print(("  PASS " if cond else "  FAIL ") + name + ("  " + detail if detail else ""))
        if not cond:
            fails.append(name)

    # 用 AI 搜证的唐代真实尺寸构造（非硬编码常量，仅自检用例）
    XZ_M, HORSE_M, GATE_M, POP_M = 1.70, 1.60, 8.0, 10.0
    scene = {
        "canvas": {"w_px": 540, "h_px": 960},
        "reference": {"name": "玄奘", "real_m": XZ_M, "px": 170.0},
        "baseline_y": 700,
        "objects": [
            {"name": "玄奘", "real_m": XZ_M, "pivot": "bottom_center", "on_ground": True},
            {"name": "马", "real_m": HORSE_M, "real_w_m": 2.2, "pivot": "bottom_center", "on_ground": True},
            {"name": "城门洞", "real_m": GATE_M, "real_w_m": 5.35, "pivot": "bottom_center", "on_ground": True},
            {"name": "城头旗", "real_m": 0.90, "real_w_m": 0.30, "pivot": "top_center", "anchor_y_px": 120},
            {"name": "胡杨", "real_m": POP_M, "pivot": "bottom_center", "on_ground": True},
        ],
    }

    print("[scale_map self_check]")
    smap = build_scale_map(scene)
    print("  px_per_m = %.2f  基线 y=%d" % (smap["px_per_m"], smap["baseline_y"]))

    # 1 命名参照物唯一：所有物体像素必须由它推出
    ppm = smap["px_per_m"]
    derived = {o["name"]: round(o["target_h_px"] / o["real_m"], 4) for o in smap["objects"]}
    ck("1 所有部件 px_per_m 同源", max(abs(v - ppm) for v in derived.values()) < 1e-3,
       "离散 %.4f" % max(abs(v - ppm) for v in derived.values()))

    # 2 落地物底边全部贴 baseline（业界：feet on y=82 防弹跳）
    ground = [o for o in smap["objects"] if o["on_ground"]]
    ck("2 站立物共用地平线", len({round(o["box"][1], 1) for o in ground}) == 1,
       "底边集合 %s" % sorted({round(o["box"][1], 1) for o in ground}))

    # 3 比例关系正确（玄奘:城门 = 1:4.71）
    lut = {o["name"]: o for o in smap["objects"]}
    r_gate = lut["城门洞"]["real_m"] / lut["玄奘"]["real_m"]
    ck("3 玄奘:城门=1:4.71", abs(r_gate - 8.0 / 1.70) < 1e-6, "%.3f" % r_gate)

    # 4 旗帜不再失调：0.9m 旗应远小于 8m 城门
    r_flag = lut["城头旗"]["target_h_px"] / lut["城门洞"]["target_h_px"]
    ck("4 旗/城门 像素比 = 0.9/8", abs(r_flag - 0.9 / 8.0) < 1e-6, "%.4f" % r_flag)

    # 5 verify 能拦住 2.3 倍失调（本轮真实 bug）
    bad = [{"name": "城头旗", "h_px": lut["城头旗"]["target_h_px"] * 2.3}]
    ok_bad, rep = verify(smap, bad)
    ck("5 2.3倍失调被拦截", (not ok_bad) and "suggest_scale" in rep[0],
       "建议缩放 %.3f" % rep[0].get("suggest_scale", 0))

    # 6 verify 放行正确尺寸
    good = [{"name": "城头旗", "h_px": lut["城头旗"]["target_h_px"]}]
    ok_good, _ = verify(smap, good)
    ck("6 正确尺寸放行", ok_good)

    # 7 缺槽必须报错（铁律31）
    threw = False
    try:
        build_scale_map({"canvas": {"w_px": 1, "h_px": 1}, "reference": {"name": "x", "real_m": 1.0},
                         "baseline_y": 1, "objects": [{"real_m": 1.0}]})
    except KeyError:
        threw = True
    ck("7 缺 name 槽即报错", threw)

    # 8 落地物 pivot 非 bottom_center 必须报错
    threw2 = False
    try:
        build_scale_map({"canvas": {"w_px": 1, "h_px": 1},
                         "reference": {"name": "x", "real_m": 1.0, "px": 100.0},
                         "baseline_y": 10,
                         "objects": [{"name": "a", "real_m": 1.0, "on_ground": True,
                                      "pivot": "top_center", "anchor_y_px": 5}]})
    except ValueError:
        threw2 = True
    ck("8 落地物 pivot 错误即报错", threw2)

    # 9 prompt_block 必须含米制与地平线（铁律65）
    pb = prompt_block(smap)
    ck("9 提示块含 px_per_m/地平线/米数",
       ("px_per_m" in pb) and ("地平线" in pb) and ("%.2f" % XZ_M in pb))

    # 10 证伪：换参照物，全图尺度必须整体变化（证明不是写死）
    s2 = build_scale_map({**scene, "reference": {"name": "城门洞", "real_m": GATE_M, "px": 400.0}})
    ck("10 换参照物整体缩放", abs(s2["px_per_m"] - 50.0) < 1e-6,
       "%.1f vs %.1f" % (s2["px_per_m"], ppm))

    print("  -> %s" % ("PASS" if not fails else "FAIL %s" % fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    raise SystemExit(self_check())
