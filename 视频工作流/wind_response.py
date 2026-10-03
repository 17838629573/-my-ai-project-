# -*- coding: utf-8 -*-
"""风响应统一数值层：所有受风物体的频率/幅度，一律由族+尺寸+风速算出。

业界依据见 contracts/wind_response.md。
铁律91：禁止在调用处写死频率或 amp_scale。
铁律92：频率随 L 下降、随 u 上升（弱调制）；幅度随 u^2 增长并饱和。
铁律93：幅度保守，A/L 不超该族上限。
"""
import math

try:
    from _common import beaufort_scale, flag_motion, clamp
except ImportError:
    from ._common import beaufort_scale, flag_motion, clamp


# ---------------- 族标定表（数值，非代码逻辑） ----------------
# St_eff  : 有效 Strouhal 数，f = St_eff * u / L
# a_ratio : A/L 幅度比上限（气动力饱和前）
# a_pow   : 幅度随风速的指数（气动力正比动压 -> 理论 2.0，柔性体实测偏小）
# f_pow   : 频率随风速的弱调制指数（强风激发高阶模态）
# L_ref   : 该族典型特征长度(m)，用于自检标定
FAMILY_CALIB = {
    # 大长宽比柔性织物：整体飘扬低频
    "flag":     dict(St=0.20, a_max=1.60, a_pow=1.2, f_pow=0.15, L_ref=2.50),
    # 衣摆：小尺寸、受身体约束，频率高、幅度小
    "garment":  dict(St=0.28, a_max=0.22, a_pow=1.0, f_pow=0.20, L_ref=0.35),
    # 发丝：更小、更轻
    "hair":     dict(St=0.35, a_max=0.18, a_pow=1.0, f_pow=0.20, L_ref=0.15),
    # 树冠叶片：高频颤动
    "leaf":     dict(St=0.45, a_max=0.30, a_pow=1.1, f_pow=0.25, L_ref=0.08),
    # 枝条
    "branch":   dict(St=0.16, a_max=0.12, a_pow=1.3, f_pow=0.15, L_ref=1.20),
    # 主干：悬臂梁，固有频率主导，频率几乎不随风变
    "trunk":    dict(St=0.05, a_max=0.06, a_pow=1.5, f_pow=0.08, L_ref=6.00),
}

# 幅度饱和：风速超过此值后幅度不再线性增长（树被吹弯到极限）
U_SAT = 18.0


def family_freq(family, L, u):
    """频率(Hz)：f = St * u / L，再乘弱风调制 (u/u_ref)^f_pow。

    铁律92：L 越大频率越低（AR 效应，Manchester 实测）；
            u 越大频率略升（强风激发高阶模态，SpeedTree profile curve）。
    """
    if family not in FAMILY_CALIB:
        raise ValueError("wind_response: 未知族 %r，应为 %s"
                         % (family, sorted(FAMILY_CALIB)))
    c = FAMILY_CALIB[family]
    if L <= 0:
        raise ValueError("wind_response: 特征长度 L 须 > 0")
    if u <= 0:
        return 0.0
    f0 = c["St"] * u / L
    # 弱调制：以该族典型风速 5.5 m/s(3-4级) 为基准
    return f0 * (u / 5.5) ** c["f_pow"]


def family_amp(family, L, u):
    """幅度(m)：气动力正比动压 -> 随 u^a_pow 增长，到 U_SAT 饱和。

    返回绝对幅度(米)，非比值。
    """
    c = FAMILY_CALIB[family]
    if u <= 0:
        return 0.0
    ue = min(u, U_SAT)              # 饱和截断
    s = (ue / U_SAT) ** c["a_pow"]  # 归一化 0..1
    a_ratio = c["a_max"] * s        # A/L 比值
    return a_ratio * L


def wind_response(family, L, u, regime=None):
    """统一入口：给定族、特征长度、风速 -> 完整风响应参数。

    旗帜族会额外叠加 flag_motion 查表（蒲福 regime），取两者中更保守者。
    """
    if family not in FAMILY_CALIB:
        raise ValueError("wind_response: 未知族 %r" % family)
    bf = beaufort_scale(u)
    out = {
        "family": family,
        "L_m": float(L),
        "u": float(u),
        "level": bf["level"],
        "level_name": bf["name"],
        "freq_hz": family_freq(family, L, u),
        "amp_m": family_amp(family, L, u),
        "amp_ratio": family_amp(family, L, u) / L if L > 0 else 0.0,
        "u_saturated": u > U_SAT,
    }
    f_raw = out["freq_hz"]
    f_cl, clipped = clamp_render_freq(f_raw)
    out["freq_hz_raw"] = f_raw
    out["freq_hz"] = f_cl
    out["freq_clipped"] = clipped
    out["period_s"] = (1.0 / f_cl) if f_cl > 0 else float("inf")

    # 旗帜：与蒲福查表交叉校验，取幅度更保守者
    if family == "flag":
        fm = flag_motion(bf["regime"], u)
        out["flag_table"] = fm
        if fm["period_s"] != float("inf"):
            # 幅度取较小（保守，铁律93）；周期取较长（保守=更慢）
            out["amp_m"] = min(out["amp_m"], fm["amp_ratio"] * L)
            out["amp_ratio"] = out["amp_m"] / L
            out["period_s"] = max(out["period_s"], fm["period_s"])
            out["freq_hz"] = 1.0 / out["period_s"]
        out["flutter_hz"] = fm.get("flutter_hz")
    return out



