# -*- coding: utf-8 -*-
"""地面坐标反投影 + 世界弧长参数化。

【为什么必须存在】
路径的像素弧长 ≠ 世界弧长。实测：同一条路径 6 段世界长度均为 8.10m，
但像素长度为 238.2 / 98.4 / 53.8 / 33.8 / 23.3 / 17.0 px。
用像素弧长匀速推进 => 世界速度从 4.14 m/s 失控到 54.76 m/s（设定 1.5）。

【业界依据】
1) arXiv pinhole ground plane：v_img = f*H_c/Z  =>  Z = f*h/(y-v_h)
   （arXiv 2605.30161 "Why Far Looks Up" §A Ground-Plane Geometry）
2) Mode 7 affine ground plane：每扫描线世界距离/像素 z(sy)=h/(sy-s_h)【横向】，
   其梯度 dz/dsy = -h/(sy-s_h)^2【深度】。两者是不同公式，不可混用。
3) 弧长参数化（Frenet-Serret / arc-length parametrization）：
   s(t) = ∫|γ'(τ)|dτ，以 s 为参数时 |dγ/ds| = 1，
   把「路径几何」与「行进速度」彻底解耦。
   本项目：先在地面坐标系按米积分，再反查像素位置。

依赖: 无（纯数学，仅 math）
"""
import math


def _pt(p):
    return (float(p[0]), float(p[1]))


def cam_of(spec):
    """从 scene_spec 取相机参数。缺键报错而非静默回落（铁律96）。"""
    persp = (spec.get("path") or {}).get("perspective")
    if not persp:
        raise SystemExit("铁律96违规：scene_spec 缺 path.perspective，无法做地面反投影")
    need = ("horizon_y", "camera_height_m", "focal_px", "vanishing_pt")
    miss = [k for k in need if k not in persp]
    if miss:
        raise SystemExit("铁律96违规：path.perspective 缺 %s" % miss)
    vh = float(persp["horizon_y"])
    h = float(persp["camera_height_m"])
    if abs(h) < 1e-9:
        raise SystemExit("camera_height_m 不可为 0")
    vp = persp["vanishing_pt"]
    return {"v_h": vh, "h": h, "f": float(persp["focal_px"]),
            "v_x": float(vp[0]), "v_y": float(vp[1])}


def back_project(x, y, cam):
    """屏幕像素 -> 地面坐标（米）。返回 (X 横向米, Z 深度米)。"""
    dy = float(y) - cam["v_h"]
    if abs(dy) < 1e-9:
        raise ValueError("y 与地平线重合，无法反投影（深度为无穷）")
    Z = cam["f"] * cam["h"] / dy
    X = (float(x) - cam["v_x"]) * Z / cam["f"]
    return (X, Z)


def forward_project(X, Z, cam):
    """地面坐标（米）-> 屏幕像素。返回 (x, y)。"""
    if abs(Z) < 1e-9:
        raise ValueError("深度不可为 0")
    y = cam["v_h"] + cam["f"] * cam["h"] / Z
    x = cam["v_x"] + float(X) * cam["f"] / Z
    return (x, y)


def px_per_m_lateral(y, cam):
    """横向 px/m：用于人物【缩放】与【路宽】。=(y-v_h)/h"""
    return (float(y) - cam["v_h"]) / cam["h"]


def px_per_m_depth(y, cam):
    """深度 px/m：用于沿路径【推进】的屏幕速度曲线。=(y-v_h)^2/(f*h)"""
    d = float(y) - cam["v_h"]
    return d * d / (cam["f"] * cam["h"])


