#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
复用规划：镜像/偏移/分层，减生图张数。

契约: contracts/solver_split.md
改前必读: IMPROVE_solver_split.md
"""





def _reuse_for(obj, spec, ans):
    """逐物体复用规划（铁律49-53）。

    播放帧数由物理周期定，需生成帧数由复用定——两个数字，禁混用。
    复用是语义判断（左右是否真只是方向反了），代码算完必须交 AI 确认。
    """
    # 末端横向位移序列。
    # 【铁律49】复用面向的是「素材张数 mat_frames」，不是播放帧数 frames：
    # 我们要省的是生图张数。若拿 frames 去规划，gen_n 会超过 mat_frames
    # （实测 16 张素材却要生 17 张），等于省了个寂寞。
    pg = ans["phase_geometry"]
    mf = int(ans["mat_frames"])
    if mf > 1:
        idx = [round(i * (len(pg) - 1) / (mf - 1)) for i in range(mf)]
    else:
        idx = [0]
    series = [pg[i][-1][0] for i in idx]
    anch = obj.get("锚点") or obj.get("anchor") or spec.get("anchor")
    ask_base = [
        "【结构复用】人体/动物主体结构是否只需生成一次？"
        "左右走 = 同一套骨架镜像翻转，仅摆动相位不同（业界 sprite "
        "mirror 定式，8帧走路 = 4张唯一图 + 4张镜像）",
        "【摆动差异】方向反转后残留的衣摆/发丝差异，是否交给 "
        "additive_offset 逐帧叠加，而非整块重新生图？",
    ]
    if anch is None:
        return {"strategy": "unknown",
                "play_n": ans["mat_frames"], "gen_n": ans["mat_frames"],
                "mirror": {"allowed": False},
                "ask_ai": ask_base + [
                    "缺 mirror anchor，无法规划半周期镜像。"
                    "请填 锚点=[x_px, y_px]（翻转轴必须过它，否则主体滑移）"]}
    try:
        rp = reuse_plan(series, criteria=spec.get("criteria"), anchor=anch)
    except ValueError as e:
        return {"strategy": "unknown",
                "play_n": ans["mat_frames"], "gen_n": ans["mat_frames"],
                "mirror": {"allowed": False},
                "ask_ai": ask_base + ["复用规划失败：%s" % e]}
    rp["ask_ai"] = ask_base + rp["ask_ai"]
    return rp




# ------------------------------------------------------------ 自检
# ------------------------------------------------------------ 复用规划（铁律49-53）
# 【业界搜证】见 contracts/reuse.md（真实联网）：
#  - lobehub：8帧走路 = 4张唯一图 + 4张镜像
#  - sprite-ai：4帧循环 F3=mirror(F1)、F4=mirror(F2)，只画2-3张
#  - Unity 官方 Blend Tree Mirror：镜像**不产生完全对称**，需自动补 offsets
#  - Defold：atlas 内复用同一图是"引用"不是"复制"
# 【数学依据】简谐 x(t+T/2) = -x(t) → 空间镜像 = 时间平移半周期
#   带系统性偏置时：x(t+T/2) = -x(t) + 2·offset
#   offset 与残差的量化，就是业界"自动加 offsets"的可计算版本。
def reuse_plan(series, criteria=None, anchor=None, axis="vertical"):
    """复用规划：播放帧数（物理定） vs 需生成帧数（复用定）。

    series  : 一维数值序列，物理算出的每帧特征位移，长度 = 播放帧数 N
    criteria: 阈值，铁律32 外置（mirror_residual_max，默认 0.05）
    anchor  : 镜像锚点 [x, y]，必填（铁律51）
    axis    : vertical(左右翻) / horizontal(上下翻)
    """
    if anchor is None:
        raise ValueError(
            "缺 mirror anchor（铁律51）：不指定锚点的翻转会导致主体滑移")
    if axis not in ("vertical", "horizontal"):
        raise ValueError("axis 需为 vertical|horizontal")

    crit = criteria or {}
    thr = float(crit.get("mirror_residual_max", 0.05))

    xs = [float(v) for v in series]
    n = len(xs)
    if n < 2:
        raise ValueError("series 长度需 >= 2")

    pp = max(xs) - min(xs)
    half = n // 2

    # 半周期配对：x[i] 与 x[i+half] 应互为反号（+2·offset）
    ssum = [xs[i] + xs[i + half] for i in range(half)]
    offset = (sum(ssum) / len(ssum)) / 2.0
    resid = max(abs(s - 2.0 * offset) for s in ssum)
    ratio = (resid / pp) if pp > 1e-12 else 0.0
    allowed = ratio <= thr

    if allowed:
        gen_n = half + (n % 2)
        strategy = "half_mirror"
    else:
        gen_n = n
        strategy = "none"

    reuse_map = [(i, False) if i < half else (i - half, True)
                 for i in range(n)]

    return {
        "play_n": n,
        "gen_n": gen_n,
        "strategy": strategy,
        "mirror": {
            "axis": axis,
            "anchor": list(anchor),
            "offset_m": offset,
            "residual_ratio": ratio,
            "threshold": thr,
            "allowed": allowed,
        },
        "reuse_map": reuse_map,
        # 铁律52：复用是语义判断（左右是否真只是方向反了），必须交 AI 确认
        "ask_ai": [
            "左右两半周期是否真的只是方向相反？（左右走 / 左右摆）",
            "镜像后是否有不可翻转的方向性特征？（文字、单侧配饰、光向、发型分缝）",
            "偏置补偿 offset=%.4g 是否在视觉可接受范围？" % offset,
            "是否接受 %s：播放 %d 帧 / 生成 %d 张？" % (strategy, n, gen_n),
        ],
    }




def layer_plan(spec):
    """分层规划（铁律53）：base 生成一次，overlay 挂 anchor，摆动走 additive。

    spec['layers'] 由 AI 声明——分层如何切是语义判断，代码不猜（铁律18/31）。
    业界：SummerEngine Modular Atlas / Terraria 分离件 / zombie-emily named anchor。
    """
    lys = spec.get("layers") if isinstance(spec, dict) else None
    if not lys or "base" not in lys:
        raise ValueError(
            "缺 layers.base 声明（铁律31/53）：分层如何切是语义判断，代码不猜")

    base = lys["base"]
    ovs = lys.get("overlays") or []
    out = []
    for o in ovs:
        if "name" not in o or "anchor" not in o:
            raise ValueError("overlay 缺 name 或 anchor（铁律31）")
        out.append({"name": o["name"], "anchor": o["anchor"],
                    "dx": float(o.get("dx", 0.0)),
                    "dy": float(o.get("dy", 0.0)),
                    "scale": float(o.get("scale", 1.0))})

    drv = (spec.get("drive") or {}).get("src") if isinstance(spec, dict) else None
    return {
        "base": {"name": base.get("name", "base"),
                 "frames": int(base.get("frames", 1)),
                 "regenerate_on_drive_change": False},
        "overlays": out,
        "additive": {"drive": drv or "none",
                     "curve_n": int((spec.get("render") or {}).get("N", 0)),
                     "note": "摆动作为 offset curve 叠加到 base，不重生成 base"},
    }




def additive_offset(base_curve, drive_curve, weight=1.0):
    """additive offset curve（铁律53）：base 一次生成，摆动算出来叠上去。

    业界 mocaponline：每个修饰是 additive offset curve，可多个叠加；
    5 个 base clip → 50 个看似各异的角色。
    """
    if len(base_curve) != len(drive_curve):
        raise ValueError("base_curve 与 drive_curve 长度需一致")
    w = float(weight)
    return [float(b) + w * float(d) for b, d in zip(base_curve, drive_curve)]
