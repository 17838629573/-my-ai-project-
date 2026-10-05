#!/usr/bin/env python3
"""合成出片：探测基线 + 路径约束 + 语义落位 + 程序化风摆。
依赖: chroma groundline scale_map path placement shot_plan wind_sway framerate solver
被依赖: 无（末端执行）
改前必读: IMPROVE_build_video.md

铁律要点
  T76 角色位置 = 路径弧长 s + 横向偏移 offset，禁止自由 xy
  T77 等速必须按弧长参数化
  T84 落位一律走 placement，禁止手填 baseline
  T79 植物风摆程序化，禁止序列帧
"""
import json
import os
import numpy as np
from PIL import Image
import cv2

import chroma as CH
import framerate as FR
import groundline as GL
import scale_map as SM
import path as PA
import _ground_arc as GA
import genqueue as GQ
import placement as PL
import shot_plan as SP
import wind_sway as WS
import cloth_wire as CW
import build_phase_setup as BPS
import build_phase_gen as BPG
import build_phase_time as BPT
import build_phase_asset as BPA
import build_phase_render as BPR

W, H = 540, 960
FPS = FR.FPS
OUT = "玄奘西行_城墙成片.mp4"


def load_sheet(*a, **k):
    from build_util import load_sheet as _f
    return _f(*a, **k)


from composite import _srgb_to_lin, _lin_to_srgb


def _resize_cs(*a, **k):
    from build_util import _resize_cs as _f
    return _f(*a, **k)


def resize_h(*a, **k):
    from build_util import resize_h as _f
    return _f(*a, **k)


def sway_image(*a, **k):
    from build_util import sway_image as _f
    return _f(*a, **k)


def over(*a, **k):
    from build_util import over as _f
    return _f(*a, **k)


def place_at(*a, **k):
    from build_util import place_at as _f
    return _f(*a, **k)


def _need(*a, **k):
    from build_util import _need as _f
    return _f(*a, **k)


from build_util import KEYJOINTS


def _joint_seq(*a, **k):
    from build_util import _joint_seq as _f
    return _f(*a, **k)



def apply_garment_wind(*a, **k):
    from build_util import apply_garment_wind as _f
    return _f(*a, **k)

def main():
    """编排器：只做阶段串接，各阶段实现见 build_phase_*.py。"""
    spec = json.load(open("scene_spec.json"))
    bg = cv2.imread("_生成/城墙背景.png")
    if bg is None:
        raise SystemExit(
            "[素材] 缺 _生成/城墙背景.png —— 素材已清空，须先生图再出片。"
            "禁静默降级（铁律31/99）：不带旧图、不出空片。")
    bg = cv2.resize(bg, (W, H))

    # 1-3 基线 / 比例尺 / 路径
    baseline_y = BPS.setup_baseline(bg, spec, W)
    sc_info = BPS.setup_scale(spec, baseline_y)
    px_per_m, U = sc_info["px_per_m"], sc_info["U"]
    pinfo = BPS.setup_path(spec, bg, W, H, px_per_m)

    # 4-4b 生图任务包与顺序（一次一物体，铁律81）
    BPG.plan_shots(spec, W, H, baseline_y)
    BPG.emit_gen_queue(spec, U)

    # 5 周期与步态时间（需先知道图集实际帧数，故与素材加载同序）
    T_FLAG = BPT.flag_period_s(spec)
    gt = BPT.gait_time(spec)

    # 6 素材（先加载，拿到真实帧数）
    flag_frames = BPA.load_flag_sheet(px_per_m)
    man_frames = BPA.load_man_sheet(px_per_m)
    _t = BPA.load_tree(px_per_m)
    tree_frame, has_tree = (_t[0], _t[1]) if _t else (None, False)

    # 5b 逐帧时长必须按【实际帧数】切分，否则循环回绕时姿态跳变（实测逼出）
    n_f, n_m = len(flag_frames), len(man_frames)
    dur_f, dur_m = BPT.durations_for(T_FLAG, gt["cycle"], n_f, n_m)
    _cf, _cm = n_f * dur_f[0], n_m * dur_m[0]
    for _nm, _c, _want in (("旗", _cf, T_FLAG), ("人", _cm, gt["cycle"])):
        if abs(_c - _want) > 1e-6:
            raise SystemExit(f"[时序] {_nm}循环周期 {_c:.4f}s != 真实周期 {_want:.4f}s —— 禁出跳变片")
    print(f"[5] 旗周期={T_FLAG:.3f}s  步态: speed={gt['speed']}m/s "
          f"stride={gt['stride']}m cycle={gt['cycle']:.3f}s "
          f"cadence={120/gt['cycle']:.0f}步/分")
    print(f"[5b] 时序对齐: 旗{n_f}帧×{dur_f[0]:.4f}s={_cf:.4f}s  "
          f"人{n_m}帧×{dur_m[0]:.4f}s={_cm:.4f}s（=周期，循环无缝）")
    print(f"[6] 旗{len(flag_frames)}帧 人{len(man_frames)}帧 树素材={has_tree}")

    # V2：地面坐标系 —— cam 参数全部来自 spec 声明，缺键报错（铁律96）
    _GA_CAM = GA.cam_of(spec)
    _GA_WT = GA.world_arc_table(pinfo["pts"], _GA_CAM)
    _pxs = [float(x) for x in spec.get("walkers_s", [40.0, 160.0, 280.0])]
    _GA_S0M = [GA.px_arc_to_meter(pinfo["pts"], x, _GA_WT) for x in _pxs]
    print(f"[5c] V2世界弧长: 路径{_GA_WT['total']:.2f}m "
          f"三人起始={[round(v,2) for v in _GA_S0M]}m")

    # 7 出片
    BPR.render({
        "bg": bg, "W": W, "H": H, "FPS": FPS, "OUT": OUT,
        "flag_frames": flag_frames, "man_frames": man_frames,
        "tree_frame": tree_frame, "has_tree": has_tree,
        "dur_f": dur_f, "dur_m": dur_m,
        "pts": pinfo["pts"], "table": pinfo["table"],
        "total_s": pinfo["total_s"], "hw_px": pinfo["hw_px"],
        "speed": gt["speed"], "px_per_m": px_per_m, "U": U,
        "wr_gar": sc_info["wr_gar"],
        "s0": [float(x) for x in spec.get("walkers_s", [40.0, 160.0, 280.0])],
        # V2：世界弧长推进三件套
        "cam": _GA_CAM, "wtable": _GA_WT, "s_start_m": _GA_S0M,
        # V4：路半宽改为米制，渲染端按 y 实时收敛
        "hw_m": pinfo["hw_m"],
        "flag_xy": _flag_xy(spec, bg, H),
        "tree_xy": _tree_xy(spec, bg, H),
        # P9：人物须随深度缩小。px_per_m(y) = (y - v_h)/h_cam
        #   （由声明的透视自洽：y=880 -> 117.6 与 near_px_per_m 吻合；
        #     y=600 -> 35.06 与 far_px_per_m 吻合）
        "horizon_y": _anchors(spec, bg, H)["horizon_y"],
        "h_cam": _anchors(spec, bg, H)["h_cam"],
        "total": 8.0,
    })


