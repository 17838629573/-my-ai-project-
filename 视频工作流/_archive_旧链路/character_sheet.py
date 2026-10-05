#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
角色图集 + 映射层
==================================================
【核心思路（用户指出）】
  不要"生成全身像再裁出特写" —— 那样裁出来的是低分辨率糊图。
  正确做法：每个景别【原生生成】一张专用图，
  代码只负责【映射回去】，不做裁切计算。

【两种映射模式】
  native  原生模式：细节资产（中景/近景/特写）
          生成时构图（头顶留白、切点）已烘焙进图像，
          → 代码【不裁剪】，整帧缩放到画布，保留原构图。
          char_h / ground_y 由图像自身决定，代码不重算。

  scaled  缩放模式：全身资产（大远景/远景/全景）
          生成时是完整全身像
          → 代码裁包围盒、按景别缩放到 char_h、放到 ground_y。
          比例由 photo_rules 反算。

【为什么必须分开】
  对 native 资产做 trim（裁包围盒）会【摧毁】生成时烘焙的头顶留白，
  这是此前的一个隐患：trim 后缩放=把留白吃掉，人物顶到画面上边缘。
"""
import json
import os

import cv2
import numpy as np

from chroma import chroma_key, clean_mask

BASE = os.path.dirname(os.path.abspath(__file__))
CHAR_DIR = os.path.join(BASE, "assets_tang", "char")


# ------------------------------------------------------------------ 图集声明
# mode: native（原生构图，不裁剪） / scaled（全身，按景别缩放）
# shots: 该资产适用的景别
SHEET = {
    # ---- 全身资产：用于大远景 / 远景 / 全景 ----
    "walk_a":  dict(file="xz_walk_a.jpg", mode="scaled", pose="walk",
                    frame=0, shots=["EWS", "WS", "FS"]),
    "walk_b":  dict(file="xz_walk_b.jpg", mode="scaled", pose="walk",
                    frame=1, shots=["EWS", "WS", "FS"]),
    "stand":   dict(file="xz_stand.jpg", mode="scaled", pose="stand",
                    shots=["EWS", "WS", "FS"]),
    "kneel":   dict(file="xz_kneel.jpg", mode="scaled", pose="kneel",
                    shots=["WS", "FS", "MS"]),
    # ---- 原生细节资产：各自对应景别，不裁剪 ----
    "cowboy":  dict(file="xz_cowboy.jpg", mode="native", pose="walk",
                    shots=["MFS"]),
    "medium":  dict(file="xz_medium.jpg", mode="native", pose="stand",
                    shots=["MS"]),
    "mcu":     dict(file="xz_mcu.jpg", mode="native", pose="stand",
                    shots=["MCU"]),
    # cu 已判废并归档 _archive/broken/：前景占比 3.1%，泛洪把主体吃掉
    "hands":   dict(file="xz_hands.jpg", mode="native", pose="detail",
                    shots=["ECU"]),
}

# ------------------------------------------------------------------ 配角登记
# 【契约先行】先声明槽位，status="missing" 表示资产尚未生成。
# enforce.py 会检出 missing 项；生成后只需把 status 改成 "ok"。
# 禁止凭空把 missing 写成 ok —— 那等于造假。
SUPPORTING = {
    # 与主角明确同框的角色（按叙事文本推导，非按重要性）
    "li_daliang": dict(cn="李大亮·凉州都督", file="li_daliang.png",
                       scene="03_office", status="missing",
                       need=["anchor", "stand"]),
    "li_chang":   dict(cn="李昌·瓜州州吏", file="li_chang.png",
                       scene="04_yamen", status="missing",
                       need=["anchor", "stand"]),
    "shi_pantuo": dict(cn="石槃陀·胡人向导", file="shi_pantuo.png",
                       scene="05_river", status="missing",
                       need=["anchor"]),
    "old_man":    dict(cn="老翁·赠马者", file="old_man.png",
                       scene="05_river", status="missing",
                       need=["anchor"]),
}

# ------------------------------------------------------------------ 表情集
# 【按内容裁剪】行业标准 6-12 个；本片叙事实际只需要 6 个。
# 喜悦/愤怒/惊讶/恐惧/厌恶/害羞/得意/困惑 → 文本中不存在，一律不生成。
EXPRESSION = {
    "neutral":  dict(cn="平静", file="xz_expr_01.png", status="missing"),
    "resolute": dict(cn="坚毅", file="xz_expr_02.png", status="missing"),
    "despair":  dict(cn="绝望", file="xz_expr_03.png", status="missing"),
    "wry":      dict(cn="自嘲", file="xz_expr_04.png", status="missing"),
    "moved":    dict(cn="感动", file="xz_expr_05.png", status="missing"),
    "grateful": dict(cn="感恩", file="xz_expr_06.png", status="missing"),
}

# ------------------------------------------------------------------ 道具
# 只登记剧情转折点道具。不需要：武器套组/多套服装/季节皮肤。
PROP = {
    "waterskin": dict(cn="水袋", file="prop_waterskin.png", status="missing",
                      why="失手洒掉 = 全片最关键转折点"),
    "warrant":   dict(cn="通缉文牒", file="prop_warrant.png", status="missing",
                      why="被撕掉 = 第二个转折点"),
    "horse":     dict(cn="瘦老赤马", file="prop_horse.png", status="missing",
                      why="它才是我的救命恩人"),
    "bundle":    dict(cn="行囊", file="prop_bundle.png", status="missing",
                      why="行走镜头必备"),
    "staff":     dict(cn="行脚杖", file="prop_staff.png", status="missing",
                      why="行走镜头必备"),
}

# ------------------------------------------------------------------ 走路 8 帧
# 【行业标准】contact / down / passing / up × 左右镜像 = 8 帧
# 播放速率 10fps，8 帧 = 0.8s 一个完整循环
WALK_8FRAME = {
    "F1_contact":  dict(file="xz_walk_01.png", mirror="F5", height="mid",   status="missing"),
    "F2_down":     dict(file="xz_walk_02.png",    mirror="F6", height="lowest", status="missing"),
    "F3_passing":  dict(file="xz_walk_03.png", mirror="F7", height="rising", status="missing"),
    "F4_up":       dict(file="xz_walk_04.png",      mirror="F8", height="highest", status="missing"),
}


def missing_assets():
    """
    【已修】status 改为由【文件是否真实存在】推导，不再手填。
    旧实现只看 v["status"] != "ok" —— 手填 ok 就能绕过，等于造假。
    现在：文件不存在即 missing，无论 status 写什么。
    """
    out = []
    for grp, tbl in (("配角", SUPPORTING), ("表情", EXPRESSION),
                     ("道具", PROP), ("走路8帧", WALK_8FRAME)):
        for k, v in tbl.items():
            f = os.path.join(CHAR_DIR, v.get("file", ""))
            if not (v.get("file") and os.path.exists(f)):
                out.append((grp, k, v.get("cn", k)))
    return out


def load_native(path, H, W):
    """
    原生模式：抠像但【不裁剪】，整帧缩放到画布。
    保留生成时烘焙的构图（头顶留白、切点）。
    返回 (BGRA, 放置x, 放置y)
    """
    bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    bgra, _ = chroma_key(bgr)
    bgra = clean_mask(bgra)
    bgra = cv2.resize(bgra, (W, H), interpolation=cv2.INTER_AREA)
    return bgra, 0, 0


def load_scaled(path, target_h):
    """缩放模式：抠像 → 清掩膜 → 裁包围盒 → 按高度缩放。"""
    bgr = cv2.imread(path, cv2.IMREAD_COLOR)
    if bgr is None:
        raise FileNotFoundError(path)
    bgra, _ = chroma_key(bgr)
    bgra = clean_mask(bgra)
    a = bgra[:, :, 3]
    ys, xs = np.where(a > 200)
    if len(xs) == 0:
        raise ValueError(f"{path}: 抠像后无前景")
    y0, y1 = ys.min(), ys.max() + 1
    x0, x1 = xs.min(), xs.max() + 1
    crop = bgra[y0:y1, x0:x1]
    h, w = crop.shape[:2]
    nw = max(1, int(round(w * target_h / h)))
    return cv2.resize(crop, (nw, int(target_h)), interpolation=cv2.INTER_AREA)


def resolve(shot_type, pose="walk", frame=0):
    """
    由【景别 + 姿态】查图集，返回资产条目。
    优先：该景别 + 该姿态的精确匹配
    回落：该景别的任意资产
    """
    cands = [k for k, v in SHEET.items() if shot_type in v["shots"]]
    if not cands:
        raise ValueError(f"没有资产覆盖景别 {shot_type}")
    # 精确匹配 pose
    for k in cands:
        v = SHEET[k]
        if v["pose"] == pose and v.get("frame", 0) == frame:
            return k, v
    for k in cands:
        if SHEET[k]["pose"] == pose:
            return k, SHEET[k]
    return cands[0], SHEET[cands[0]]


def measure_native_composition(path, H=960, W=540):
    """
    测量原生资产的构图：头顶留白、底部切点。
    用于验证生成时声明的构图是否真的达成了。
    """
    bgra, _, _ = load_native(path, H, W)
    a = bgra[:, :, 3]
    ys = np.where((a > 200).any(axis=1))[0]
    if len(ys) == 0:
        return None
    return {"top_px": int(ys.min()), "bottom_px": int(ys.max()),
            "headroom_pct": round(ys.min() / H, 3),
            "bottom_pct": round(ys.max() / H, 3)}


if __name__ == "__main__":
    import sys
    sys.path.insert(0, BASE)
    from photo_rules import SHOT_TYPES, body_pixels

    H, W = 960, 540
    print("=" * 78)
    print("角色图集 · 资产清单")
    print("=" * 78)
    print(f"{'资产':<10}{'模式':<8}{'姿态':<8}{'适用景别':<20}{'文件':<18}")
    print("-" * 78)
    for k, v in SHEET.items():
        print(f"{k:<10}{v['mode']:<8}{v['pose']:<8}"
              f"{','.join(v['shots']):<20}{v['file']:<18}")

    print("\n" + "=" * 78)
    print("缺失检查")
    print("=" * 78)
    miss = [v["file"] for v in SHEET.values()
            if not os.path.exists(os.path.join(CHAR_DIR, v["file"]))]
    print("  缺失文件:", miss if miss else "无")

    print("\n" + "=" * 78)
    print("原生资产构图实测（验证生成时声明的留白是否达成）")
    print("=" * 78)
    print(f"{'资产':<10}{'声明头顶留白':>14}{'实测':>10}{'判定':>10}")
    print("-" * 78)
    DECLARED = {"cowboy": 0.10, "medium": 0.12, "mcu": 0.12}
    from photo_rules import SHOT_TYPES as _ST
    for k, d in DECLARED.items():
        p = os.path.join(CHAR_DIR, SHEET[k]["file"])
        if not os.path.exists(p):
            continue
        m = measure_native_composition(p, H, W)
        if m is None:
            print(f"{k:<10}{'—':>14}{'无前景':>10}{'FAIL':>10}")
            continue
        got = m["headroom_pct"]
        ok = "OK" if abs(got - d) <= 0.06 else "偏差"
        print(f"{k:<10}{d:>14.0%}{got:>10.1%}{ok:>10}")

    print("\n" + "=" * 78)
    print("景别 → 资产 映射解析")
    print("=" * 78)
    print(f"{'景别':<7}{'中文':<8}{'资产':<10}{'模式':<8}{'人物高':>8}{'占屏':>7}")
    print("-" * 78)
    for st_key in ["EWS", "WS", "FS", "MFS", "MS", "MCU", "CU", "ECU"]:
        st = SHOT_TYPES[st_key]
        try:
            k, v = resolve(st_key)
        except ValueError as e:
            print(f"{st_key:<7}{st.cn:<8}{'—':<10}{'—':<8}{str(e)[:28]:>8}")
            continue
        ch, full = body_pixels(st, H)
        if v["mode"] == "native":
            disp = "原生满屏"
            frac = "—"
        else:
            disp = ch
            frac = f"{ch/H:.0%}"
        print(f"{st_key:<7}{st.cn:<8}{k:<10}{v['mode']:<8}{disp:>8}{frac:>7}")

    out = os.path.join(BASE, "character_sheet.json")
    json.dump({"sheet": SHEET, "resolution": [W, H]},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n写出 -> {out}")


# ---------------------------------------------------------------- 命名规范
# 【成熟方案 · 来源已核】sprite sheet 业界一致约定：
#   character_animation_frame.png，全小写、下划线分隔、
#   帧号【两位补零】。原因：hero_run_10 在几乎所有文件浏览器与打包工具中
#   都排在 hero_run_2 之前 —— 会【静默重排动画顺序】。
#   实测确认：sorted(['xz_walk_2','xz_walk_10']) == ['xz_walk_10','xz_walk_2']
def check_naming(directory=CHAR_DIR):
    """返回违例列表，空=通过。新增序列帧后必跑。"""
    import os
    bad = []
    for fn in sorted(os.listdir(directory)):
        stem = os.path.splitext(fn)[0]
        if stem != stem.lower():
            bad.append((fn, "非全小写"))
        for part in stem.split("_"):
            if part.isdigit() and len(part) < 2:
                bad.append((fn, f"帧号未两位补零: {part}"))
    return bad


# ---------------------------------------------------------------- 资产分级
# 【成熟方案】贴图分辨率按【屏幕占比】分级，不按角色重要性：
#   特写/近景（占屏大）  -> 高分辨率
#   远景/配角（占屏小）  -> 低分辨率，省显存与 IO
#   多部件角色用图集(TextureAtlas)合并，减少 draw call
# 我们这里是 2D 图层，对应的是【生成/缩放目标高度】而非贴图边长。
TIER_BY_SHARE = [
    # (占屏下限, 目标高度px)  —— 由 photo_rules.body_frac 决定
    (0.60, 1400),   # 近景及以上
    (0.40, 1000),
    (0.20,  700),
    (0.00,  420),   # 大远景/配角
]


def tier_target_h(body_frac):
    """按屏幕占比返回该资产的目标高度。占屏越小越省。"""
    for lo, h in TIER_BY_SHARE:
        if body_frac >= lo:
            return h
    return TIER_BY_SHARE[-1][1]


def loop_closed(frames):
    """循环动画首帧必须等于末帧（death 除外）。
    返回 (是否闭合, 平均像素差)。差值>0 说明循环点会跳一下。"""
    if len(frames) < 2:
        return True, 0.0
    import numpy as np
    d = np.abs(frames[0].astype(np.int16) - frames[-1].astype(np.int16)).mean()
    return bool(d < 1.0), float(d)
