#!/usr/bin/env python3
"""出片前置：基线探测 + 比例尺 + 路径校验。
依赖: groundline scale_map path path_align wind_response cloth_wire _px
被依赖: build_video
改前必读: IMPROVE_build_video.md
铁律: T84 落位走 placement 禁手填 baseline / T98 基线须落在可行走面
      T96 路径控制点越界即报错 / T86 px_per_m 唯一口径禁重算
"""
import json
import numpy as np
import groundline as GL
import scale_map as SM
import path as PA
import path_align as PAL
import cloth_wire as CW
from wind_response import wind_response as _wr
from _px import to_px
from build_util import _need

W_DIR_DEFAULT = 1.0   # 风向：+1 向右（左->右），-1 向左


def setup_baseline(bg, spec, W):
    """基线：探测后必须校验落在可行走面上（铁律98）。
    探测值非地面时回退 spec 声明值；两者皆非地面则报错，禁静默降级。"""
    gl = GL.detect(bg)
    cand = int(gl["baseline_y"])
    ok, score = PAL.is_ground_patch(bg, W // 2, cand)
    if ok:
        print(f"[1] 基线探测 y={cand} (置信度{gl['confidence']:.2f}) "
              f"地面校验通过 score={score:.2f}")
        return cand
    declared = int(spec.get("scale", {}).get("baseline_y", 0))
    ok2, s2 = PAL.is_ground_patch(bg, W // 2, declared) if declared else (False, 0.0)
    if not ok2:
        raise SystemExit(
            f"铁律98违规：探测基线 y={cand} 非地面(score={score:.2f})，"
            f"且 spec 声明 baseline_y={declared} 亦未通过地面校验(score={s2:.2f})。"
            f"请重新声明 scale.baseline_y 落在画面可行走面上。")
    print(f"[1] 基线：探测 y={cand} 非地面(score={score:.2f})，"
          f"采用 spec 声明 y={declared} (score={s2:.2f})")
    return declared


def setup_scale(spec, baseline_y, wind_dir=W_DIR_DEFAULT):
    """比例尺 + 风响应。px_per_m 由 scale_map 唯一给出（铁律86），此处禁重算。
    衣摆幅值由布料气动比算出（铁律102 禁写死 amp_scale）。"""
    sc = dict(spec["scale"])
    sc["baseline_y"] = baseline_y
    smap = SM.build_scale_map(sc)
    px_per_m = float(smap["px_per_m"])
    _ref = smap.get("reference", {})
    print(f"[2] px_per_m={px_per_m:.3f} (参照物 {_ref.get('name','?')} "
          f"{_ref.get('real_m','?')}m = {_ref.get('px','?')}px)")
    U = float(spec["wind"]["U"])
    wr_gar = _wr("garment", 0.35, U)
    gar = CW.garment_amp_m(
        {"family": "cloth", "name": "僧衣衣摆",
         "garment": {"area_m2": 0.30, "mass_kg": 0.25,
                     "normal": [1.0, 0.0]}},
        (U * wind_dir, 0.0), family="garment", L_char_m=0.35)
    wr_gar = dict(wr_gar, amp_m=gar["amp_m"])
    wr_leaf = _wr("leaf", 0.08, U)
    print(f"[2b] 风响应 U={U:.1f}: 衣摆 f={wr_gar['freq_hz']:.2f}Hz "
          f"A={to_px(wr_gar['amp_m'], px_per_m):.1f}px "
          f"摆角={gar['swing_deg']:.1f}° 吹飞={gar['blow_off']} | "
          f"叶 f={wr_leaf['freq_hz']:.2f}Hz")
    return {"px_per_m": px_per_m, "smap": smap, "U": U,
            "wr_gar": wr_gar, "wr_leaf": wr_leaf}


def setup_path(spec, bg, W, H, px_per_m):
    """路径：AI 声明控制点，代码不猜。越界报错（铁律96），
    未落在可行走面报错（铁律98）。"""
    pcfg = spec["path"]
    pts = [tuple(map(float, p)) for p in pcfg["pts"]]
    pts = PAL.normalize_pts(pts, W, H)
    vp = PAL.validate_path(pts, bg)
    if not vp["ok"]:
        raise SystemExit(f"铁律98违规：路径未落在可行走面上 偏差率{vp['rate']:.2f} "
                         f"不通过点={vp['fails'][:6]} 请重声明 path.pts")
    hw_px = float(pcfg["half_width_m"]) * px_per_m
    table = PA.arc_table(pts)
    print(f"[3] 路径 {len(pts)}控制点 全长{table['total']:.0f}px 半宽{hw_px:.0f}px")
    return {"pts": pts, "table": table, "hw_px": hw_px,
            "total_s": table["total"], "pcfg": pcfg}