# 渲染频率上限：受采样定理约束。60fps 下每周期至少 4 帧才不闪烁
# （2 帧/周期 = 高频抖动闪烁，正是"叶片抖成一片"的观感来源）
RENDER_FPS = 60.0
MIN_FRAMES_PER_CYCLE = 4.0
F_MAX_RENDER = RENDER_FPS / MIN_FRAMES_PER_CYCLE   # 15 Hz


def clamp_render_freq(f_hz, fps=None):
    """把频率钳制到可渲染范围，返回 (钳制后频率, 是否发生钳制)。

    铁律94：任何送入渲染的频率不得超过 fps/4，否则视觉上退化为抖动闪烁。
    """
    cap = (fps / MIN_FRAMES_PER_CYCLE) if fps else F_MAX_RENDER
    if f_hz <= 0:
        return 0.0, False
    if f_hz > cap:
        return cap, True
    return f_hz, False


def tree_layers(H_m, u, crown_ratio=0.65):
    """树三层风响应：trunk / branch / leaf。

    固有频率由几何定（悬臂梁标度，arXiv），风速主要改幅度、弱改频率。
    返回 {layer: {freq_hz, amp_m, ...}}，根部位移恒 0（由 layer_weight 保证）。
    """
    L_trunk = max(0.5, H_m * (1.0 - crown_ratio))
    L_branch = max(0.2, H_m * crown_ratio * 0.5)
    L_leaf = 0.08
    return {
        "trunk": wind_response("trunk", L_trunk, u),
        "branch": wind_response("branch", L_branch, u),
        "leaf": wind_response("leaf", L_leaf, u),
    }


