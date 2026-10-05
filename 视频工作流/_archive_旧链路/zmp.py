#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""X_c 失衡判定：ZMP + 支撑多边形。

业界（Vukobratovic / Physical Touch-Up）:
  ZMP = 地面反作用力净力矩为零的点。
  稳定判据：ZMP 必须落在【支撑多边形】内 —— 各接触点构成的凸包。
  出界即失衡，修正做法是把 ZMP 投影回支撑区并反解姿态。

重要限定（论文原文）：
  ZMP 在支撑区内 ≠ 一定平衡。真人绊倒时 ZMP 也可能仍在区内。
  所以本模块只做【判据与投影】，不声称能杜绝摔倒。

静态特例：加速度为 0 时 ZMP 退化为重心在地面的投影（CoM 投影）。
"""
import math

try:
    from scipy.spatial import ConvexHull
    HAS_SCIPY = True
except Exception:
    HAS_SCIPY = False


def _convex_hull_2d(pts):
    """Andrew monotone chain。pts: [(x,z), ...] -> 凸包顶点（逆时针）。"""
    pts = sorted(set((float(p[0]), float(p[1])) for p in pts))
    if len(pts) <= 2:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[0]) * (b[0] - o[0])

    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def support_polygon(contacts):
    """接触点 -> 支撑多边形（凸包）。contacts: [(x,z), ...]"""
    if not contacts:
        raise ValueError("support_polygon: 无接触点 —— 腾空状态无支撑多边形")
    return _convex_hull_2d(contacts)


def _point_in_convex(pt, poly, eps=1e-9):
    """点是否在凸多边形内（含边界）。poly 须为逆时针有序。"""
    n = len(poly)
    if n == 0:
        return False
    if n == 1:
        return math.hypot(pt[0] - poly[0][0], pt[1] - poly[0][1]) <= eps
    if n == 2:
        # 退化为线段：点到线段距离
        (x1, z1), (x2, z2) = poly
        dx, dz = x2 - x1, z2 - z1
        L2 = dx * dx + dz * dz
        if L2 < eps:
            return math.hypot(pt[0] - x1, pt[1] - z1) <= eps
        t = max(0.0, min(1.0, ((pt[0] - x1) * dx + (pt[1] - z1) * dz) / L2))
        return math.hypot(pt[0] - (x1 + t * dx), pt[1] - (z1 + t * dz)) <= eps
    for i in range(n):
        (x1, z1), (x2, z2) = poly[i], poly[(i + 1) % n]
        if (x2 - x1) * (pt[1] - z1) - (z2 - z1) * (pt[0] - x1) < -eps:
            return False
    return True


def _project_to_polygon(pt, poly):
    """点到凸多边形的最近点（出界时投影回来）。"""
    best, bd = None, float("inf")
    n = len(poly)
    for i in range(n):
        (x1, z1), (x2, z2) = poly[i], poly[(i + 1) % n]
        dx, dz = x2 - x1, z2 - z1
        L2 = dx * dx + dz * dz
        if L2 < 1e-18:
            t = 0.0
        else:
            t = max(0.0, min(1.0, ((pt[0] - x1) * dx + (pt[1] - z1) * dz) / L2))
        qx, qz = x1 + t * dx, z1 + t * dz
        d = math.hypot(pt[0] - qx, pt[1] - qz)
        if d < bd:
            bd, best = d, (qx, qz)
    return best


def com_projection(links):
    """静态 ZMP = 各连杆质心的质量加权投影。
    links: [{'m': kg, 'r': (x,y,z)}, ...]，只取 (x,z) 平面。"""
    M = sum(float(l["m"]) for l in links)
    if M <= 0:
        raise ValueError("com_projection: 总质量须 > 0")
    x = sum(float(l["m"]) * float(l["r"][0]) for l in links) / M
    z = sum(float(l["m"]) * float(l["r"][2]) for l in links) / M
    return (x, z)


def zmp_dynamic(links, g=9.81):
    """动态 ZMP（Physical Touch-Up 式）。
    links: [{'m', 'r': (x,y,z), 'a': (ax,ay,az)}]，y 为竖直向上。

      Zx = Σ m_i(ÿ_i + g) x_i - Σ m_i ẍ_i y_i
           ─────────────────────────────────
                  Σ m_i(ÿ_i + g)
    """
    num_x = num_z = den = 0.0
    for l in links:
        m = float(l["m"]); r = l["r"]; a = l.get("a", (0.0, 0.0, 0.0))
        num_x += m * (a[1] + g) * r[0] - m * a[0] * r[1]
        num_z += m * (a[1] + g) * r[2] - m * a[2] * r[1]
        den += m * (a[1] + g)
    if abs(den) < 1e-12:
        raise ValueError("zmp_dynamic: 分母趋零（自由落体，无支撑）")
    return (num_x / den, num_z / den)


class Balance:
    """失衡判定 + ZMP 投影修正。"""

    def __init__(self, contacts, eps=1e-9):
        self.contacts = list(contacts)
        self.poly = support_polygon(self.contacts) if self.contacts else []
        self.eps = eps

    def stable(self, zmp):
        """ZMP 是否在支撑多边形内。腾空（无接触点）一律判 False。"""
        if not self.poly:
            return False
        return _point_in_convex((float(zmp[0]), float(zmp[1])), self.poly, self.eps)

    def margin(self, zmp):
        """稳定裕度：ZMP 到多边形边界的最短距离（负值=已出界）。"""
        if not self.poly:
            return float("-inf")
        z = (float(zmp[0]), float(zmp[1]))
        if _point_in_convex(z, self.poly, self.eps):
            return min(math.hypot(z[0] - p[0], z[1] - p[1]) for p in self.poly)
        q = _project_to_polygon(z, self.poly)
        return -math.hypot(z[0] - q[0], z[1] - q[1])

    def correct(self, zmp):
        """把出界 ZMP 投影回支撑区（业界修正做法）。"""
        z = (float(zmp[0]), float(zmp[1]))
        if self.stable(z):
            return z, 0.0
        q = _project_to_polygon(z, self.poly)
        return q, math.hypot(z[0] - q[0], z[1] - q[1])


def self_check():
    ok, bad = [], []
    def add(n, c, m=""):
        (ok if c else bad).append(n + (" " + m if m else ""))

    # 双脚站立：支撑多边形为两脚凸包（此处退化线段）
    contacts = [(-0.15, 0.0), (0.15, 0.0), (-0.15, 0.12), (0.15, 0.12)]
    B = Balance(contacts)

    add("1 双脚站稳(重心居中)", B.stable((0.0, 0.06)), "")
    add("2 重心出界判失衡", not B.stable((0.60, 0.06)), "")
    m_in = B.margin((0.0, 0.06)); m_out = B.margin((0.60, 0.06))
    add("3 裕度符号", m_in > 0 and m_out < 0, f"内={m_in:.3f} 外={m_out:.3f}")

    q, d = B.correct((0.60, 0.06))
    add("4 投影回支撑区", B.stable(q) and d > 0, f"移动={d:.3f}")
    add("5 投影精度", abs(q[0] - 0.15) < 1e-9, f"q={q}")

    # 单脚：凸包退化
    B1 = Balance([(0.0, 0.0)])
    add("6 单脚支撑退化为点", B1.stable((0.0, 0.0)) and not B1.stable((0.3, 0.0)))

    # 腾空：无接触点 -> 无支撑多边形
    B0 = Balance([])
    add("7 腾空无支撑", not B0.stable((0.0, 0.0)), "")

    # 静态 ZMP == 质量加权投影
    links = [{"m": 40.0, "r": (0.0, 0.9, 0.0)}, {"m": 20.0, "r": (0.30, 0.5, 0.0)}]
    z = com_projection(links)
    add("8 静态ZMP=质量加权", abs(z[0] - 0.10) < 1e-12, f"x={z[0]:.6f} 期望0.10")

    # 动态 ZMP 在加速度为 0 时退化为静态
    zd = zmp_dynamic([dict(l, a=(0.0, 0.0, 0.0)) for l in links])
    add("9 动静态一致", abs(zd[0] - z[0]) < 1e-12, f"{zd[0]:.6f} vs {z[0]:.6f}")

    print("PASS:")
    for x in ok: print("  " + x)
    if bad:
        print("FAIL:")
        for x in bad: print("  " + x)
    else:
        print("FAIL: 无")
    return not bad


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
