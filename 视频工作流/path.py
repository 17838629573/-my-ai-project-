# -*- coding: utf-8 -*-
"""路径约束：把位置表示为「弧长 s + 横向偏移 offset」，使其永远在路径上。

业界依据见 contracts/path.md（Double Fine PhysSpline / AturSams lookahead）。
"""
import math


def _pt(p):
    return (float(p[0]), float(p[1]))


def catmull_rom(p0, p1, p2, p3, u):
    """标准 Catmull-Rom，u∈[0,1]，曲线经过 p1→p2。"""
    p0, p1, p2, p3 = _pt(p0), _pt(p1), _pt(p2), _pt(p3)
    u = float(u)
    u2 = u * u
    u3 = u2 * u
    x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * u
               + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * u2
               + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * u3)
    y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * u
               + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * u2
               + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * u3)
    return (x, y)


def _seg(pts, u):
    """把全局 u∈[0,1] 映射到某段 Catmull-Rom。端点自动复制。"""
    pts = [_pt(p) for p in pts]
    if len(pts) < 2:
        raise ValueError("路径至少需要 2 个控制点，收到 %d" % len(pts))
    u = min(1.0, max(0.0, float(u)))
    n = len(pts) - 1                       # 段数
    f = u * n
    i = int(f)
    if i >= n:
        i = n - 1
    t = f - i
    p1 = pts[i]
    p2 = pts[i + 1]
    p0 = pts[i - 1] if i - 1 >= 0 else pts[i]
    p3 = pts[i + 2] if i + 2 <= len(pts) - 1 else pts[i + 1]
    return catmull_rom(p0, p1, p2, p3, t)


def sample(pts, u):
    return _seg(pts, u)


