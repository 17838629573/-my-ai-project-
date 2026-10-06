"""动作分层合成与声明式求解

契约: motion/layer
  输入: 底层位姿 fn(t) -> {关节: (u,v,w)}
        overlays = [(fn, region, mode, w)]  声明式意图
  输出: 合成后的位姿字典（同一 17 关节结构）
  依赖: numpy, .character.joints
  被依赖: tests/*, showreel/*
  约束: 权重一律走本模块 per-bone 表，不许就地写 0/1 硬切；
        新增动作只写 overlays 声明，不改动底层公式
  校验: python -m motion.layer

为什么单独成模块
  过去每个组合动作（走路中挥手、走路中运球）都要手算一套新公式，
  导致同样的关节数学被抄 N 遍，且每次都要人工反解参数。
  分层的意义：底层公式只写一次，上层只声明"哪块骨骼、用什么模式"。

公式出处:
  · 分层混合（Mask 权重只在层内生效，层间由 LayerWeight 控制，两者相乘）：
    Unity Avatar Mask 骨骼遮罩
  · 分界点选腰部：UE Layered Blend per Bone 明确警告——
    选骨盆太靠下则"手臂混合不彻底"，选头太靠上则"身体转动不自然"
  · Override 用 Lerp / Additive 用加法：Unity Clip Blending 两种模式
  · 沿脊柱渐变而非硬切：避免可见接缝（同 UE 的 Branch Filter 渐变）
"""
import numpy as np

from .character.body import joints as J

# ---- 骨骼分区（依据 UE：分界点取腰部，不取骨盆也不取头）----
LOWER = ("pelvis", "hip_l", "hip_r", "knee_l", "knee_r", "ank_l", "ank_r")
BRIDGE = ("waist", "chest")
UPPER = ("neck", "head",
         "sh_l", "sh_r", "elb_l", "elb_r", "wri_l", "wri_r")

# ---- per-bone 权重：沿脊柱渐变，杜绝 0/1 硬切 ----
# pelvis 0.0 为分界，向上递增至手臂 1.0
WEIGHT = {
    "pelvis": 0.00,
    "waist": 0.35,      # 腰部：UE 推荐分界点
    "chest": 0.70,
    "neck": 0.85,
    "head": 0.90,
}
for _j in ("sh_l", "sh_r", "elb_l", "elb_r", "wri_l", "wri_r",
           "hip_l", "hip_r", "knee_l", "knee_r", "ank_l", "ank_r"):
    WEIGHT[_j] = 1.00

REGION = {
    "lower": LOWER,
    "bridge": BRIDGE,
    "upper": UPPER,
    "full": J.JOINTS,
}


def bone_w(joint, region, layer_w=1.0):
    """单骨骼最终权重 = Mask 权重 × LayerWeight（Unity：两者相乘）"""
    if region != "full" and joint not in REGION[region]:
        return 0.0
    if joint in WEIGHT:
        return float(WEIGHT[joint]) * float(layer_w)
    # 未在权重表中的关节（toe/heel 等末端）按名称归入下半身，权重 0
    if joint.startswith(("toe", "heel")):
        return 0.0
    return 1.0 * float(layer_w)


def _delta(over):
    """overlay 可能是位姿字典，也可能是 {'J': delta, ...} 形式"""
    if isinstance(over, dict) and "J" in over and not _is_pose(over):
        return over["J"]
    return over


def _is_pose(d):
    return any(k in d for k in ("wri_r", "ank_l", "head"))


def blend(base, over, region="full", mode="override", layer_w=1.0):
    """合成一位姿

    override : P = lerp(base, over, w)   替代（走路自带摆臂→被盖掉）
    additive : P = base + w * over      叠加（呼吸、挥手叠在走路之上）

    over 允许两种形态：完整位姿字典，或 {'J': 增量}（gesture.wave 即是后者）
    """
    src = _delta(over)
    out = {}
    for j, bv in base.items():
        w = bone_w(j, region, layer_w)
        b = np.asarray(bv, float)
        if j in src:
            o = np.asarray(src[j], float)
        else:
            # additive 下缺失关节即无增量；override 下则保持底层
            o = np.zeros(3) if mode == "additive" else b
        out[j] = tuple(b + w * o) if mode == "additive" \
            else tuple(b + w * (o - b))
    return out


def compose(base_fn, overlays, t):
    """声明式入口：只写意图，不手算参数

    base_fn   : t -> 位姿（gait / run / jump / sit …）
    overlays  : [(fn, region, mode, layer_w), ...] 按顺序叠加
    """
    p = dict(base_fn(t))
    for fn, region, mode, w in overlays:
        p = blend(p, fn(t), region=region, mode=mode, layer_w=w)
    return p


# ---------------- 自动求解：给定目标，反解轨迹，不手填参数 ----------------

def solve_min_jerk(p0, p1, T):
    """最小急动度 5 次多项式系数（Flash & Hogan 1985）

    过去要手填中间关键帧；这里只需给起点、终点、时长，系数自动解出。
    边界条件：位置连续 + 起止速度/加速度为 0
    """
    p0 = np.asarray(p0, float)
    p1 = np.asarray(p1, float)
    d = p1 - p0
    T = float(T)
    # x(t) = p0 + d * (10u^3 - 15u^4 + 6u^5)
    return p0, d, T


def min_jerk_at(coef, t):
    """按 solve_min_jerk 的系数取 t 时刻位置（自动满足 C2 连续）"""
    p0, d, T = coef
    u = min(max(t / T, 0.0), 1.0)
    return p0 + d * (10 * u ** 3 - 15 * u ** 4 + 6 * u ** 5)