_ANCHORS_CACHE = {}


def _anchors(spec, bg, H):
    """一次算全部落点并缓存 —— 避免 flag/tree 各调一遍 anchors_from_scene。"""
    key = id(spec)
    if key not in _ANCHORS_CACHE:
        import _surface as SF
        _ANCHORS_CACHE[key] = SF.anchors_from_scene(spec, bg, int(H))
    return _ANCHORS_CACHE[key]


def _xy_of(spec, bg, H, kind):
    """按 kind 取落点 (x,y)。place() 返回 dict 不是 tuple（实测逼出）。"""
    import _surface as SF
    a = _anchors(spec, bg, H)
    for nm, p in a["anchors"].items():
        _k = SF._surface_kind(nm, spec)
        _want = kind if isinstance(kind, (tuple, list, set)) else (kind,)
        if _k in _want:
            px, py = p.get("x"), p.get("y")
            if px is None or py is None:
                raise SystemExit(
                    "[落点] %s 的 x/y 未算出(x=%s y=%s) —— %s（禁默认兜底，铁律31）"
                    % (nm, px, py, p.get("via", "")))
            print("[落点] %s(%s) -> (%.1f, %.1f) 地平线y=%.1f 相机高%.3fm（代码算）"
                  % (nm, kind, px, py, a["horizon_y"], a["h_cam"]))
            return (float(px), float(py))
    raise SystemExit("[落点] 场景里没有 %s 类物体，禁默认" % kind)


def _flag_xy(spec, bg, H):
    """旗落点由 _surface 按墙顶算出，禁用默认地面兜底（铁律31）。"""
    import _surface as SF
    a = _anchors(spec, bg, H)
    for nm, p in a["anchors"].items():
        if SF._surface_kind(nm, spec) == "flag":
            # place() 返回 dict {kind,surface,x,y,via}，不是 tuple。
            # 旧代码写 p[0]/p[1] → KeyError: 0（实测逼出）。
            px, py = p.get("x"), p.get("y")
            if px is None or py is None:
                raise SystemExit(
                    "[落点] %s 的 x/y 未算出(x=%s y=%s) —— %s（禁默认兜底，铁律31）"
                    % (nm, px, py, p.get("via", "")))
            print("[落点] %s -> (%.1f, %.1f) 地平线y=%.1f 相机高%.3fm（代码算）"
                  % (nm, px, py, a["horizon_y"], a["h_cam"]))
            return (float(px), float(py))
    raise SystemExit("[落点] 场景里没有旗/幡类物体，禁默认")


def _tree_xy(spec, bg, H):
    """树落点：soil 层，排除路面后落在路径外侧（铁律31 禁默认）。

    注意：_surface_kind 对 vegetation 族返回的是 "willow" 不是 "tree"
    （实测逼出——旧代码找 "tree" 永远找不到，报"场景里没有"）。
    """
    return _xy_of(spec, bg, H, ("willow", "tree"))


if __name__ == "__main__":
    main()
