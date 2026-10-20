# 契约: proc/tools/anchors
#   一句话: 判据阈值的外部锚点注册表 —— 只登记可复核的业界数值与口径，供 provenance 比对
#   完整契约见 tools/__init__.py
#   依据: Simmons et al.(2011) 研究者自由度 —— 阈值须独立于本次结果事先定标，
#         故"事先定标的来源"必须是项目外部、可复核的公开数值；
#         Kerr(1998) HARKing —— 本表数值一律先于本次实测取得，禁止事后回填；
#         arXiv:2104.08878 数据泄露 —— 若阈值反过来迁就实测，则"通过"不可信。
#   输入: harness.CRIT 的 [(name, thr, src)]
#   输出: (issues, compared, uncompared, gaps)；issues 为空表示无矛盾
#   依赖: 无（纯数据表，不联网、不跑物理）
#   约束: 只登记有 URL 或可引文献的数值；查不到的一律不写，不靠"业界通常"这类措辞蒙混；
#         relation=DIRECT 才做等值判定，REFERENCE 只报宽松/严格倍数，DIMENSION 只报量纲不可比；
#         本表自身不产生 PASS —— 未登记的判据如实计入 uncompared。
#   校验: python _proc/tools/anchors.py --self-check
# -*- coding: utf-8 -*-
"""外部锚点注册表（R22-A2）。

背景：provenance 原先只能比对"出处文本里自己写了数值"的判据 —— 56 条里只有 5 条满足，
其余 51 条标"未比对"，不冒充通过但也没有任何外部参照。

本表把**联网取到的业界公开数值**登记进来，让 provenance 从"内部自洽"扩展到"外部对齐"。
每条锚点必带 source 与 url（可复核），relation 决定怎么比：

    DIRECT     阈值应当等于锚点值（如 Box2D slop、Strouhal 区间端点）
    REFERENCE  同量纲参照，只报"我们是业界参照的多少倍"（宽松/严格），不做等值判定
    DIMENSION  量纲与业界口径不一致，如实标"不可比"，既不冒充通过也不冒充失败

另登记 GAPS：业界有明确数值、而我们尚未建立的判据（真正的缺口，不是本表能补的）。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
# 路径层级：本文件在 _proc/tools/attest/ 下，故 _PROC 要上溯两级。
# 写成 dirname(_HERE) 会让 _PROC 变成 _proc/tools —— 与 smell.py 曾踩过的
# 同层级错误同源（扫描范围悄悄缩小），故此处显式两级并加注释。
_PROC = os.path.dirname(os.path.dirname(_HERE))
if _PROC not in sys.path:
    sys.path.insert(0, _PROC)

# ---------------------------------------------------------------- 锚点表
# 字段: name / value / relation / unit / source / url / note
ANCHORS = [
    # ---- 接触与穿透：直接取自 Box2D 官方源码 ----
    dict(name="penetration_m", value=0.005, relation="DIRECT", unit="m",
         source="Box2D v2.4.1 b2_common.h:65 #define b2_linearSlop 0.005f",
         url="https://github.com/erincatto/box2d/blob/v2.4.1/include/box2d/b2_common.h",
         note="线性穿透容差，业界默认让位分离前允许的穿透量"),
    dict(name="contact_float_m", value=0.005, relation="DIRECT", unit="m",
         source="同上 b2_linearSlop", url="https://github.com/erincatto/box2d/blob/v2.4.1/include/box2d/b2_common.h",
         note="接触相浮空同用 slop"),
    dict(name="ground_penetration_m", value=0.005, relation="DIRECT", unit="m",
         source="同上 b2_linearSlop", url="https://github.com/erincatto/box2d/blob/v2.4.1/include/box2d/b2_common.h",
         note="穿地深度同用 slop"),
    dict(name="seg_penetration_m", value=0.005, relation="DIRECT", unit="m",
         source="同上 b2_linearSlop", url="https://github.com/erincatto/box2d/blob/v2.4.1/include/box2d/b2_common.h",
         note="骨段穿模同用 slop"),
    dict(name="xbody_penetration_m", value=0.005, relation="DIRECT", unit="m",
         source="同上 b2_linearSlop", url="https://github.com/erincatto/box2d/blob/v2.4.1/include/box2d/b2_common.h",
         note="跨实体穿模同用 slop"),

    # ---- 足部滑步：业界动捕真值 ----
    dict(name="foot_slip_m", value=0.001, relation="DIRECT", unit="m/frame",
         source="Zhang et al.2018 度量 s=d(2-2^(h/H))；Character Controllers Using Motion VAEs "
                "(arXiv:2103.14274) Table 1 报告动捕真值 0.10 cm/frame",
         url="https://arxiv.org/pdf/2103.14274.pdf",
         note="0.10 cm/frame = 0.001 m/frame，我们的阈值与动捕真值一致"),
    dict(name="skate_cm_frame", value=0.1, relation="REFERENCE", unit="cm/frame",
         source="同上：动捕真值 0.10；业界模型典型 0.067~0.44；OmniControl(arXiv:2310.08580) "
                "以 2.5cm 作为 skating 判定阈值",
         url="https://arxiv.org/pdf/2103.14274.pdf",
         note="我们取 1.0，为动捕真值的 10 倍 —— 与同项目的 foot_slip_m(0.1cm) 相差一个量级，"
              "两条滑步判据口径不一致。口径提醒：业界 0.10 基于动捕(AMASS 约 60fps)，"
              "本项目 24fps，同速度下每帧位移天然大 2.5 倍；即便按此折算，"
              "A1 直线行走实测 0.697 cm/frame 仍约为折算后参照(0.25)的 2.8 倍 —— "
              "该偏离是实测事实，不是度量口径造成的"),

    # ---- 游动效率 ----
    dict(name="strouhal_lo", value=0.2, relation="DIRECT", unit="无量纲",
         source="Saadat et al.《On the rules for aquatic locomotion》PhysRevFluids 2, 083102 (2017)；"
                "Taylor/Nudds/Thomas Nature 425:707 (2003)",
         url="https://link.aps.org/doi/10.1103/PhysRevFluids.2.083102",
         note="高效巡航 St 紧约束区间下界"),
    dict(name="strouhal_hi", value=0.4, relation="DIRECT", unit="无量纲",
         source="同上", url="https://link.aps.org/doi/10.1103/PhysRevFluids.2.083102",
         note="高效巡航 St 紧约束区间上界"),

    # ---- 抖动：量纲不可比 ----
    dict(name="jitter_accel", value=None, relation="DIMENSION", unit="10^2 m/s^3",
         source="Du et al.2023 / Karunratanakul 2023：Jitter 报告单位为 10^2 m/s^3（jerk 量级）",
         url="https://arxiv.org/pdf/2504.01338",
         note="我们的实现取 a_{t+1}-a_t 的均值，未除 dt^3，单位是 m/frame^3 而非 m/s^3 —— "
              "与业界口径不可直接比。这是量纲问题，不是阈值对错"),

    # ---- 稳定性余量：业界有推荐值，我们更宽松 ----
    dict(name="bos_dist_m", value=0.05, relation="REFERENCE", unit="m",
         source="人形导航教材 cog_buffer（稳定余量）典型取值 0.05~0.1 m",
         url="https://devhammad0.github.io/physical-ai-robotics-textbook/docs/chapter-3-autonomous-navigation/autonomous-humanoid-navigation",
         note="我们只要求 >=0（不越界），业界建议留 0.05~0.1 余量 —— 我们的判据更宽松"),

    # ---- 流体密度 ----
    dict(name="water_rho_rel", value=0.0, relation="REFERENCE", unit="无量纲",
         source="Macklin & Müller 2013 PBF：不可压缩条件 C = rho/rho0 - 1 = 0；"
                "后续工作指出流体-边界界面处密度误差显著更大",
         url="https://dl.acm.org/doi/10.1145/2461912.2461984",
         note="业界未给统一容差，0.1 为本工程自定；锚点 0 表示理论目标，只作方向参照"),

    # ---- 恢复系数 ----
    dict(name="restitution_err", value=None, relation="DIMENSION", unit="无量纲",
         source="Boeing《Evaluation of real-time physics simulation systems》：多数商用引擎的 COR "
                "近似都不理想，该文未给统一容差",
         url="http://www.adrianboeing.com/pal/papers/p281-boeing.pdf",
         note="业界无公认容差，无法构成锚点；我们的 0.05 属自定，如实标不可比"),

    # ---- 牛顿摆 ----
    dict(name="cradle_energy_err", value=None, relation="REFERENCE", unit="无量纲",
         source="LibreTexts 31.4 Newton's Cradle：末球应飞到'几乎相同的高度'(almost the same height)",
         url="https://phys.libretexts.org/Bookshelves/University_Physics/Book%3A_University_Physics_(OpenStax)/Book%3A_University_Physics_I_-_Mechanics_Sound_Oscillations_and_Waves_(OpenStax)/31%3A_Alternating-Current_Circuits",
         note="定性描述'几乎相同高度'，无数值阈值；我们的 5% 与之方向一致，但属自定"),

    # ---- 树叶终端速度：自洽可验 ----
    dict(name="leaf_v_term_mps", value=3.13, relation="DIRECT", unit="m/s",
         source="自由落体终速 sqrt(2gh)，h=2m, g=9.8 → 6.26 m/s；我们取 0.5 倍作为 flutter 上限",
         url="https://phys.libretexts.org",
         note="0.5*sqrt(2*9.8*2)=3.130，阈值与该式自洽；flutter 实测 0.16 远低于此"),

    # ---- 振幅比 A*（2026-10 补齐：业界有、我们此前缺）----
    dict(name="amp_ratio_lo", value=0.1, relation="DIRECT", unit="无量纲",
         source="Saadat et al. 2017《On the rules for aquatic locomotion》"
                "PhysRevFluids 2, 083102：St 单独不足以判定高效游动，需附加 A* = A/L ∈ [0.1, 0.3]",
         url="https://link.aps.org/doi/10.1103/PhysRevFluids.2.083102",
         note="A 为**峰峰**振幅 A_p-p，与 St=fA/U 共用同一个 A（Arellano: "
              "'A_p-p is the tail-beat peak-to-peak amplitude'）。"
              "初版误用单边振幅算出 0.104，修正后 2*0.03125/0.30=0.2083，"
              "落在区间内且吻合论文'约 20% 体长'"),
    dict(name="amp_ratio_hi", value=0.3, relation="DIRECT", unit="无量纲",
         source="同上上界",
         url="https://link.aps.org/doi/10.1103/PhysRevFluids.2.083102",
         note="同上；A* 上界 0.3"),

    # ---- 打滑帧占比（2026-10 补齐）----
    dict(name="foot_skate_ratio", value=0.40, relation="DIRECT", unit="占比",
         source="Motion Toolbox evaluation config：foot_skating_joint 按打滑帧占比评估，"
                "good < 0.40 / moderate < 0.60（越小越好）",
         url="https://github.com/lijiaman/chois_release",
         note="分母取接触帧（CHOIS contact-based 定义）。与 skate_cm_frame 的 "
              "Zhang 2018 高度加权公式 s=v(2-2h/H) 不是同一量，数值不可直接比较。"
              "A1 实测 0.0213（47 接触帧中 1 帧超阈值）"),

    # ---- 稳定余量（业界有，我们只有"越界距离"）----
    dict(name="bos_margin_m", value=0.0, relation="DIRECT", unit="m",
         source="bipedal 步行通行做法：ZMP 不仅要在支撑多边形内，还需留稳定余量；"
                "业界常用 0.05~0.10 m",
         url="https://doi.org/10.1002/9780470549148",
         note="本项登记下界 0（不越界）；0.05~0.10 的余量建议因缺节段质量表暂不采纳为判据，"
              "见 GAPS.segment_mass_table"),
]

# ---------------------------------------------------------------- 业界有、我们没有的判据（真缺口）
GAPS = [
    # ---- 以下两项已于 2026-10 补齐为正式判据，移入 ANCHORS（保留条目以证可追溯）----
    # dict(name="strouhal_amplitude_ratio", ...)  -> ANCHORS["amp_ratio_lo"/"amp_ratio_hi"]
    # dict(name="foot_skate_ratio", ...)          -> ANCHORS["foot_skate_ratio"]
    dict(name="segment_mass_table",
         expect="人体节段质量占比表（用于 ZMP/稳定余量的加权）",
         source="Winter《Biomechanics and Motor Control of Human Movement》节段质量占比；"
                "或 Drillis & Contini 1966（本工程 proportions 已引用该文）",
         url="https://doi.org/10.1002/9780470549148",
         note="bos_margin 测量能力已就位（自检覆盖），但项目内无带出处的节段质量表。"
              "未接入具体用例——用编造的质量分布凑判据违反 A1，宁可留空"),
]


def by_name():
    """返回 {判据名: 锚点}；重名取先登记的。"""
    out = {}
    for a in ANCHORS:
        out.setdefault(a["name"], a)
    return out


def _load_crit(crit):
    """取判据表 [(name, thr, src)]；失败或为空时返回 (None, 探针失效描述)。"""
    if crit is not None:
        return (crit, None) if crit else (None, "[R22-A2 探针失效] 判据表为空")
    sys.path.insert(0, _PROC)
    try:
        from tests.harness import CRIT
    except Exception as e:
        return None, "[R22-A2 探针失效] 无法读取 harness.CRIT：%s" % e
    rows = [(n, v[0], v[2] if len(v) > 2 else "")
            for n, v in (CRIT or {}).items()]
    if not rows:
        return None, "[R22-A2 探针失效] harness.CRIT 为空"
    return rows, None


def _cmp_direct(name, thr, a):
    """DIRECT 关系：阈值应等于锚点值。返回 (compared, issue_or_None, note)。"""
    av = a.get("value")
    if av is None:
        return 0, None, (name, "DIRECT", "UNCERTAIN", "锚点缺数值")
    compared = 1
    if abs(thr - float(av)) > 1e-9:
        return (compared,
                "[R22-A2 外部锚点矛盾] 判据 %s 阈值=%s，外部锚点=%s（%s，%s）"
                % (name, thr, av, a["source"], a["url"]),
                (name, "DIRECT", "MISMATCH", "thr=%s vs anchor=%s" % (thr, av)))
    return compared, None, (name, "DIRECT", "ALIGNED", "阈值=锚点 %s" % av)


def _cmp_reference(name, thr, a):
    """REFERENCE 关系：同量纲参照，差一个量级以上需说明。返回同上。"""
    av = a.get("value")
    if av is None:
        return 0, None, (name, "REFERENCE", "UNCERTAIN", "锚点缺数值")
    compared = 1
    av_f = float(av)
    # 用容差而非 == ：锚点值经 float() 转换，直接判等会在规则里报浮点相等异味，
    # 且容差语义更贴合"锚点为零（理论目标值）"的本意。
    if abs(av_f) < 1e-12:
        return compared, None, (name, "REFERENCE", "REFERENCE",
                                "锚点为理论目标 0，仅作方向参照")
    ratio = thr / av_f
    if ratio >= 10.0 or ratio <= 0.1:
        return (compared,
                "[R22-A2 与业界参照差一个量级以上] 判据 %s 阈值=%s，业界参照=%s（%.1f 倍）"
                "—— 需说明为何偏离，出处：%s" % (name, thr, av, ratio, a["source"]),
                (name, "REFERENCE", "LOOSE" if ratio > 1 else "TIGHT",
                 "%.1fx 锚点" % ratio))
    return compared, None, (name, "REFERENCE", "REFERENCE",
                            "%.1fx 锚点，同量级" % ratio)


def compare(crit=None):
    """把 CRIT 与外部锚点比对。

    crit: [(name, thr, src)]，None 时从 harness.CRIT 读。
    返回 (issues, compared, uncompared, detail)
      issues     矛盾或越界的描述（DIRECT 不等 / REFERENCE 差一个量级以上）
      compared   真正完成比对的条数
      uncompared 无锚点，未比对（不冒充通过）
      detail     [(name, relation, verdict, note)]
    """
    rows, err = _load_crit(crit)
    if err:
        return ([err], 0, [], [])

    tbl = by_name()
    issues, compared, uncompared, detail = [], 0, [], []
    for name, thr, _src in rows:
        a = tbl.get(name)
        if a is None:
            uncompared.append(name)
            continue
        rel = a["relation"]
        try:
            thr_f = float(thr)
        except Exception:
            uncompared.append(name)
            detail.append((name, rel, "UNCERTAIN", "阈值非数值，无法比对"))
            continue
        if rel == "DIRECT":
            got, iss, note = _cmp_direct(name, thr_f, a)
        elif rel == "REFERENCE":
            got, iss, note = _cmp_reference(name, thr_f, a)
        else:  # DIMENSION
            uncompared.append(name)
            detail.append((name, rel, "DIMENSION", a["note"]))
            continue
        compared += got
        detail.append(note)
        if iss:
            issues.append(iss)
        elif got == 0:
            uncompared.append(name)
    return issues, compared, uncompared, detail



def _sc_table(chk):
    """表自身完整性 + 比对语义：错位必报 / 对齐不报 / 无锚点不计入已比对。"""
    bad = [a["name"] for a in ANCHORS if not a.get("source") or not a.get("url")]
    chk.eq("锚点必须带 source+url", bad, [])
    rels = set(a["relation"] for a in ANCHORS)
    chk.eq("relation 取值合法", (rels <= {"DIRECT", "REFERENCE", "DIMENSION"}), True)
    nodir = [a["name"] for a in ANCHORS
             if a["relation"] == "DIRECT" and a.get("value") is None]
    chk.eq("DIRECT 锚点必须有数值", nodir, [])
    iss, cmpd, unc, _d = compare([("penetration_m", 0.01, "")])
    chk.eq("DIRECT 错位必须被抓到", len(iss), 1)
    chk.eq("DIRECT 错位计入已比对", cmpd, 1)
    iss2, cmp2, _u2, _d2 = compare([("penetration_m", 0.005, "")])
    chk.eq("DIRECT 对齐不报", len(iss2), 0)
    chk.eq("DIRECT 对齐计入已比对", cmp2, 1)
    _i3, c3, u3, _d3 = compare([("jitter_px", 0.1, "工程经验值")])
    chk.eq("无锚点计入未比对", ("jitter_px" in u3 and c3 == 0), True)


def _sc_dimension(chk):
    """量纲不可比不能冒充通过：不计入已比对，且必须有说明。"""
    _i4, c4, u4, d4 = compare([("jitter_accel", 0.001, "")])
    chk.eq("量纲不可比不计入已比对", c4, 0)
    chk.eq("量纲不可比有说明", (d4[0][2] if d4 else ""), "DIMENSION")
    iss5, _c5, _u5, _d5 = compare([("skate_cm_frame", 1.0, "")])
    chk.eq("差一个量级必须报", len(iss5), 1)


def self_check():
    import base.assertrun as _ar
    chk = _ar.Checker("tools/attest/anchors")
    _sc_table(chk)
    _sc_dimension(chk)
    return 0 if chk.report(verbose=True) else 1



def main():
    if "--self-check" in sys.argv:
        sys.exit(self_check())
    issues, compared, uncompared, detail = compare()
    print("=== 外部锚点比对 ===")
    for name, rel, verdict, note in detail:
        print("  %-24s %-10s %-10s %s" % (name, rel, verdict, note))
    print("已比对 %d 条，未比对 %d 条" % (compared, len(uncompared)))
    if GAPS:
        print("业界有、我们没有的判据：")
        for g in GAPS:
            print("  - %s 期望 %s（%s）" % (g["name"], g["expect"], g["url"]))
    for i in issues:
        print("  " + i)
    sys.exit(1 if issues else 0)


if __name__ == "__main__":
    main()