def solve_ballistic(p0, tgt, v0=None, g=9.80665):
    """反解抛体初速：给定出手点、目标点，自动算该用多快

    这是修复"飞行时间被手的时间反向决定"的关键——
    因果应为：先定球速 → 飞行时间 = 距离/球速，而不是反过来。
    v0 给定时按 v0 解飞行时间；未给定时按 V_PASS 基准解。
    """
    p0 = np.asarray(p0, float)
    tgt = np.asarray(tgt, float)
    if v0 is None:
        v0 = V_PASS
    dx = abs(tgt[0] - p0[0])
    T = dx / v0                      # 飞行时间由球速决定
    v = np.array([(tgt[0] - p0[0]) / T,
                  (tgt[1] - p0[1] + 0.5 * g * T * T) / T])
    return p0, v, T


# 传球速度基准（依据: Shimizu et al.  wheelchair basketball chest pass
# 有经验组 5.3±0.5 m/s，无经验组 4.4±0.3 m/s）
V_PASS = 5.3


def attach(obj_xyz, pose, joint, offset=(0.0, 0.0, 0.0)):
    """物体自动跟随骨骼：给关节名即可，不手算世界坐标"""
    p = np.asarray(pose[joint], float) + np.asarray(offset, float)
    return tuple(p)


# ---------------- 自检 ----------------

def _flat_pose(v):
    """自检用平骨架：所有关节 y=v，x=z=0。"""
    return {j: (0.0, float(v), 0.0) for j in J.JOINTS}


def _chk_mask(c):
    """分区覆盖全骨架、权重沿脊柱单调递增（不硬切）。"""
    allj = set(LOWER) | set(BRIDGE) | set(UPPER)
    c.chk("分区覆盖 17 关节", set(J.JOINTS) == allj,
          "%d/%d" % (len(allj), len(J.JOINTS)))
    seq = [WEIGHT[k] for k in ("pelvis", "waist", "chest", "neck", "head")]
    c.chk("脊柱权重单调递增", all(a < b for a, b in zip(seq, seq[1:])), str(seq))


def _chk_blend(c):
    """blend 四性：override 替代 / additive 纯加法 / 层权重乘法 / 分区外不动。"""
    b, o = _flat_pose(0.0), _flat_pose(1.0)
    r = blend(b, o, "upper", "override", 1.0)
    c.chk("override w=1 完全替代", abs(r["wri_r"][1] - 1.0) < 1e-12,
          "%.4f" % r["wri_r"][1])
    c.chk("override 不动下半身", abs(r["ank_l"][1] - 0.0) < 1e-12,
          "%.4f" % r["ank_l"][1])
    r2 = blend(b, {"wri_r": (0.0, 0.5, 0.0)}, "upper", "additive", 1.0)
    c.chk("additive 纯加法", abs(r2["wri_r"][1] - 0.5) < 1e-12,
          "%.4f" % r2["wri_r"][1])
    r3 = blend(b, o, "upper", "override", 0.5)
    c.chk("层权重乘法生效", abs(r3["wri_r"][1] - 0.5) < 1e-12,
          "%.4f" % r3["wri_r"][1])     # Unity 口径：层权重 × mask 权重
    r4 = blend(b, o, "lower", "override", 1.0)
    c.chk("分区外不受影响", abs(r4["wri_r"][1] - 0.0) < 1e-12,
          "%.4f" % r4["wri_r"][1])


def _chk_solver(c):
    """自动求解三性：min_jerk 边界、弹道球速恒定、attach 跟随。"""
    c_ = solve_min_jerk((0.0, 0.0), (1.0, 0.5), 0.8)
    c.chk("min_jerk 起点精确",
          np.allclose(min_jerk_at(c_, 0.0), (0.0, 0.0), atol=1e-12), "0")
    c.chk("min_jerk 终点精确",
          np.allclose(min_jerk_at(c_, 0.8), (1.0, 0.5), atol=1e-12), "1")
    h = 1e-4
    v0 = (min_jerk_at(c_, h) - min_jerk_at(c_, 0.0)) / h
    c.chk("min_jerk 起点速度为 0", abs(v0[0]) < 1e-3, "%.2e" % v0[0])
    # 飞行时间由球速决定，不是由手决定
    _p, v, T = solve_ballistic((0.0, 1.5), (3.5, 1.3))
    c.chk("飞行时间由球速决定", abs(abs(v[0]) - V_PASS) < 1e-9,
          "vx=%.4f T=%.4fs" % (v[0], T))
    # 距离变化时球速恒定（旧实现的病：会被拉成 8m/s）
    _p2, v2, T2 = solve_ballistic((0.0, 1.5), (7.0, 1.3))
    c.chk("距离变化而球速不漂移", abs(abs(v2[0]) - abs(v[0])) < 1e-9,
          "%.3f vs %.3f, T %.3f->%.3f" % (abs(v[0]), abs(v2[0]), T, T2))
    pose = {j: (0.1, 0.2, 0.0) for j in J.JOINTS}
    c.chk("attach 自动跟随",
          abs(attach(None, pose, "wri_r", (0.0, 0.05, 0.0))[1] - 0.25) < 1e-12,
          "0.25")


def self_check():
    """分层自检：判据不变，断言交统一执行器。"""
    from base.assertrun import Checker
    c = Checker("layer")
    _chk_mask(c)
    _chk_blend(c)
    _chk_solver(c)
    return c.report()
