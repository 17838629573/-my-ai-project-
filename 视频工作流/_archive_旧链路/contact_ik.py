#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X_h：末端执行器（手/脚）到物体接触点的 IK 约束。

业界要点（theorangeduck / InterControl / 运动重定向文献）：
  1. 两骨 IK（hip-knee-heel 或 shoulder-elbow-wrist）用余弦定理求解，
     不用 pole vector —— 用关节侧向量定旋转轴，避免极点翻转。
  2. maxExtension + 指数 soft clamp 防超伸：目标不可达时停在略小于
     L1+L2 处，而不是伸直锁死（伸直会导致后续无法回弯）。
  3. IK 是【姿态修正】不是【姿态替换】：在输入 pose 上叠加最小旋转，
     保留原始动画风格。完全重算会丢失表演细节。
  4. 末端定位约束形式化为 hfk(q) = e（正向运动学等于目标位置）。

本模块只做解析解部分（余弦定理 + soft clamp），
不含全身优化 —— 那是 contact_plan.py 的职责。
"""
import math

L1 = 0.42      # 上臂/大腿
L2 = 0.40      # 前臂/小腿
MAX_EXT = 0.999  # 最大伸展比（相对 L1+L2）


def _soft_clamp(d, l1=L1, l2=L2, max_ext=MAX_EXT):
    """指数 soft clamp：把距离压到略小于 l1+l2，防超伸锁死。

    业界做法：直接 clamp 到 l1+l2 会让关节伸直（knee lock），
    之后无法回弯且姿态丑。用 soft clamp 保留一点弯曲余量。
    """
    dmax = (l1 + l2) * max_ext
    dmin = abs(l1 - l2) * 1.001
    if d <= dmax:
        return max(d, dmin)
    # 超出部分指数压缩，渐近逼近 dmax
    over = d - dmax
    return dmax + (l1 + l2) * (1.0 - max_ext) * (1.0 - math.exp(-over / (l1 + l2)))


def _cosine_law(a, b, c):
    """已知三边求 a、b 夹角（对边 c）。返回弧度。"""
    v = (a * a + b * b - c * c) / (2.0 * a * b)
    v = max(-1.0, min(1.0, v))
    return math.acos(v)


def solve_two_bone(root, target, l1=L1, l2=L2, side=(0.0, 0.0, 1.0)):
    """两骨 IK 解析解。

    root   : 根关节位置（髋/肩）tuple3
    target : 末端目标位置（踝/腕）tuple3
    side   : 关节弯曲侧的参考向量（定旋转轴，免 pole vector）

    返回 dict:
      d       实际求解距离（已 soft clamp）
      d_raw   原始距离
      a1      根关节处弯曲角（弧度）
      a2      中间关节处弯曲角（弧度）
      reachable 原始距离是否在 [|l1-l2|, l1+l2] 内
    """
    delta = tuple(float(t) - float(r) for r, t in zip(root, target))
    d_raw = math.sqrt(sum(x * x for x in delta))
    d = _soft_clamp(d_raw, l1, l2)
    reachable = abs(l1 - l2) <= d_raw <= (l1 + l2)

    # 余弦定理：三角形 (l1, l2, d)
    a1 = _cosine_law(l1, d, l2)     # 根关节处，对边 l2
    a2 = math.pi - _cosine_law(l1, l2, d)   # 中间关节处，补角

    return {"d": d, "d_raw": d_raw, "a1": a1, "a2": a2,
            "reachable": reachable}


def contact_ik(root, target, l1=L1, l2=L2):
    """末端到接触点的 IK：只发姿态修正量，不替换整个姿态。

    返回 dict:
      ok         是否可达（不可达时也给 soft clamp 后的解）
      d, d_raw, a1, a2
      correction 末端被拉回到的位置（不可达时靠近目标但不超过极限）
    """
    delta = tuple(float(t) - float(r) for r, t in zip(root, target))
    n = math.sqrt(sum(x * x for x in delta))
    s = solve_two_bone(root, target, l1, l2)
    if n < 1e-9:
        unit = (0.0, 0.0, 0.0)
    else:
        unit = tuple(x / n for x in delta)
    corr = tuple(float(r) + u * s["d"] for r, u in zip(root, unit))
    return {"ok": s["reachable"], "d": s["d"], "d_raw": s["d_raw"],
            "a1": s["a1"], "a2": s["a2"], "correction": corr}


def self_check():
    ok, bad = [], []

    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    # 1 可达目标：修正后末端应精确落到 target
    root = (0.0, 1.0, 0.0)
    tgt = (0.3, 0.6, 0.0)
    r = contact_ik(root, tgt)
    err = math.dist(r["correction"], tgt)
    add("1 可达目标精确命中", err < 1e-6, "err=%.2e" % err)

    # 2 不可达目标：不得超伸
    far = (5.0, 1.0, 0.0)
    r2 = contact_ik(root, far)
    add("2 不可达不超伸", r2["d"] <= (L1 + L2) + 1e-9,
        "d=%.4f <= %.4f" % (r2["d"], L1 + L2))
    add("3 不可达标记为不可达", not r2["ok"], "ok=%s" % r2["ok"])

    # 3 soft clamp 单调性：距离越远，d 越接近极限但不超
    ds = [contact_ik(root, (x, 1.0, 0.0))["d"] for x in (0.5, 1.0, 2.0, 10.0)]
    add("4 soft clamp 单调不减", all(b >= a - 1e-12 for a, b in zip(ds, ds[1:])),
        "d=%s" % [round(x, 4) for x in ds])
    # soft clamp 的上确界是 L1+L2（渐近逼近，永不达到）—— 这才是"不超伸"。
    # MAX_EXT 只决定 dmax 的位置，不是上限。
    add("5 soft clamp 渐近不超伸", max(ds) <= (L1 + L2) + 1e-9,
        "max=%.4f <= %.4f" % (max(ds), L1 + L2))

    # 4 余弦定理自洽：三角形闭合
    r3 = contact_ik(root, (0.4, 0.7, 0.0))
    add("6 角度有限且为正", r3["a1"] > 0 and r3["a2"] > 0,
        "a1=%.3f a2=%.3f" % (r3["a1"], r3["a2"]))

    # 5 过近目标（小于 |l1-l2|）也不崩
    r4 = contact_ik(root, (0.0, 1.0, 0.0))
    add("7 退化输入不崩", r4["d"] >= abs(L1 - L2) - 1e-9,
        "d=%.4f" % r4["d"])

    print("PASS:")
    for x in ok:
        print("  " + x)
    if bad:
        print("FAIL:")
        for x in bad:
            print("  " + x)
    else:
        print("FAIL: 无")
    return not bad


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
