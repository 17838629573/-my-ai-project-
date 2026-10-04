#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
规则驱动放置（rule-based placement）—— 禁硬编码坐标。

业界依据：
  [1] Bao & Savarese CVPR2010: 物体必须躺在支撑面上，且物体法线必须平行于
      支撑面法线（n1 // n）；不平行者不可能坐落于该面。
  [2] Footprints CVPR2020: 可行走面 = 语义类 mask S + 深度图 D。
  [3] Houdini/UE 程序化散布: slope filter / height band / density mask
      / exclusion volume / clustering —— 落点是规则算出的，不是填的。

本模块只做"物体该落在哪个表面、落点在哪"；像素落位交 placement.py。

契约: contracts/surface.md
改前必读: IMPROVE_surface.md
"""

import param_decl as PD
from _perspective import (y_at_depth, object_px_height, scale_field,
                          depth_at, focal_px)

__all__ = ["SURFACE_CLASSES", "RULES", "NORMAL", "surface_at",
           "wall_top_y", "ground_y_at_depth", "offset_outside_path",
           "place", "self_check"]

# 表面层（语义类，对齐 ADE20K：wall / sky / road / earth / plant）
SURFACE_CLASSES = ("sky", "far", "wall_face", "wall_top", "path", "soil")

# 各层外法线方向（世界坐标）。地面朝上，墙面水平。
NORMAL = {
    "sky": None, "far": None,
    "wall_face": "horizontal",   # 垂直面：法线水平 → 站不住直立物
    "wall_top": "up",            # 墙顶面：法线朝上 → 可立
    "path": "up",
    "soil": "up",
}

# 规则：物体种类 → 可落层 + 排除层 + 是否需直立（法线平行）
RULES = {
    "tree":      {"layers": ("soil",), "exclude": ("path", "wall_face"),
                  "upright": True, "why": "树根系须入土，且路径上不可能有树"},
    "flag":      {"layers": ("wall_top",), "exclude": ("soil",),
                  "upright": True, "why": "城头旗插在墙顶，不是插在地里"},
    "person":    {"layers": ("path", "soil"), "exclude": ("wall_face",),
                  "upright": True, "why": "人在可行走面上"},
    "willow":    {"layers": ("soil",), "exclude": ("path", "wall_face"),
                  "upright": True, "why": "旱柳属树，同 tree"},
    "banner":    {"layers": ("wall_top",), "exclude": ("soil",),
                  "upright": True, "why": "幡同旗"},
    "cart":      {"layers": ("path",), "exclude": ("soil", "wall_face"),
                  "upright": True, "why": "车在道上，不在田里"},
}


def _rule(kind):
    if kind not in RULES:
        raise ValueError(
            "未知放置种类 %r；已登记: %s —— 新种类须先补 RULES（铁律31）"
            % (kind, sorted(RULES)))
    return RULES[kind]


def surface_at(y, v_h):
    """屏幕行 y 属于哪个表面层（纯几何：地平线是硬分界）。

    地平线以上不可能是可行走面（业界[2]：地平线以上无地面交点）。
    """
    if v_h is None:
        raise ValueError("缺地平线 v_h：须由消失点算出，禁手填（铁律31）")
    return "sky" if y < v_h else "ground_candidate"


from _wall_geom import wall_top_y, wall_depth_for_top  # noqa: F401  (拆分见 _wall_geom.py)

def ground_y_at_depth(z_m, v_h, f_px, h_cam):
    """深度 z 处地面的屏幕行 y。地面是 Z 平面，直接由透视反解。"""
    return y_at_depth(z_m, v_h, f_px, h_cam)


def offset_outside_path(path_center_x_px, path_half_w_m, clear_m,
                        side, px_per_m):
    """排除区（exclusion volume）：物体须离路径边缘 clear_m 以外。

    side: -1 左侧 / +1 右侧。返回物体中心的屏幕 x。
    """
    if side not in (-1, 1):
        raise ValueError("side 须为 -1 或 +1")
    edge_x = path_center_x_px + side * path_half_w_m * px_per_m
    return edge_x + side * clear_m * px_per_m


def place(kind, v_h, f_px, h_cam, *, z_m=None, h_wall_m=None, image_h=None,
          path_center_x_px=None, path_half_w_m=None, clear_m=None,
          side=-1):
    """综合落点：按规则选表面 → 算落点 (x, y)。全程无手填坐标。

    tree/willow  → 地面(soil)，且排除路径 → 落在路径外侧 clear_m
    flag/banner  → 墙顶(wall_top)，y 由墙高经透视算出
    person/cart  → 路径上
    """
    r = _rule(kind)
    layers = r["layers"]

    # 法线平行性判定（业界[1]）：直立物必须落在法线朝上的面上
    if r["upright"] and not any(NORMAL.get(L) == "up" for L in layers):
        raise ValueError(
            "%s 要求直立，但可落层 %s 的法线均非朝上 —— 违反支撑面法线平行(业界[1])"
            % (kind, layers))

    if "wall_top" in layers:
        if h_wall_m is None:
            h_wall_m = PD.require(
                "wall_height_m", "architecture",
                "墙顶落点须由墙的真实高度经透视算出，不能手填 y 坐标",
                unit_hint="m", hint="古城墙/城墙的实测高度，给来源与常见区间")
        y = wall_top_y(h_wall_m, z_m, v_h, f_px, h_cam, image_h)
        x = path_center_x_px if path_center_x_px is not None else None
        return {"kind": kind, "surface": "wall_top", "x": x, "y": y,
                "via": "wall_top_y(h_wall=%.2fm, z=%.1fm)" % (h_wall_m, z_m)}

    if "soil" in layers:
        y = ground_y_at_depth(z_m, v_h, f_px, h_cam)
        # 仅当该种类「禁止落在路径上」（树类）时才需要排除区；
        # 人/车可落在路径上，不应被树的排除区要求挡住。
        if "path" in r["exclude"]:
            if path_center_x_px is None or path_half_w_m is None:
                raise ValueError(
                    "soil 放树须给 path_center_x_px/path_half_w_m 以算排除区；"
                    "否则无法保证树不在路面上（铁律31）")
            if clear_m is None:
                raise ValueError("缺 clear_m：树离路缘的净距(m)，须声明")
            x = offset_outside_path(path_center_x_px, path_half_w_m,
                                    clear_m, side, scale_field(y, v_h, h_cam))
            via = "offset_outside_path(clear=%.1fm)" % clear_m
        else:
            x = path_center_x_px
            via = "ground_y_at_depth(z=%.1fm)" % z_m
        return {"kind": kind, "surface": "soil", "x": x, "y": y, "via": via}

    y = ground_y_at_depth(z_m, v_h, f_px, h_cam)
    return {"kind": kind, "surface": layers[0], "x": path_center_x_px,
            "y": y, "via": "ground_y_at_depth(z=%.1fm)" % z_m}


def self_check():
    ck = []
    v_h, h_cam, f = 300.0, 3.383, focal_px(960)

    # 1 地平线以上判为 sky —— 树上不了天
    ck.append(("1 地平线以上=sky", surface_at(250, v_h) == "sky"))
    ck.append(("2 地平线以下=地面候选", surface_at(600, v_h) == "ground_candidate"))

    # 3 墙顶高于墙基，且随墙高单调上移
    y1 = wall_top_y(10.0, 30.0, v_h, f, h_cam)
    y2 = wall_top_y(12.0, 30.0, v_h, f, h_cam)
    ck.append(("3 墙越高顶越靠上", y2 < y1))

    # 4 墙顶必须高于同深度地面
    yg = ground_y_at_depth(30.0, v_h, f, h_cam)
    ck.append(("4 墙顶高于地面", y1 < yg))

    # 5 树被排除在路径外（业界 exclusion volume）
    x_l = offset_outside_path(270.0, 1.2, 3.0, -1, 100.0)
    x_r = offset_outside_path(270.0, 1.2, 3.0, +1, 100.0)
    ck.append(("5 树在路缘外侧", x_l < 270.0 - 120.0 and x_r > 270.0 + 120.0))

    # 6 墙面法线水平 → 直立物不可落（这就是"树不能种在墙上"的判据）
    ck.append(("6 墙面法线非朝上", NORMAL["wall_face"] == "horizontal"))
    ck.append(("7 墙顶法线朝上", NORMAL["wall_top"] == "up"))

    # 8 未知种类必须报错，不静默
    try:
        _rule("ufo")
        ck.append(("8 未知种类报错", False))
    except ValueError:
        ck.append(("8 未知种类报错", True))

    # 9 树落在墙面上必须被拒（规则层拦截）
    try:
        place("tree", v_h, f, h_cam, z_m=30.0,
              path_center_x_px=270.0, path_half_w_m=1.2, clear_m=3.0)
        surf_ok = True
    except ValueError:
        surf_ok = False
    ck.append(("9 tree 只落 soil 不落墙", surf_ok))

    # 10 缺 clear_m 必须报错（不静默给默认）
    try:
        place("tree", v_h, f, h_cam, z_m=30.0,
              path_center_x_px=270.0, path_half_w_m=1.2)
        ck.append(("10 缺 clear_m 报错", False))
    except ValueError:
        ck.append(("10 缺 clear_m 报错", True))

    # 11 透视自洽：地面 y 随深度单调（近处靠下）
    ck.append(("11 近处地面更靠下",
               ground_y_at_depth(10.0, v_h, f, h_cam)
               > ground_y_at_depth(50.0, v_h, f, h_cam)))

    # 12 depth_at 与 y_at_depth 互逆
    z = 25.0
    ck.append(("12 深度与屏幕行互逆",
               abs(depth_at(ground_y_at_depth(z, v_h, f, h_cam),
                            v_h, f, h_cam) - z) < 1e-6))

    for name, ok in ck:
        print(("  PASS " if ok else "  FAIL ") + name)
    return all(ok for _, ok in ck)


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)


def _horizon_of(spec):
    """地平线取值：spec 顶层 / path.perspective / scale 三处依次找。

    背景（实测逼出 2026-10-03 城墙场景）：
      场景把 horizon_y 声明在 spec['path']['perspective']['horizon_y']=482，
      而本函数原写 spec.get('horizon_y') 读【顶层】-> None -> 回落 Hough
      消失点反解 -> 得到 588.5。
      后果（几何自检，v_h 错则深度反解为负）：
        v_h=482  : z(y=557.4) = +60.0m  合理
        v_h=588.5: z(y=557.4) = -107m   负数 = 在相机背后 = 不可能
      于是人物走到路径末端就被判为"在地平线以上=天上"。

      旁证：groundline.detect 独立检测 y=479，与声明的 482 吻合，
      说明 482 是真值，588.5 是 Hough 在纹理复杂图上误检。
    """
    for get in (lambda: spec.get("horizon_y"),
                lambda: (spec.get("path") or {}).get("horizon_y"),
                lambda: ((spec.get("path") or {}).get("perspective") or {}).get("horizon_y"),
                lambda: (spec.get("scale") or {}).get("horizon_y")):
        try:
            v = get()
        except Exception:
            v = None
        if v is not None:
            return float(v)
    return None


def anchors_from_scene(spec, bg_bgr, image_h):
    """场景级落点：旗→墙顶，树→地面且退让路径。全程无手填坐标。

    v_h（地平线）优先从背景图消失点反解；取不到就报错，禁静默用默认值
    （旧实现 spec.get('flag_anchor_xy', [90, baseline_y]) 默认落到地面，
     导致旗插在马道上、本该插墙顶）。
    """
    import cv2 as _cv, numpy as _np
    import _perspective as _P
    v_h = _horizon_of(spec)
    if v_h is None:
        if bg_bgr is None:
            raise SystemExit("[落点] 缺 horizon_y 且无背景图，禁默认地面（铁律31）")
        gray = _cv.cvtColor(bg_bgr, _cv.COLOR_BGR2GRAY)
        edges = _cv.Canny(gray, 50, 150)
        lines = _cv.HoughLinesP(edges, 1, _np.pi / 180, 120,
                                minLineLength=250, maxLineGap=20)
        # cv2 版本兼容：HoughLinesP 返回 (N,1,4) 或 (N,4)，两者都要吃下
        segs = []
        if lines is not None:
            arr = _np.asarray(lines).reshape(-1, 4)
            segs = [tuple(int(v) for v in row) for row in arr]
        v_h = _P.horizon_from_vanishing(segs, image_h)
        if v_h is None:
            raise SystemExit("[落点] 背景图消失点不足，无法反解地平线，禁默认")
    f_px = _P.focal_px(image_h)

    ref = spec["scale"]["reference"]
    # baseline_y 在 spec['scale'] 下（scene_spec.json 实际结构），不是顶层
    base_y = float(spec["scale"].get("baseline_y", spec.get("baseline_y")))
    h_cam = _P.camera_height_from_ref(float(ref["real_m"]),
                                      float(ref.get("px_top", base_y - float(ref["px"]))),
                                      base_y, float(v_h))
    wall_h = spec.get("wall_height_m")
    if wall_h is None:
        # 只捕获 AskAI / ParamRejected；不能 except Exception ——
        # 曾因 require() 少传 family/why 抛 TypeError，被宽 except 吞掉，
        # 伪装成"参数缺失"，实际参数已落盘。掩盖真错误的代价是查错链变长。
        import param_decl as PD
        try:
            _r = PD.require(
                "wall_height_m", "architecture",
                "城墙真实高度，用于把墙体落点到透视地面",
                unit_hint="m")
            # verify() 已解包为标量？兼容两种返回形态，别再靠猜
            wall_h = _r["value"] if isinstance(_r, dict) else _r
        except (PD.AskAI, PD.ParamRejected) as e:
            raise SystemExit("[落点] 缺 wall_height_m：先由 AI 搜证落盘 "
                             "params_ai.json（禁默算）\n" + str(e)[:400])
        except TypeError as e:
            raise SystemExit("[落点] require() 调用签名错误（非参数缺失）: %s" % e)
    wall_h = float(wall_h)
    out = {}
    for o in spec["scale"]["objects"]:
        kind = str(_surface_kind(o["name"], spec))
        z = float(o.get("z_m", spec.get("wall_depth_m", 95.0)))
        p = place(kind, float(v_h), f_px, h_cam, z_m=z, h_wall_m=wall_h,
                  image_h=image_h,
                  path_center_x_px=_path_center_x(spec),
                  path_half_w_m=(spec.get("path") or {}).get("half_width_m"),
                  clear_m=float(spec.get("tree_clear_m", 3.0)))
        out[o["name"]] = p
    return {"horizon_y": float(v_h), "h_cam": h_cam, "f_px": f_px,
            "anchors": out}



def _path_center_x(spec):
    """路面中心线 x。

    spec 顶层并没有 path_center_x_px 键（实际在 spec['path']['pts'] 里），
    旧代码取 spec.get(...) 恒为 None，导致铁律31 永远报"须给中心"。
    这里从路径控制点取：近端与远端 x 的中点（单点透视下中心线近似线性）。
    """
    p = (spec.get("path") or {})
    if p.get("center_x_px") is not None:
        return float(p["center_x_px"])
    pts = p.get("pts") or []
    if not pts:
        return None
    xs = [float(pt[0]) for pt in pts]
    return (min(xs) + max(xs)) / 2.0

def _surface_kind(name, spec):
    fams = spec.get("families") or {}
    fam = fams.get(name, "")
    if fam == "vegetation":
        return "willow"
    if "旗" in name or "幡" in name or fam == "cloth":
        return "flag"
    if fam == "biped":
        return "person"
    return "person"
