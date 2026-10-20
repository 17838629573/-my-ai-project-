# 契约: proc/tools/motionqual_selfcheck
#   一句话: motionqual 各指标的自检语料与驱动——证明每条指标能测出已知答案
#   完整契约见 tools/__init__.py
#   依据: NASA/JPL「无断言的自检等于没自检」；本轮新增 A*/打滑占比/稳定余量
#         三条指标，每条都必须有"测得出已知答案"的断言，否则等于没牙齿。
#   输入: 无（自带演示骨架序列）
#   输出: self_check() -> bool；断言明细打印到 stdout
#   依赖: tools.measure.motionqual
#   约束: 与指标实现分离，避免 motionqual.py 超 500 行红线（R2 超纲）
#   校验入口: python3 tools/corpus/motionqual_selfcheck.py
# -*- coding: utf-8 -*-
"""motionqual 指标自检 —— 与实现分离。

为什么分文件:
  演示序列 + 断言驱动约 110 行，与测量逻辑无关；内联会让 motionqual.py
  突破 500 行红线。分开后指标表仍是单一职责，自检也能独立跑。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))

from tools.measure.motionqual import (  # noqa: E402
    seg_seg_dist, zmp_stability, jitter_accel, pene_bone, contact_f1,
    duty_factor, relative_phase, strouhal, amp_ratio, foot_skate_ratio,
    bos_margin,
)
from base.assertrun import Checker  # noqa: E402


def _demo_frames(n=40, wobble=0.0):
    """构造可解析的演示骨架序列：整体匀速前进 + 可选抖动。"""
    out = []
    for i in range(n):
        x = 0.01 * i
        w = wobble * (1.0 if i % 2 else -1.0)
        out.append({
            "hip": (x, 0.0, 0.90),
            "chest": (x, 0.0, 1.30 + w),
            "head": (x, 0.0, 1.60 + w),
            "lfoot": (x - 0.2, 0.0, 0.02),
            "rfoot": (x + 0.2, 0.0, 0.02),
        })
    return out


def _sc_geom(C):
    """几何指标：段段距离 + 骨级自穿透。"""
    C.eq("seg_seg 相交距离", round(seg_seg_dist(
        (0, 0, 0), (1, 0, 0), (0.5, -0.5, 0), (0.5, 0.5, 0)), 9), 0.0)
    C.eq("seg_seg 平行距离", round(seg_seg_dist(
        (0, 0, 0), (1, 0, 0), (0, 1, 0), (1, 1, 0)), 9), 1.0)
    far = [{"a": (0, 0, 0), "b": (1, 0, 0), "c": (0, 1, 0), "d": (1, 1, 0)}]
    C.eq("PeneBone 分离无穿透", pene_bone(far, [("a", "b"), ("c", "d")]), 0.0)
    near = [{"a": (0, 0, 0), "b": (1, 0, 0), "c": (0, 0.01, 0), "d": (1, 0.01, 0)}]
    C.gt("PeneBone 重叠应为正", pene_bone(near, [("a", "b"), ("c", "d")]), 0.0)


def _sc_zmp(C, still, JN, MS, FT):
    """ZMP 稳定越界率与抖动。"""
    o0, d0 = zmp_stability(still, JN, MS, FT)
    C.eq("ZMP 匀速直行 越界率", o0, 0.0)
    C.eq("ZMP 匀速直行 BoSDist", d0, 0.0)
    j_clean = jitter_accel(still, JN)
    j_wob = jitter_accel(_demo_frames(40, 0.05), JN)
    C.lt("抖动 匀速应≈0", j_clean, 1e-9)
    C.gt("抖动 加抖应>0", j_wob, 0.0)
    C.gt("抖动 单调性", j_wob, j_clean)


def _sc_contact(C):
    """接触 F1 / 占空比 / 相对相位。"""
    gt = [True] * 5 + [False] * 5
    C.eq("接触F1 完全一致", round(contact_f1(gt, gt)["f1"], 9), 1.0)
    C.eq("接触F1 全错", round(contact_f1([False] * 10, gt)["f1"], 9), 0.0)
    C.eq("占空比 半程", duty_factor([True] * 5 + [False] * 5), 0.5)
    # 注意: 不能用 "x or 兜底值"，0.0 是合法答案且是假值，会被误替换
    _rp = relative_phase(gt, gt)
    C.eq("相对相位 同相", 9.0 if _rp is None else round(_rp, 9), 0.0)


def _sc_swim(C):
    """游动指标：Strouhal 与振幅比 A*（峰峰口径）。"""
    C.eq("Strouhal 2Hz*5cm/0.5mps", round(strouhal(2.0, 0.05, 0.5), 9), 0.4)
    C.note("St 0.2~0.4 出自 Triantafyllou 1993 / trout 实测 0.19~0.22")
    # 0.06/0.30 = 0.2，正好落在 [0.1, 0.3]，也对应论文"约 20% 体长"
    C.eq("A* 峰峰6cm/体长30cm", round(amp_ratio(0.06, 0.30), 9), 0.2)
    C.eq("A* 体长为0 应 None", amp_ratio(0.06, 0.0), None)
    # 反例：单边振幅直除会得 0.1（贴下界），说明口径错了会掉出区间
    C.eq("A* 口径反例 单边3cm/30cm", round(amp_ratio(0.03, 0.30), 9), 0.1)
    C.note("A* = A/L 的 A 是峰峰振幅(Saadat 2017 与 St 共用 A)；误用单边会小一半")


def _sc_skate(C):
    """打滑帧占比：阈值边界、无接触帧、up_axis 口径三组反例。"""
    # 每帧世界坐标前进 0.9cm，明确低于阈值 1.0cm → 不算打滑
    # 注意: 不能用"恰好等于阈值"的样本——浮点累加下 0.01*i-0.01*(i-1) 会在
    # 1e-18 量级上下抖动，边界帧归属不确定，这是浮点比较的固有脆弱性，
    # 不是实现缺陷。判据设计上应避免依赖恰好相等的边界值（见 smell S 浮点相等）。
    fr_eq = [{"lfoot": (0.009 * i, 0.0, 0.01), "rfoot": (0.009 * i, 0.0, 0.01)}
             for i in range(10)]
    r_eq, nc_eq, ns_eq = foot_skate_ratio(fr_eq, ["lfoot", "rfoot"])
    C.eq("打滑占比 低于阈值不算滑", ns_eq, 0)
    C.eq("打滑占比 接触帧数", nc_eq, 9)
    # 每帧前进 5cm，远超阈值 → 全滑
    fr_big = [{"lfoot": (0.05 * i, 0.0, 0.01)} for i in range(10)]
    r_big, _, ns_big = foot_skate_ratio(fr_big, ["lfoot"])
    C.eq("打滑占比 远超阈值全滑", round(r_big, 9), 1.0)
    # 足端离地(z=0.5) → 无接触帧 → ratio 必须是 None，不能是 0.0
    fr_air = [{"lfoot": (0.05 * i, 0.0, 0.5)} for i in range(10)]
    r_air, nc_air, _ = foot_skate_ratio(fr_air, ["lfoot"])
    C.eq("打滑占比 无接触帧应 None", r_air, None)
    C.eq("打滑占比 无接触帧计数0", nc_air, 0)
    C.note("0.0 与 None 必须分开：0.0=零打滑，None=没得测（否则会冒充通过）")
    # up_axis 口径：竖直轴指定错了会把"抬脚"当成水平滑移
    #   up_axis=1 → 竖直变化被排除 → 不打滑
    #   up_axis=2 → 把竖直变化当成水平位移 → 全滑（错误口径）
    fr_up = [{"lfoot": (0.0, 0.0, 0.01)}, {"lfoot": (0.0, 0.05, 0.01)}]
    _, _, ns_up1 = foot_skate_ratio(fr_up, ["lfoot"], up_axis=1)
    _, _, ns_up2 = foot_skate_ratio(fr_up, ["lfoot"], up_axis=2)
    C.eq("打滑占比 up_axis=1 排除竖直变化", ns_up1, 0)
    C.eq("打滑占比 up_axis=2 误把抬脚当滑移", ns_up2, 1)
    C.note("up_axis 必须显式传：项目内存在 (x,h,z) 与 (x,y,z↑) 两种口径")


def _sc_margin(C, still, JN, MS, FT):
    """稳定余量：双脚为正、单脚收窄、空输入不得冒充 0。"""
    mn, mean = bos_margin(still, JN, MS, FT)
    C.gt("稳定余量 匀速直行应为正", mn, 0.0)
    C.gt("稳定余量 均值应为正", mean, 0.0)
    # 单脚支撑（另一脚抬起）→ 支撑区间收窄，余量必须变小
    one_foot = [dict(f, rfoot=(f["rfoot"][0], f["rfoot"][1], 0.9)) for f in still]
    mn1, _ = bos_margin(one_foot, JN, MS, FT)
    C.lt("稳定余量 单脚应小于双脚", mn1, mn)
    mn0, mean0 = bos_margin([], JN, MS, FT)
    C.eq("稳定余量 空序列应 None", mn0, None)


def self_check():
    """自检: 每条指标都要能"测出已知答案"，否则等于没有牙齿。"""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    from base.assertrun import Checker
    C = Checker("tools/motionqual")
    JN = ["hip", "chest", "head", "lfoot", "rfoot"]
    MS = [0.40, 0.35, 0.10, 0.075, 0.075]
    FT = ["lfoot", "rfoot"]
    still = _demo_frames(40, 0.0)
    _sc_geom(C)
    _sc_zmp(C, still, JN, MS, FT)
    _sc_contact(C)
    _sc_swim(C)
    _sc_skate(C)
    _sc_margin(C, still, JN, MS, FT)
    return C.report()


if __name__ == "__main__":
    sys.exit(0 if self_check() else 1)