def world_arc_table(pts, cam):
    """地面坐标下的累积弧长表（单位：米）。

    返回 {XZ: [(X,Z)...], cum: [米...], total: 米, seg: [每段米...]}
    """
    pts = [_pt(p) for p in pts]
    if len(pts) < 2:
        raise ValueError("路径至少 2 个控制点")
    # 【防御】地平线以上不是可行走面（业界 Footprints CVPR2020）。
    #   实测：末点越地平线 10px -> 深度 -451.91m（相机背后），
    #   世界长度暴涨到 483m。必须报错，禁静默产出垃圾。
    bad = [(i, p) for i, p in enumerate(pts) if p[1] <= cam["v_h"] + 1e-6]
    if bad:
        raise SystemExit(
            "铁律98违规：路径控制点在地平线(y=%s)之上，不是可行走面。违规点=%s"
            % (cam["v_h"], [(i, (round(a, 1), round(b, 1))) for i, (a, b) in bad]))
    XZ = [back_project(p[0], p[1], cam) for p in pts]
    if any(z <= 0 for _, z in XZ):
        raise SystemExit("路径反投影出现非正深度，请检查 perspective 声明")
    seg, cum = [], [0.0]
    for i in range(len(XZ) - 1):
        d = math.hypot(XZ[i + 1][0] - XZ[i][0], XZ[i + 1][1] - XZ[i][1])
        seg.append(d)
        cum.append(cum[-1] + d)
    return {"XZ": XZ, "cum": cum, "seg": seg, "total": cum[-1]}


def at_world_distance(wt, wtable, cam):
    """按【世界米】取屏幕点。匀速走米 => 自动产生正确的透视减速曲线。

    wt: 从起点算起的行走米数（可为任意实数，内部对 total 取模实现循环）
    返回 {xy: (x,y) 屏幕, XZ: (X,Z) 地面, d: 归一化后的米数}
    """
    total = wtable["total"]
    if total <= 1e-9:
        raise ValueError("路径世界长度为 0")
    d = float(wt) % total
    cum = wtable["cum"]
    i = 0
    for k in range(len(wtable["seg"])):
        if d < cum[k + 1] or k == len(wtable["seg"]) - 1:
            i = k
            break
    span = wtable["seg"][i]
    u = (d - cum[i]) / span if span > 1e-9 else 0.0
    u = min(1.0, max(0.0, u))
    a, b = wtable["XZ"][i], wtable["XZ"][i + 1]
    X = a[0] + (b[0] - a[0]) * u
    Z = a[1] + (b[1] - a[1]) * u
    return {"xy": forward_project(X, Z, cam), "XZ": (X, Z), "d": d}


def px_arc_to_meter(pts, s_px, wtable, pcum=None):
    """像素弧长 -> 世界米（用于把旧的像素制起始站位换算到米制）。

    同一条折线段内，像素参数 u 与世界参数 u 一致（线性插值同构），
    因此：像素弧长落在第 k 段、段内比例 u => 世界米 = cum[k] + seg[k]*u
    """
    import math as _m
    pts = [_pt(p) for p in pts]
    if pcum is None:
        pcum = [0.0]
        for i in range(len(pts) - 1):
            pcum.append(pcum[-1] + _m.hypot(pts[i+1][0]-pts[i][0],
                                            pts[i+1][1]-pts[i][1]))
    total_px = pcum[-1]
    if total_px <= 1e-9:
        raise ValueError("路径像素长度为 0")
    s = float(s_px) % total_px
    k = 0
    for i in range(len(pcum) - 1):
        if s < pcum[i + 1] or i == len(pcum) - 2:
            k = i
            break
    seg_px = pcum[k + 1] - pcum[k]
    u = (s - pcum[k]) / seg_px if seg_px > 1e-9 else 0.0
    return wtable["cum"][k] + wtable["seg"][k] * u


def hw_px_at(y, half_width_m, cam):
    """【V4】三角形路宽：横向半宽随深度收敛到消失点。

    业界依据（一点透视画法 / Visionaire way border）：
      路面两条边各自连到同一个消失点，所有横向标线都收敛过去；
      角色只能在这个透视多边形内行走。
    公式：px_per_m_lateral(y) = (y - v_h)/h，故 hw_px = half_width_m * (y-v_h)/h

    【旧实现的病】setup 时算一次固定值 = half_width_m * near_px_per_m，
      全程不变 —— 走廊是等宽矩形带，不是三角形。远端该 26.9px 处用了 141.2px。
    """
    return float(half_width_m) * px_per_m_lateral(y, cam)


