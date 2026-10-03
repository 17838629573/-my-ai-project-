"""透视几何：地平线 / 深度 / 缩放场（纯函数，禁硬编码坐标）

业界依据（详见 IMPROVE_perspective.md）：
  [1] Hoiem et al. IJCV 2008 "Putting Objects in Perspective" Eq.(6)
      y_world ≈ H_cam * (v_t - v_b) / (v_0 - v_b)
  [2] CVPR "Single View Scene Scale Estimation Using Scale Field"
      SF(y) = (y - v_0) / H_cam            [px per meter]
      两式联立自洽：(v_b - v_t) = y_world * SF
  [3] 地面平面（零俯仰）：Z = f * H_cam / (y - v_0)
      来源：MDPI Sensors 2026 单目测距 Eq.(2)；McGill 视觉讲义

核心性质（铁律100）：
  横向（平行画面）移动 → y 不变 → SF 不变 → 无大小变化
  纵深（沿地面远近）移动 → y 变 → SF 线性变 → 远小近大
  路径点必须由 y(Z) 函数生成，禁止手填两点坐标。
"""

from __future__ import annotations

import math

# 焦距与像高之比的经验值。唯一出处：Hoiem IJCV2008 正文
#   "f = 1.4 times image height is typical"
F_OVER_IMAGE_H = 1.4


def focal_px(image_h: int, ratio: float = F_OVER_IMAGE_H) -> float:
    """焦距（px）。ratio 缺省取 Hoiem 经验值 1.4。"""
    if image_h <= 0:
        raise ValueError("image_h 必须 > 0")
    return ratio * float(image_h)


def horizon_from_vanishing(segs, image_h: int):
    """由线段组求地平线 y。

    segs: [(x1,y1,x2,y2), ...]，取延长线交点（消失点）的 y 中位数。
    依据[2]：所有平行线组的消失点都落在地平线上。
    线段不足或交点发散时抛错，禁静默返回默认值（铁律31）。
    """
    pts = []
    n = len(segs)
    for i in range(n):
        for j in range(i + 1, n):
            p = _seg_intersect(segs[i], segs[j])
            if p is None:
                continue
            x, y = p
            # 排除近并行（交点跑到极远）与画面外的退化交点
            if abs(x) > 20 * image_h or abs(y) > 20 * image_h:
                continue
            pts.append(y)
    if len(pts) < 3:
        raise ValueError(
            "地平线探测失败：有效交点 %d 个 < 3。须提供至少两组汇聚平行线"
            % len(pts)
        )
    pts.sort()
    return pts[len(pts) // 2]


def _seg_intersect(a, b):
    """两线段延长线交点，平行返回 None。"""
    x1, y1, x2, y2 = a
    x3, y3, x4, y4 = b
    d = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
    if abs(d) < 1e-9:
        return None
    t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / d
    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))


def camera_height_from_ref(y_world: float, v_t: float, v_b: float, v_h: float) -> float:
    """由已知真实高度的参照物反解相机高度。依据[1] Eq.(6) 变形。

    y_world: 参照物真实高度(m)；v_t/v_b: 其顶部/底部像素 y；v_h: 地平线 y。
    """
    if v_b <= v_h:
        raise ValueError("参照物底部必须在地平线下方（v_b > v_h）")
    if v_t >= v_b:
        raise ValueError("顶部像素 y 必须小于底部（图像 y 向下为正）")
    return y_world * (v_b - v_h) / (v_b - v_t)


def scale_field(y: float, v_h: float, h_cam: float) -> float:
    """缩放场 SF(y)：该屏幕行上 1 米对应多少像素。依据[2]。"""
    if h_cam <= 0:
        raise ValueError("h_cam 必须 > 0")
    if y <= v_h:
        raise ValueError("y 必须在地平线下方（y > v_h），否则是天空无地面尺度")
    return (y - v_h) / h_cam


def depth_at(y: float, v_h: float, f_px: float, h_cam: float) -> float:
    """屏幕行 y 对应的地面深度 Z(m)。依据[3]。"""
    sf = scale_field(y, v_h, h_cam)
    return f_px / sf


def y_at_depth(z: float, v_h: float, f_px: float, h_cam: float) -> float:
    """深度 Z(m) 对应的屏幕行 y。depth_at 的反函数。"""
    if z <= 0:
        raise ValueError("深度 Z 必须 > 0")
    return v_h + f_px * h_cam / z


