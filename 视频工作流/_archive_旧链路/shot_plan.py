#!/usr/bin/env python3
"""镜头规划 / 生图任务包：告诉 AI 路画在哪、物体多大、落在哪、提示词怎么写。
依赖: path placement scale_map wind_sway groundline
被依赖: build_video
改前必读: IMPROVE_shot_plan.md
只做规划，不画像素。
"""
import json
import placement as PL
import path as PA
import scale_map as SM
import wind_sway as WS


def _need(d, keys, where):
    miss = [k for k in keys if k not in d]
    if miss:
        raise KeyError(f"{where} 缺槽位 {miss}（铁律31：缺槽即报错，禁静默默认）")
    return [d[k] for k in keys]


def build_scale(scene):
    smap = SM.build_scale_map(scene)
    return smap


def path_hint(pts, half_width_m, px_per_m, persp=None):
    """路径在背景图上的像素提示。pts 为像素控制点。

    persp 必填（铁律31）：{"near_px_per_m", "far_px_per_m"}，
    近端/远端各自的米→像素比。缺则不猜透视，直接报错——
    因为"路面远近一样宽"正是纵深走向被画成水平路的根因。
    """
    if not isinstance(pts, (list, tuple)) or len(pts) < 2:
        raise ValueError("path_hint: 控制点至少 2 个（铁律78：由 AI 声明，代码不猜）")
    if not persp:
        raise KeyError("path_hint 缺 persp（near_px_per_m/far_px_per_m），"
                       "禁静默按无透视处理（铁律31）")
    near_ppm = float(_need(persp, ["near_px_per_m"], "persp")[0])
    far_ppm = float(_need(persp, ["far_px_per_m"], "persp")[0])
    table = PA.arc_table(pts)
    total_px = table["total"]
    a, b = pts[0], pts[-1]
    # 纵深判定：y 变小 = 远离镜头（画面更深处）
    depth = "由近及远" if float(b[1]) < float(a[1]) else (
        "由远及近" if float(b[1]) > float(a[1]) else "纯横向（无纵深）")
    return {
        "pts_px": [list(map(float, p)) for p in pts],
        "half_width_px": float(half_width_m) * float(px_per_m),
        "half_width_m": float(half_width_m),
        "total_px": float(total_px),
        "total_m": float(total_px) / float(px_per_m),
        "near_ppm": near_ppm,
        "far_ppm": far_ppm,
        "near_w_px": float(half_width_m) * 2.0 * near_ppm,
        "far_w_px": float(half_width_m) * 2.0 * far_ppm,
        "shrink_pct": (1.0 - far_ppm / near_ppm) * 100.0,
        "depth": depth,
        "start_px": [float(a[0]), float(a[1])],
        "end_px": [float(b[0]), float(b[1])],
    }


def locate(kind, real_m, anchor_xy, px_per_m, src_shape=None, scale=None):
    """单个物体的落位矩形（铁律84：不手填，一律走 placement.place）。

    src_shape: 源图 (h, w)，缺省按 256 格。scale: 缩放比，缺省按
    target_px/源高 自动算，保证语义点落在 anchor_xy 上。
    """
    target_h = float(real_m) * float(px_per_m)
    ch, cw = (float(src_shape[0]), float(src_shape[1])) if src_shape else (256.0, 256.0)
    reg = {"kind": kind, "canvas_w": cw, "canvas_h": ch}
    s = float(scale) if scale else (target_h / ch)
    tgt = (float(anchor_xy[0]), float(anchor_xy[1]))
    rect = PL.place(reg, tgt, scale=s)
    return {"target_px": target_h, "scale": s, "rect": rect, "regpoint": reg,
            "anchor_px": tgt, "placed_ok": PL.verify(reg, tgt, rect)}


def path_prompt(ph, material="夯土马道"):
    """路面几何提示（铁律97）：必须让 AI 画出"走向 + 纵深透视"。

    旧版只给首末两点 + 单一宽度 → 模型画成水平路，与长城纵深走向不符，
    人物于是走在长城外面。现补齐：全部控制点、由近及远方向、近宽远窄。
    """
    a, b = ph["start_px"], ph["end_px"]
    ctrl = "→".join(f"({p[0]:.0f},{p[1]:.0f})" for p in ph["pts_px"])
    return (f"画面中有一条{material}（城墙顶部的可行走走道，两侧为垛口与墙体），"
            f"自近端坐标({a[0]:.0f},{a[1]:.0f}){ph['depth']}延伸到远端({b[0]:.0f},{b[1]:.0f})，"
            f"控制点依次 {ctrl}；"
            f"路面为单点透视：近端宽约{ph['near_w_px']:.0f}像素，"
            f"向远处收窄到约{ph['far_w_px']:.0f}像素（收缩{ph['shrink_pct']:.0f}%），"
            f"路面全长{ph['total_px']:.0f}像素（约{ph['total_m']:.1f}米），"
            f"路宽{ph['half_width_m']*2:.1f}米。路面只存在于墙顶走道，"
            f"墙体立面与城下地面不得画成路面。")


def obj_prompt(name, real_m, ph, kind, on_path=False):
    """物体落位提示。on_path 默认改为 False（铁律100）：

    旧版默认 True，导致柳树等未声明 on_path 的物体被一律写成"沿路面行走"
    → 树种到长城马道上。现按族判定：只有会行走的族才允许 on_path。
    """
    line = f"{name}：真实高度 {real_m:.2f} 米"
    if on_path:
        line += (f"，沿上述{material_name(ph)}行走，路面宽 {ph['half_width_m']*2:.1f} 米，"
                 f"脚底必须踩在路面上")
    else:
        line += "，不在路面上，落在城下地面上（墙体之外的地面区域）"
    line += "。主体竖直，不要整体倾斜。"
    return line