def self_check():
    """自检：反投影/正投影互逆、弧长表、世界速度恒定。"""
    import math as _m
    fails = []
    cam = {"v_h": 482.0, "h": 3.366, "f": 1344.0, "v_x": 474.0, "v_y": 482.0}

    def ck(name, cond, detail=""):
        if not cond:
            fails.append("%s %s" % (name, detail))

    # 1 正反投影互逆
    for (x, y) in ((60.0, 878.8), (395.3, 557.4), (303.0, 645.9)):
        X, Z = back_project(x, y, cam)
        bx, by = forward_project(X, Z, cam)
        ck("1_互逆", abs(bx - x) < 1e-6 and abs(by - y) < 1e-6,
           "(%s,%s)->(%s,%s)" % (x, y, round(bx, 4), round(by, 4)))

    # 2 横向 px/m 与深度 px/m 是不同公式
    a = px_per_m_lateral(878.8, cam)
    b = px_per_m_depth(878.8, cam)
    ck("2_两公式不同", abs(a - b) > 1.0, "lateral=%s depth=%s" % (round(a, 2), round(b, 2)))
    ck("2b_横向值", abs(a - 117.88) < 0.5, str(round(a, 2)))
    ck("2c_深度值", abs(b - 34.80) < 0.5, str(round(b, 2)))

    # 3 实测路径：世界弧长 48.60m，像素弧长仅 7.99m
    pts = [(60.0, 878.8), (232.0, 714.0), (303.0, 645.9), (341.8, 608.7),
           (366.2, 585.3), (383.1, 569.2), (395.3, 557.4)]
    wt = world_arc_table(pts, cam)
    ck("3_世界弧长", abs(wt["total"] - 48.60) < 0.5, str(round(wt["total"], 2)))
    px = sum(_m.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
             for i in range(len(pts) - 1))
    ck("3b_低估倍数", wt["total"] / (px / 117.647) > 5.0,
       "%.1fx" % (wt["total"] / (px / 117.647)))

    # 4 核心：按米推进，世界速度必须恒定
    speed = 1.5
    prev_Z, vs = None, []
    for k in range(1, 9):
        t = k * 0.25
        r = at_world_distance(speed * t, wt, cam)
        Z = r["XZ"][1]
        if prev_Z is not None:
            vs.append((Z - prev_Z) / 0.25)
        prev_Z = Z
    ck("4_世界速度恒定", all(abs(v - speed) < speed * 0.05 for v in vs),
       "实测 %s" % [round(v, 3) for v in vs])

    # 5 屏幕速度必须是递减曲线（不是匀速）
    # 【修正】8 秒只走 12m / 全程 48.6m = 24.7%，仍在近段，减速幅度小。
    #   必须沿【全程】采样才能体现透视减速曲线。
    scr = []
    for k in range(6):
        frac = k / 5.0 * 0.999
        d0 = wt["total"] * frac
        p0 = at_world_distance(d0, wt, cam)["xy"]
        p1 = at_world_distance(d0 + speed / 60.0, wt, cam)["xy"]
        scr.append(_m.hypot(p1[0] - p0[0], p1[1] - p0[1]) * 60)
    ck("5_屏幕速度递减", scr[0] > scr[-1] * 10.0,
       "首=%.1f 末=%.1f px/s 降%.1fx" % (scr[0], scr[-1], scr[0] / max(scr[-1], 1e-9)))
    # 5b 全程各点世界速度恒定 1.5
    wz = []
    for k in range(6):
        d0 = wt["total"] * (k / 5.0 * 0.999)
        z0 = at_world_distance(d0, wt, cam)["XZ"][1]
        z1 = at_world_distance(d0 + speed / 60.0, wt, cam)["XZ"][1]
        wz.append((z1 - z0) * 60)
    ck("5b_全程世界速度恒定", all(abs(v - speed) < speed * 0.02 for v in wz),
       "实测 %s" % [round(v, 3) for v in wz])

    # 6 脚不越地平线：8 秒末仍在地平线下方
    end = at_world_distance(speed * 8.0, wt, cam)["xy"]
    ck("6_不越地平线", end[1] > cam["v_h"] + 50,
       "末帧y=%.1f vs 地平线%.1f" % (end[1], cam["v_h"]))

    # 7 边界：起点
    r0 = at_world_distance(0.0, wt, cam)
    ck("7_起点", abs(r0["xy"][0] - 60.0) < 1e-6 and abs(r0["xy"][1] - 878.8) < 1e-6,
       str(tuple(round(v, 3) for v in r0["xy"])))

    # 8 取模循环
    r_full = at_world_distance(wt["total"], wt, cam)
    ck("8_取模", abs(r_full["d"]) < 1e-6, str(round(r_full["d"], 6)))

    # 9【判据陷阱·勿再犯】三种曾导致误报的测量错误，此处锁死正确测法
    #   a) 横向/平行屏幕路径：不能用 ΔZ 衡量速度（横向走 ΔZ=0），
    #      必须用地面总位移 hypot(ΔX, ΔZ)
    flat = [(50.0, 800.0), (200.0, 800.0), (350.0, 800.0), (500.0, 800.0)]
    wf = world_arc_table(flat, cam)
    Xa, Za = at_world_distance(wf["total"] * 0.2, wf, cam)["XZ"]
    Xb, Zb = at_world_distance(wf["total"] * 0.2 + 1.0, wf, cam)["XZ"]
    ck("9a_平行屏幕用总位移", abs(math.hypot(Xb - Xa, Zb - Za) - 1.0) < 1e-3,
       "实测位移=%.4f" % math.hypot(Xb - Xa, Zb - Za))
    #   b) 折返路径：深度减小是正确行为，速度符号本就该为负，不是失控
    back = [(100.0, 860.0), (250.0, 760.0), (380.0, 660.0), (250.0, 760.0), (100.0, 860.0)]
    wb = world_arc_table(back, cam)
    zs = [at_world_distance(wb["total"] * k / 8.0 * 0.999, wb, cam)["XZ"][1]
          for k in range(9)]
    ck("9b_折返深度先增后减", max(zs) > zs[-1] and max(zs) > zs[0],
       "Z序列 %s" % [round(v, 1) for v in zs])
    #   c) 蜿蜒路径：跨折线段的两点直线距离 < 折线弧长，是测量假象。
    #      段内采样必须排除跨段区间，否则误报速度偏低（曾误报 8.62%）
    zig = [(200.0, 870.0), (280.0, 800.0), (150.0, 740.0), (300.0, 690.0),
           (180.0, 650.0), (320.0, 620.0), (240.0, 600.0)]
    wz = world_arc_table(zig, cam)

    def _seg_i(d):
        return max(j for j in range(len(wz["cum"]) - 1) if d >= wz["cum"][j] - 1e-9)

    vs2 = []
    for k in range(400):
        d0 = wz["total"] * k / 400.0 * 0.9999
        d1 = wz["total"] * (k + 1) / 400.0 * 0.9999
        if _seg_i(d0) != _seg_i(d1):
            continue                     # 排除跨段区间
        p0 = at_world_distance(d0, wz, cam)["XZ"]
        p1 = at_world_distance(d1, wz, cam)["XZ"]
        vs2.append(math.hypot(p1[0] - p0[0], p1[1] - p0[1]) / ((d1 - d0) / speed))
    ck("9c_蜿蜒段内恒速", len(vs2) > 100 and all(abs(v - speed) < speed * 0.01 for v in vs2),
       "n=%d 速度%.4f~%.4f" % (len(vs2), min(vs2), max(vs2)))

    # 9d【V4】三角形路宽必须收敛（不是常数）
    _hw1 = hw_px_at(878.8, 1.2, cam)
    _hw2 = hw_px_at(557.4, 1.2, cam)
    ck("9d_路宽收敛", _hw1 > _hw2 * 4.0,
       "近=%.1fpx 远=%.1fpx 收敛%.2fx" % (_hw1, _hw2, _hw1 / _hw2))
    ck("9d2_近端值", abs(_hw1 - 141.5) < 3.0, str(round(_hw1, 1)))
    ck("9d3_远端值", abs(_hw2 - 26.9) < 3.0, str(round(_hw2, 1)))
    ck("9d4_单调递减", all(
        hw_px_at(y, 1.2, cam) > hw_px_at(y - 100, 1.2, cam)
        for y in (878.8, 778.8, 678.8, 578.8)), "y 越小(越远)半宽越小")

    # 10 地平线防御：越界必须抛 SystemExit，禁静默
    try:
        world_arc_table([(100.0, 870.0), (300.0, 700.0), (400.0, 472.0)], cam)
        ck("10_地平线防御", False, "越界路径未报错")
    except SystemExit:
        ck("10_地平线防御", True)
    except Exception as e:
        ck("10_地平线防御", False, "抛了 %s 而非 SystemExit" % type(e).__name__)

    return fails


if __name__ == "__main__":
    f = self_check()
    print("FAIL %d" % len(f) if f else "PASS all")
    for x in f:
        print("  " + x)