def path_along_depth(z0: float, z1: float, n: int, v_h: float,
                     f_px: float, h_cam: float, x_of=None):
    """沿纵深生成路径点（远 → 近 或 近 → 远）。

    返回 [(x, y, scale_px_per_m), ...]，步长按真实深度等分，
    故屏幕上是不等间距的（近处疏、远处密）—— 这正是透视压缩。
    依据[3] y(Z) 双曲线关系，非手填坐标。
    """
    if n < 2:
        raise ValueError("n 必须 >= 2")
    out = []
    for i in range(n):
        t = i / (n - 1)
        z = z0 + (z1 - z0) * t
        y = y_at_depth(z, v_h, f_px, h_cam)
        # 横向分量：沿墙脊的 x 随深度线性插值（脊线在世界是直线）
        x = (x_of(z, t) if x_of else 0.0)
        out.append((x, y, scale_field(y, v_h, h_cam)))
    return out


def path_lateral(y: float, x0: float, x1: float, n: int, v_h: float, h_cam: float):
    """横向（平行画面）路径：y 恒定 → scale 恒定（铁律100 前段）。"""
    sf = scale_field(y, v_h, h_cam)
    return [(x0 + (x1 - x0) * i / (n - 1), y, sf) for i in range(n)]


def object_px_height(y_world: float, y_base: float, v_h: float, h_cam: float) -> float:
    """真实高 y_world(m) 的物体立于屏幕行 y_base 时的像素高。依据[1]。"""
    return y_world * scale_field(y_base, v_h, h_cam)


def self_check() -> bool:
    ck = []
    h_cam, v_h = 1.65, 300.0
    f = focal_px(960)

    # 1 缩放场随 y 线性：离地平线越远 scale 越大
    s1 = scale_field(400, v_h, h_cam)
    s2 = scale_field(800, v_h, h_cam)
    ck.append(("1 SF 随离地平线距离线性增长", abs(s2 / s1 - 5.0) < 1e-9))

    # 2 深度与 (y-v_h) 成反比
    z1 = depth_at(400, v_h, f, h_cam)
    z2 = depth_at(800, v_h, f, h_cam)
    ck.append(("2 深度与(y-v_h)成反比", abs(z1 / z2 - 5.0) < 1e-9))

    # 3 y(Z) 与 Z(y) 互逆
    ck.append(("3 y(Z) 与 Z(y) 互逆", abs(y_at_depth(z1, v_h, f, h_cam) - 400) < 1e-6))

    # 4 Hoiem(6) 与 ScaleField 自洽
    y_w, v_b = 1.70, 800.0
    px_h = object_px_height(y_w, v_b, v_h, h_cam)
    h_back = camera_height_from_ref(y_w, v_b - px_h, v_b, v_h)
    ck.append(("4 Hoiem(6)与ScaleField自洽", abs(h_back - h_cam) < 1e-9))

    # 5 横向路径 scale 恒定
    lat = path_lateral(800, 0, 500, 5, v_h, h_cam)
    ck.append(("5 横向路径scale恒定", len({round(p[2], 9) for p in lat}) == 1))

    # 6 纵深路径 scale 单调变化（远小近大）
    dep = path_along_depth(60.0, 12.0, 6, v_h, f, h_cam)
    sc = [p[2] for p in dep]
    ck.append(("6 纵深路径scale单调递增(近大)", all(sc[i] < sc[i + 1] for i in range(5))))

    # 7 纵深路径屏幕间距不等（透视压缩）
    ys = [p[1] for p in dep]
    gaps = [ys[i + 1] - ys[i] for i in range(5)]
    ck.append(("7 屏幕间距不等(远处密)", all(gaps[i] < gaps[i + 1] for i in range(4))))

    # 8 地平线上方拒绝（天空无尺度）
    try:
        scale_field(v_h - 1, v_h, h_cam)
        ck.append(("8 地平线上方拒绝", False))
    except ValueError:
        ck.append(("8 地平线上方拒绝", True))

    # 9 消失点法：三条延长线真正过 VP=(400,300) 的线段，应还原出 y=300
    #    构造方式：从 VP 出发取斜率 k，截取 y=900→500 的一段
    vp_x, vp_y = 400.0, v_h
    segs = []
    for k in (-0.5, 0.5, -0.2):
        x9 = vp_x + k * (900 - vp_y)
        x5 = vp_x + k * (500 - vp_y)
        segs.append((x9, 900, x5, 500))
    ck.append(("9 消失点法还原地平线", abs(horizon_from_vanishing(segs, 960) - vp_y) < 1e-6))
    ck.append(("9b 消失点法还原VP_x", abs(_seg_intersect(segs[0], segs[1])[0] - vp_x) < 1e-6))

    # 10 交点不足时报错而非静默
    try:
        horizon_from_vanishing([(0, 0, 1, 1)], 960)
        ck.append(("10 交点不足报错", False))
    except ValueError:
        ck.append(("10 交点不足报错", True))

    for name, ok in ck:
        print(("PASS " if ok else "FAIL ") + name)
    return all(ok for _, ok in ck)


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