def arc_table(pts, n=200):
    """累积弧长表：把 u 与弧长 s 对应起来（铁律77 的基础）。"""
    n = max(8, int(n))
    us = [i / float(n) for i in range(n + 1)]
    ss = [0.0]
    for i in range(1, n + 1):
        a = _seg(pts, us[i - 1])
        b = _seg(pts, us[i])
        ss.append(ss[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
    return {"u": us, "s": ss, "total": ss[-1]}


def _u_of_s(table, s):
    """弧长 → u，线性插值反查。"""
    ss = table["s"]
    us = table["u"]
    s = min(ss[-1], max(0.0, float(s)))
    lo, hi = 0, len(ss) - 1
    while lo < hi - 1:
        mid = (lo + hi) // 2
        if ss[mid] <= s:
            lo = mid
        else:
            hi = mid
    span = ss[hi] - ss[lo]
    f = 0.0 if span <= 1e-12 else (s - ss[lo]) / span
    return us[lo] + f * (us[hi] - us[lo])


def at_distance(pts, s, table=None):
    """按弧长取点（等速）。返回 {xy, tangent, u, s}。"""
    table = table or arc_table(pts)
    s = min(table["total"], max(0.0, float(s)))
    u = _u_of_s(table, s)
    xy = _seg(pts, u)
    eps = 1.0 / max(1.0, table["total"]) * 1e-3
    a = _seg(pts, max(0.0, u - eps))
    b = _seg(pts, min(1.0, u + eps))
    dx, dy = b[0] - a[0], b[1] - a[1]
    ln = math.hypot(dx, dy) or 1.0
    return {"xy": xy, "tangent": (dx / ln, dy / ln), "u": u, "s": s}


def project(pts, x, y, table=None):
    """世界点 → (弧长 s, 带符号横向偏移 offset)。"""
    table = table or arc_table(pts)
    best = None
    n = len(table["u"])
    for i in range(n):
        u = table["u"][i]
        px, py = _seg(pts, u)
        d = math.hypot(x - px, y - py)
        if best is None or d < best[0]:
            best = (d, table["s"][i], (px, py))
    dist, s, foot = best
    at = at_distance(pts, s, table)
    tx, ty = at["tangent"]
    # 带符号偏移：切向左法向 ( -ty, tx )
    nx, ny = -ty, tx
    offset = (x - foot[0]) * nx + (y - foot[1]) * ny
    return {"s": s, "offset": offset, "xy": foot, "tangent": (tx, ty), "dist": dist}


def clamp_offset(offset, half_width):
    hw = abs(float(half_width))
    o = float(offset)
    return max(-hw, min(hw, o))


def advance(s, ds, total):
    return min(float(total), max(0.0, float(s) + float(ds)))


def lookahead(pts, s, da, table=None):
    table = table or arc_table(pts)
    return at_distance(pts, advance(s, da, table["total"]), table)


def self_check():
    fails = []
    total = [0]

    def ck(name, cond, info=""):
        total[0] += 1
        print(("PASS " if cond else "FAIL ") + name + (("  " + info) if info else ""))
        if not cond:
            fails.append(name)

    # 一条水平路：y 恒定 450（城墙走道）
    line = [(60.0, 450.0), (250.0, 450.0), (440.0, 450.0)]
    tab = arc_table(line, 400)

    # 1 经过控制点
    p = sample(line, 0.5)
    ck("路径经过中点控制点", abs(p[0] - 250.0) < 1e-6 and abs(p[1] - 450.0) < 1e-6,
       "(%g,%g)" % p)

    # 2 弧长表总长 ≈ 几何长度
    ck("弧长总长正确", abs(tab["total"] - 380.0) < 1.0, "total=%.3f" % tab["total"])

    # 3 铁律77：等速 —— 按弧长推进，相邻等距采样间距一致
    steps = [at_distance(line, tab["total"] * i / 20.0, tab)["xy"] for i in range(21)]
    gaps = [math.hypot(steps[i + 1][0] - steps[i][0], steps[i + 1][1] - steps[i][1])
            for i in range(20)]
    spread = (max(gaps) - min(gaps)) / (sum(gaps) / len(gaps))
    ck("弧长参数化等速", spread < 0.02, "间距相对离散=%.4f" % spread)

    # 3b 证伪：按 u 推进（错误做法）在不等距控制点上不等速
    bent = [(60.0, 450.0), (120.0, 445.0), (400.0, 450.0)]   # 控制点疏密不均
    tb = arc_table(bent, 400)
    ugaps = []
    prev = None
    for i in range(21):
        q = sample(bent, i / 20.0)
        if prev:
            ugaps.append(math.hypot(q[0] - prev[0], q[1] - prev[1]))
        prev = q
    uspread = (max(ugaps) - min(ugaps)) / (sum(ugaps) / len(ugaps))
    ck("证伪:按u推进不等速", uspread > 0.5, "u间距相对离散=%.3f" % uspread)
    _ = tb  # 保持引用，避免误删

    # 4 投影：路径上的点 offset≈0
    pr = project(line, 250.0, 450.0, tab)
    ck("路径上点offset≈0", abs(pr["offset"]) < 0.5, "offset=%.4f" % pr["offset"])

    # 5 投影：偏离 30px 的点 offset≈±30
    pr2 = project(line, 250.0, 420.0, tab)
    ck("偏离30px测得offset", abs(abs(pr2["offset"]) - 30.0) < 0.5,
       "offset=%.3f" % pr2["offset"])

    # 6 clamp_offset 钳制
    ck("偏移钳制在半宽内", clamp_offset(999.0, 25.0) == 25.0
       and clamp_offset(-999.0, 25.0) == -25.0, "±999→±25")

    # 7 铁律76：位置由参数构成 —— 任意 offset 钳制后，点必在路带内
    ok = True
    for o in (-60.0, -26.0, 0.0, 26.0, 60.0):
        co = clamp_offset(o, 25.0)
        if abs(co) > 25.0 + 1e-9:
            ok = False
    ck("钳制后永不越界", ok, "半宽25，输入±60")

    # 8 advance 到端点 clamp
    ck("推进到端点clamp", advance(370.0, 50.0, 380.0) == 380.0
       and advance(5.0, -50.0, 380.0) == 0.0, "370+50→380, 5-50→0")

    # 9 lookahead 不超过末端
    la = lookahead(line, 370.0, 50.0, tab)
    ck("前瞻不越末端", abs(la["s"] - 380.0) < 1e-6, "s=%.1f" % la["s"])

    # 10 切向方向正确（水平路，切向应为 ±x）
    at = at_distance(line, 100.0, tab)
    ck("切向沿路径方向", abs(abs(at["tangent"][0]) - 1.0) < 1e-3,
       "tangent=(%.3f,%.3f)" % at["tangent"])

    # 11 少于2点报错
    try:
        sample([(1.0, 2.0)], 0.5)
        ck("单点路径报错", False)
    except ValueError:
        ck("单点路径报错", True)

    # 12 弯曲路径投影仍合理（城墙走道带弧度）
    curve = [(60.0, 460.0), (200.0, 450.0), (340.0, 452.0), (480.0, 462.0)]
    tc = arc_table(curve, 400)
    pc = project(curve, *at_distance(curve, tc["total"] * 0.5, tc)["xy"], tc)
    ck("弯曲路径自投影offset≈0", abs(pc["offset"]) < 1.0, "offset=%.4f" % pc["offset"])

    print("\n共 %d 项，失败 %d -> %s" % (total[0], len(fails),
                                    "PASS" if not fails else "FAIL %s" % fails))
    return len(fails)


if __name__ == "__main__":
    import sys
    sys.exit(1 if self_check() else 0)
