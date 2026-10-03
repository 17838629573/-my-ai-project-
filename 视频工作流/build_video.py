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

    # 5 周期与步态时间
    T_FLAG = BPT.flag_period_s(spec)
    gt = BPT.gait_time(spec)
    dur_f, dur_m = BPT.durations(T_FLAG, gt["cycle"])
    print(f"[5] 旗周期={T_FLAG:.3f}s  步态: speed={gt['speed']}m/s "
          f"stride={gt['stride']}m cycle={gt['cycle']:.3f}s "
          f"cadence={120/gt['cycle']:.0f}步/分")

    # 6 素材
    flag_frames = BPA.load_flag_sheet(px_per_m)
    man_frames = BPA.load_man_sheet(px_per_m)
    _t = BPA.load_tree(px_per_m)
    tree_frame, has_tree = (_t[0], _t[1]) if _t else (None, False)
    print(f"[6] 旗{len(flag_frames)}帧 人{len(man_frames)}帧 树素材={has_tree}")

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
        "flag_xy": _flag_xy(spec, bg, H),
        "total": 8.0,
    })


def _flag_xy(spec, bg, H):
    """旗落点由 _surface 按墙顶算出，禁用默认地面兜底（铁律31）。"""
    import _surface as SF
    a = SF.anchors_from_scene(spec, bg, int(H))
    for nm, p in a["anchors"].items():
        if SF._surface_kind(nm, spec) == "flag":
            print("[落点] %s -> (%.1f, %.1f) 地平线y=%.1f 相机高%.3fm（代码算）"
                  % (nm, p[0], p[1], a["horizon_y"], a["h_cam"]))
            return (float(p[0]), float(p[1]))
    raise SystemExit("[落点] 场景里没有旗/幡类物体，禁默认")


if __name__ == "__main__":
    main()