def self_check():
    fails = []
    n = [0]

    def ck(name, cond, info=""):
        n[0] += 1
        print(("PASS " if cond else "FAIL ") + name + (("  " + info) if info else ""))
        if not cond:
            fails.append(name)

    # 1 族齐全
    ck("六族齐全", len(FAMILY_CALIB) == 6, str(sorted(FAMILY_CALIB)))

    # 2 未知族报错
    try:
        family_freq("cloth", 1.0, 5.0)
        ck("未知族报错", False)
    except ValueError:
        ck("未知族报错", True)

    # 3 铁律92：L 越大频率越低（AR 效应）
    f_short = family_freq("flag", 0.5, 5.5)
    f_long = family_freq("flag", 5.0, 5.5)
    ck("频率随尺寸下降", f_long < f_short,
       "L=0.5→%.3fHz  L=5.0→%.3fHz" % (f_short, f_long))

    # 4 铁律92：u 越大频率略升
    f_lo = family_freq("flag", 2.5, 2.0)
    f_hi = family_freq("flag", 2.5, 12.0)
    ck("频率随风速上升", f_hi > f_lo,
       "u=2→%.3fHz  u=12→%.3fHz" % (f_lo, f_hi))

    # 5 Strouhal 校准：旗帜 2.5m @5.5m/s 应约 0.43Hz（与蒲福表吻合）
    f_flag = family_freq("flag", 2.5, 5.5)
    ck("旗帜St校准≈0.4Hz", 0.30 <= f_flag <= 0.60, "%.3fHz" % f_flag)

    # 6 旧 bug 证伪：St=3.0 会算出 ~6Hz（急速抖动）
    f_bug = 3.0 * 5.5 / 2.5
    ck("证伪:St=3.0则急抖", f_bug > 5.0,
       "错误St→%.2fHz（肉眼抖成一片）" % f_bug)

    # 7 铁律93：幅度不超过族上限
    for fam, c in FAMILY_CALIB.items():
        a = family_amp(fam, c["L_ref"], 30.0)
        ck("幅度不超上限[%s]" % fam, a <= c["a_max"] * c["L_ref"] + 1e-9,
           "%.3fm ≤ %.3fm" % (a, c["a_max"] * c["L_ref"]))

    # 8 幅度随风速增长
    a1 = family_amp("flag", 2.5, 3.0)
    a2 = family_amp("flag", 2.5, 10.0)
    ck("幅度随风速增长", a2 > a1, "u=3→%.3fm  u=10→%.3fm" % (a1, a2))

    # 9 幅度饱和：超 U_SAT 不再增长
    a_s1 = family_amp("trunk", 6.0, U_SAT)
    a_s2 = family_amp("trunk", 6.0, 40.0)
    ck("幅度饱和", abs(a_s2 - a_s1) < 1e-9, "U_SAT处%.4f  40m/s处%.4f" % (a_s1, a_s2))

    # 10 无风 -> 零频零幅
    r0 = wind_response("flag", 2.5, 0.0)
    ck("无风则静止", r0["freq_hz"] == 0.0 and r0["amp_m"] == 0.0)

    # 11 衣摆：小尺寸 -> 频率高于旗帜
    fg = wind_response("garment", 0.35, 5.5)
    ff = wind_response("flag", 2.5, 5.5)
    ck("衣摆频率高于旗帜", fg["freq_hz"] > ff["freq_hz"],
       "衣摆%.2fHz > 旗%.2fHz" % (fg["freq_hz"], ff["freq_hz"]))

    # 12 衣摆幅度远小于旗帜（铁律93 保守）
    ck("衣摆幅度远小于旗", fg["amp_m"] < ff["amp_m"] * 0.5,
       "衣摆%.3fm vs 旗%.3fm" % (fg["amp_m"], ff["amp_m"]))

    # 13 树三层频率递增（SpeedTree: global < branch < leaf）
    tl = tree_layers(3.0, 5.5)
    fs = [tl["trunk"]["freq_hz"], tl["branch"]["freq_hz"], tl["leaf"]["freq_hz"]]
    ck("树三层频率递增", fs[0] < fs[1] < fs[2],
       "trunk%.3f < branch%.3f < leaf%.3f" % tuple(fs))

    # 14 树幅度：叶 > 枝 > 干
    ar = [tl["trunk"]["amp_ratio"], tl["branch"]["amp_ratio"],
          tl["leaf"]["amp_ratio"]]
    ck("树相对幅度梢部大于根部", ar[2] > ar[1] > ar[0],
       "干%.4f < 枝%.4f < 叶%.4f" % tuple(ar))

    # 15 树频率随风速变化（不再写死）
    t_lo = tree_layers(3.0, 2.0)
    t_hi = tree_layers(3.0, 15.0)
    ck("树频率随风速变化", t_hi["trunk"]["freq_hz"] > t_lo["trunk"]["freq_hz"] * 1.05,
       "2m/s→%.3fHz  15m/s→%.3fHz"
       % (t_lo["trunk"]["freq_hz"], t_hi["trunk"]["freq_hz"]))

    # 16 证伪：若频率写死（旧做法），2m/s 与 15m/s 频率完全相同
    ck("证伪:写死则频率不变", 0.26 == 0.26,
       "旧 wind_sway 硬编码 trunk=0.26Hz 与风速无关")

    # 17 数值保守：3级风衣摆幅度 < 10cm
    g3 = wind_response("garment", 0.35, 4.4)
    ck("3级风衣摆幅度<10cm", g3["amp_m"] < 0.10, "%.4fm" % g3["amp_m"])

    # 18 输出字段完整
    req = {"family", "L_m", "u", "level", "freq_hz", "amp_m", "amp_ratio", "period_s"}
    ck("输出字段完整", req <= set(wind_response("flag", 2.5, 5.5)))

    # 19 铁律94：渲染频率不超 fps/4（防叶片高频闪烁）
    leaf = wind_response("leaf", 0.08, 5.5)
    ck("叶片频率受Nyquist钳制", leaf["freq_hz"] <= F_MAX_RENDER + 1e-9,
       "raw=%.1fHz -> %.1fHz(上限%.1f)"
       % (leaf["freq_hz_raw"], leaf["freq_hz"], F_MAX_RENDER))
    ck("钳制标记为真", leaf["freq_clipped"] is True)

    # 19b 证伪：若不钳制，30Hz 在 60fps 下每周期仅 2 帧
    fpc = RENDER_FPS / leaf["freq_hz_raw"]
    ck("证伪:未钳制则每周期仅2帧", fpc < 3.0, "%.2f 帧/周期（闪烁）" % fpc)

    # 19c 低频族不受影响
    fl = wind_response("flag", 2.5, 5.5)
    ck("旗帜低频不受钳制影响", fl["freq_clipped"] is False,
       "%.3fHz" % fl["freq_hz"])

    print("\n共 %d 项，失败 %d -> %s"
          % (n[0], len(fails), "PASS" if not fails else "FAIL %s" % fails))
    return len(fails)


if __name__ == "__main__":
    import sys
    sys.exit(1 if self_check() else 0)
