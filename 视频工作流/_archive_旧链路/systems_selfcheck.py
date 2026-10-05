"""systems 的自检/检查逻辑（由 _extract_tool.py 从 systems.py 抽出）

改前必读: IMPROVE_systems.md
"""
import math
import os
import sys
import cv2
import numpy as np
from skeleton_runtime import Skeleton, apply_animation, mat_apply
import physics as ph
import physics_rules as pr
import framerate
from framerate import FPS
import re as _re

def self_check():
    from systems import CADENCE_SPM, COM_V_RATIO, Ctx, REAL_HEIGHT_M, STEP_LENGTH_M, _INLINE_PAT, _MAGIC_PAT, init_physics, update_animation, update_composite, update_physics, update_subtitle
    """只读自检 + 最小 Ctx 冒烟，不渲染。返回 (ok, 项数)"""
    ok = True
    n = 0
    here = os.path.join(os.path.dirname(os.path.abspath(__file__)), "systems.py")
    src = open(here, encoding="utf-8").read()
    # 只扫【真实代码】：注释与 docstring 里的示例数值不是违规（否则自检自指误报）
    import tokenize as _tk, io as _io
    code_only = []
    for tk in _tk.generate_tokens(_io.StringIO(src).readline):
        if tk.type in (_tk.COMMENT, _tk.STRING):
            continue
        code_only.append((tk.start[0], tk.string))
    code_src = "\n".join("%d %s" % (ln, t) for ln, t in code_only)

    # 1) 铁律11：不得内联物理公式
    n += 1
    hits = []
    for pat, why in _INLINE_PAT:
        for m in _re.finditer(pat, code_src):
            ln = code_src[:m.start()].split("\n")[0].split()[0]
            hits.append(f"L{ln} {why}: {m.group(0)[:40]}")
    if hits:
        print("FAIL 内联物理公式（铁律11）:")
        for h in hits:
            print("   -", h)
        ok = False
    else:
        print("PASS 无内联物理公式（一律调 physics.*）")

    # 2) 铁律14：气动力换算禁魔法系数
    n += 1
    magics = []
    for m in _re.finditer(_MAGIC_PAT, code_src):
        if "1e-6" in m.group(0):
            continue                      # 1e-6 是除零保护，不是量纲补丁
        ln = code_src[:m.start()].split("\n")[0].split()[0]
        magics.append(f"L{ln} {m.group(0)}")
    if magics:
        print("FAIL 疑似魔法系数（铁律14）:")
        for x in magics:
            print("   -", x)
        ok = False
    else:
        print("PASS 无魔法系数")

    # 3) 走路锁相参数自洽
    n += 1
    v = STEP_LENGTH_M * (CADENCE_SPM / 60.0)   # m/s
    if 1.2 <= v <= 1.7:
        print("PASS 步速 %.3f m/s 落在中性步速区间 1.2-1.7" % v)
    else:
        print("FAIL 步速 %.3f m/s 超出 1.2-1.7" % v)
        ok = False
    amp_cm = COM_V_RATIO * REAL_HEIGHT_M * 100 * 2
    n += 1
    if 2.0 <= amp_cm <= 5.0:
        print("PASS 重心起伏峰峰 %.2f cm 落文献 2-5cm" % amp_cm)
    else:
        print("FAIL 重心起伏 %.2f cm 超出文献 2-5cm" % amp_cm)
        ok = False

    # 4) 最小 Ctx 冒烟：各 update_* 可调用
    n += 1
    try:
        c = Ctx(540, 960)
        c.bg = None
        c.char_px = 691
        c.px_per_m = ph.px_per_m(691, REAL_HEIGHT_M)
        c.wind_speed = 0.0
        c.cloth_mass_kg = 0.0257      # 幡旗（scene_spec）
        c.cloth_area_m2 = 0.270
        init_physics(c)
        for i in range(3):
            update_animation(c, i, i / 60.0)
            update_physics(c, i, i / 60.0)
            update_composite(c, i, i / 60.0)
            update_subtitle(c, i, i / 60.0)
        print("PASS 冒烟：init_physics + 4 个 update 跑 3 帧无异常")
    except Exception as e:
        print("FAIL 冒烟异常: %s: %s" % (type(e).__name__, e))
        ok = False

    # 5) Verlet 能量不发散（无风时应衰减）
    n += 1
    try:
        c2 = Ctx(540, 960)
        c2.bg = None
        c2.char_px = 691
        c2.px_per_m = ph.px_per_m(691, REAL_HEIGHT_M)
        c2.wind_speed = 0.0
        c2.cloth_mass_kg = 0.0257
        c2.cloth_area_m2 = 0.270
        init_physics(c2)
        free = [p for p in c2.particles if not p["locked"]]
        for p in free:
            p["px"] = p["x"] - 5.0       # 给初速度
        v0 = sum(abs(p["x"] - p["px"]) for p in free) / max(1, len(free))
        for i in range(120):
            update_physics(c2, i, i / 60.0)
        v1 = sum(abs(p["x"] - p["px"]) for p in free) / max(1, len(free))
        if v1 <= v0 * 1.05:
            print("PASS Verlet 能量不发散（残余速度 %.4f -> %.4f）" % (v0, v1))
        else:
            print("FAIL Verlet 发散 %.4f -> %.4f" % (v0, v1))
            ok = False
    except Exception as e:
        print("FAIL Verlet 检查异常: %s: %s" % (type(e).__name__, e))
        ok = False

    print("\n%d 项检查 -> %s" % (n, "PASS" if ok else "FAIL"))
    return ok, n