def material_name(ph):
    return "夯土马道"


_PATH_FAMILIES = ("biped", "quadruped", "rigid")


def on_path_by_family(fam, declared=None):
    """是否允许落在路径上，按族判定（铁律100）。

    草木/布料/静态装饰一律不在路面；只有会行走的族才走路径。
    declared 显式声明时优先，但 vegetation/cloth 强制 False（不允许被声明推翻）。
    """
    if fam in ("vegetation", "cloth"):
        return False
    if declared is None:
        return fam in _PATH_FAMILIES
    return bool(declared)


def plan_shot(bg_shape, scene, objects, families=None):
    """objects: [{name, kind, real_m, on_path, s, offset, anchor_xy}]"""
    H, W = bg_shape[0], bg_shape[1]
    smap = build_scale(scene)
    px_per_m = float(smap["px_per_m"])
    pts = _need(scene, ["path"], "scene")[0]
    if not isinstance(pts, dict):
        raise KeyError("scene['path'] 须为 dict，含 pts/half_width_m/perspective")
    p_pts, p_hw = _need(pts, ["pts", "half_width_m"], "scene.path")
    ph = path_hint(p_pts, p_hw, px_per_m, persp=pts.get("perspective"))

    objs, prompts = [], []
    for o in objects:
        name, kind, real_m = _need(o, ["name", "kind", "real_m"], "objects[]")
        fam = (families or {}).get(name)
        op = on_path_by_family(fam, o.get("on_path"))
        if op:
            s = float(o.get("s", 0.0))
            off = PA.clamp_offset(float(o.get("offset", 0.0)), ph["half_width_px"])
            xy = PA.at_distance(p_pts, s, table=None)["xy"]
            xy = (xy[0] + off, xy[1])
        else:
            xy = tuple(map(float, _need(o, ["anchor_xy"], name)[0]))
        loc = locate(kind, real_m, xy, px_per_m)
        objs.append({"name": name, "kind": kind, "real_m": real_m,
                     "anchor_xy": (float(xy[0]), float(xy[1])), **loc})
        prompts.append(obj_prompt(name, real_m, ph, kind, op))

    return {
        "canvas": [int(W), int(H)],
        "px_per_m": px_per_m,
        "path_hint": ph,
        "objects": objs,
        "prompts": {"background": path_prompt(ph), "objects": prompts},
    }


def self_check():
    ok = True
    print("shot_plan 自检")

    scene = {
        "canvas": {"w_px": 540, "h_px": 960},
        "reference": {"name": "玄奘", "real_m": 1.70, "px": 200},
        "baseline_y": 640,
        "objects": [{"name": "玄奘", "real_m": 1.70, "on_ground": True},
                    {"name": "城头旗", "real_m": 2.50, "anchor_y_px": 640}],
        "path": {"pts": [(60, 700), (240, 690), (480, 705)], "half_width_m": 1.2},
    }
    smap = build_scale(scene)
    px_per_m = float(smap["px_per_m"])
    print(f"  1 px_per_m={px_per_m:.4f} (期望{200/1.70:.4f})")
    ok &= abs(px_per_m - 200.0 / 1.70) < 0.01

    # 2 路径提示
    ph = path_hint(scene["path"]["pts"], scene["path"]["half_width_m"], smap["px_per_m"])
    print(f"  2 路径 total={ph['total_px']:.1f}px/{ph['total_m']:.2f}m 半宽={ph['half_width_px']:.1f}px")
    ok &= ph["total_px"] > 0 and ph["half_width_px"] > 0

    # 3 落位由 placement 算出
    objects = [
        {"name": "玄奘", "kind": "ground_contact", "real_m": 1.70, "on_path": True, "s": 60.0},
        {"name": "城头旗", "kind": "base", "real_m": 2.50, "on_path": False, "anchor_xy": (90.0, 640.0)},
    ]
    plan = plan_shot((960, 540), scene, objects)
    for o in plan["objects"]:
        r = o["rect"]
        e = o["placed_ok"]["err_px"]
        print(f"  3 {o['name']}: target={o['target_px']:.1f}px rect=(x{r['x0']:.1f},y{r['y0']:.1f},{r['w']:.0f}x{r['h']:.0f}) err={e:.4f}px ok={o['placed_ok']['ok']}")
        ok &= bool(o["placed_ok"]["ok"])
        ok &= abs(o["target_px"] - o["real_m"] * plan["px_per_m"]) < 1e-6

    # 4 证伪：手填落位（整体平移 50px）必须被 verify 判不一致（铁律84）
    o0 = plan["objects"][0]
    fake = dict(o0["rect"])
    fake["x0"] = fake["x0"] + 50.0
    bad = PL.verify(o0["regpoint"], o0["anchor_xy"], fake)
    print(f"  4 证伪手填落位: 平移50px 被判不一致={not bad['ok']} (err={bad['err_px']:.2f}px)")
    ok &= (not bad["ok"])

    # 5 提示词含米制（铁律85）
    bgp = plan["prompts"]["background"]
    has_m = all(("米" in p or f"{o['real_m']:.2f}" in p) for p, o in zip(plan["prompts"]["objects"], plan["objects"]))
    print(f"  5 提示词含米制={has_m}  背景提示={bgp[:40]}...")
    ok &= has_m and "米" in bgp

    # 6 偏移钳制生效（铁律76：不可能出界）
    off_big = PA.clamp_offset(9999.0, ph["half_width_px"])
    print(f"  6 偏移钳制: 9999 -> {off_big:.1f} (半宽{ph['half_width_px']:.1f})")
    ok &= off_big <= ph["half_width_px"] + 1e-9

    print(f"shot_plan: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(self_check())
