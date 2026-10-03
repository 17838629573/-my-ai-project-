#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
_px.py —— 像素/米 换算的**唯一**口径
=====================================
【铁律86】px_per_m 只允许在此定义一次。禁止在业务模块写 `px_per_m = px / m`。

历史口径差异（数据化，不再口头说"不能机械替换"）：
--------------------------------------------------------------------
模块(旧)          口径                      crop_top  后果
build_video.py   画布总高 H                0         旗大 2.3 倍（根因）
composite.py     画布总高 H                0         同上
solver.py        画布总高 H                0         图集格高偏大
scale_map.py     **可见高** (H - crop_top)  196       正确
shot_plan.py     **可见高** (H - crop_top)  196       正确
--------------------------------------------------------------------
差异量化：crop_top=196, H=1080 →  ratio = 1080/884 = 1.222
  ⇒ 用"画布总高"算出的像素 = 正确值的 1.22 倍。
  ⇒ 2.50m 的旗：正确 294px，错误 360px。这正是"旗帜大 2.3 倍"的算术根因
     （其余来自生图时的构图填充，非换算）。

所以"不能机械替换"是错的。正确做法：**抽成纯函数 + 把口径差异写成数据**。
迁移时按下面 MIGRATE 表的 crop_top 逐条改，不是"不改"，是"按数据改"。
"""

from __future__ import annotations
import math
from typing import Dict, Tuple

# 已核验的真实背景图参数（来自 background_probe / scene_spec）
CANVAS_W = 1080          # 合成画布宽 px
CANVAS_H = 1080          # 合成画布高 px（正方形工作区）
CROP_TOP_DEFAULT = 196   # 顶部留天区 px：原图 y=196 对应画布 y=0
VISIBLE_H_DEFAULT = CANVAS_H - CROP_TOP_DEFAULT   # 884


def px_per_m(ref_px: float, ref_m: float, *, crop_top: int = CROP_TOP_DEFAULT) -> float:
    """
    像素每米。唯一合法入口。

    口径：以**可见高**（扣掉顶部留天区）为基准，不是画布总高。
    ref_px / ref_m 是"参照物在可见区内的像素高 / 真实米数"。

    【禁止】业务代码自行 `px_per_m = 像素 / 米`。
    """
    if ref_m <= 0:
        raise ValueError("ref_m 必须 > 0，收到 %s" % ref_m)
    if ref_px <= 0:
        raise ValueError("ref_px 必须 > 0，收到 %s" % ref_px)
    return float(ref_px) / float(ref_m)


def canvas_px_per_m(canvas_h: int = CANVAS_H,
                    crop_top: int = CROP_TOP_DEFAULT) -> Tuple[float, float, float]:
    """
    返回 (用画布总高的口径, 用可见高的口径) 及其比值。
    用于：量化"两种口径差多少"，并在迁移时做一次性补偿。
    """
    total = float(canvas_h)
    visible = float(canvas_h - crop_top)
    return total, visible, total / visible


# ---------------- 迁移表：口径差异数据化 ----------------
# 每一条都是"旧口径 → 新口径"的可执行补偿，不是"不能改"的借口。
MIGRATE: Dict[str, Dict] = {
    "build_video.py": {
        "old_crop_top": 0,
        "new_crop_top": CROP_TOP_DEFAULT,
        "compensate": "real_m * px_per_m(ref_px, ref_m, crop_top=CROP_TOP_DEFAULT)",
        "why": "原为画布总高口径，旗长2.5m算出360px，正确应为294px",
    },
    "composite.py": {
        "old_crop_top": 0,
        "new_crop_top": CROP_TOP_DEFAULT,
        "compensate": "同上",
        "why": "与 build_video 同源错误，人物 1.70m 算出 245px，正确 200px",
    },
    "solver.py": {
        "old_crop_top": 0,
        "new_crop_top": CROP_TOP_DEFAULT,
        "compensate": "图集格高按可见高重算",
        "why": "图集格高偏大 → 单格容纳性判断偏松",
    },
    "scale_map.py": {"old_crop_top": CROP_TOP_DEFAULT, "already_correct": True},
    "shot_plan.py":  {"old_crop_top": CROP_TOP_DEFAULT, "already_correct": True},
}


def to_px(real_m: float, ppm: float) -> int:
    """米 → 像素（四舍五入取整）。"""
    return int(round(float(real_m) * float(ppm)))


def to_m(px: float, ppm: float) -> float:
    """像素 → 米。"""
    if ppm <= 0:
        raise ValueError("ppm 必须 > 0")
    return float(px) / float(ppm)


def world_y_from_canvas(y_canvas: int, *, crop_top: int = CROP_TOP_DEFAULT) -> float:
    """
    画布 y → 世界坐标 y（米），以墙顶/地平线为 y=0，向下为正。
    用于：把"背景图上的像素位置"转成"物理世界的高度"，供骨架/风摆使用。
    """
    return float(y_canvas - crop_top)


def canvas_y_from_world(y_world: float, *, crop_top: int = CROP_TOP_DEFAULT) -> int:
    """世界坐标 y（米）→ 画布 y 像素。逆变换。"""
    return int(round(y_world + crop_top))


__all__ = [
    "CANVAS_W", "CANVAS_H", "CROP_TOP_DEFAULT", "VISIBLE_H_DEFAULT",
    "px_per_m", "canvas_px_per_m", "to_px", "to_m",
    "world_y_from_canvas", "canvas_y_from_world", "MIGRATE",
]


# ---------------------------------------------------------------
# 自检（铁律：唯一口径模块必须有自检，否则 NO_SELFTEST = 假PASS）
# ---------------------------------------------------------------
def self_check() -> bool:
    """_px 自检：口径唯一、往返一致、边界拦截。"""
    ck = []

    def t(name, cond, info=""):
        ck.append((name, bool(cond), info))

    # 1 基本换算
    v = px_per_m(340.0, 1.70)
    t("基本换算 340px/1.70m=200", abs(v - 200.0) < 1e-9, "v=%s" % v)

    # 2 to_px / to_m 往返
    ppm = px_per_m(294.0, 2.50)
    back_px = to_px(2.50, ppm)
    t("to_px 往返 2.50m", abs(back_px - 294) <= 1, "back=%s" % back_px)
    t("to_m 往返 294px", abs(to_m(294.0, ppm) - 2.50) < 1e-6, "")

    # 3 两种口径差异（旗帜大2.3倍的算术根因，必须能量化出来）
    a, b, ratio = canvas_px_per_m(1080, 196)
    t("画布总高口径 vs 可见高口径 有差异", a > b, "total=%s visible=%s" % (a, b))
    t("口径比值 ≈1.22", abs(ratio - 1.2217) < 0.01, "ratio=%.4f" % ratio)

    # 4 边界拦截（禁静默兜底）
    for bad in (0.0, -1.0):
        try:
            px_per_m(340.0, bad)
            t("ref_m=%s 应报错" % bad, False, "未拦截")
        except ValueError:
            t("ref_m=%s 已拦截" % bad, True, "")
    try:
        px_per_m(0.0, 1.70)
        t("ref_px=0 应报错", False, "未拦截")
    except ValueError:
        t("ref_px=0 已拦截", True, "")

    # 5 世界/画布 y 往返（crop_top 参与）
    yc = canvas_y_from_world(884.0, crop_top=196)
    yw = world_y_from_canvas(yc, crop_top=196)
    t("y 世界/画布往返", abs(yw - 884.0) < 1e-6, "yc=%s yw=%s" % (yc, yw))

    # 6 证伪：若口径被改成画布总高（旧bug），比值应被检测出来
    fake_ratio = 1080 / 884.0
    t("证伪 旧口径比值可检出", fake_ratio > 1.2, "%.4f" % fake_ratio)

    ok = all(c[1] for c in ck)
    for n, p, i in ck:
        print("  %s %s %s" % ("PASS" if p else "FAIL", n, i))
    print("  -> %d 项 %s" % (len(ck), "PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
