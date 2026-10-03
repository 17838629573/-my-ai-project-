"""镜头意图 → 机位求解（纯函数层，零硬编码）

因果链（正推，禁止从图反推）：
    叙事意图(主体/景别/角度/共现) → 解机位(7自由度) → 透视 → 落点 → 指导生图

业界依据见 IMPROVE_camera.md：
  - 针孔模型  rho = f_px * h_subject / (tau * H)   景别决定距离
  - LensCraft(2025) 景别 scale：ELS 3.0 / LS 1.5 / FS 1.0 / ECU 0.5
  - 地平线    v_h = H/2 - f_px * tan(pitch)

输出 v_h(地平线) 与 h_cam(相机高) 正好是 _perspective / _surface 的输入口径。
"""
from __future__ import annotations
import math

__all__ = [
    "SHOT_SIZE", "ANGLE", "focal_px", "distance_for_tau",
    "horizon_y", "pitch_for_framing", "camera_height_for_angle",
    "project_point", "solve", "visibility_report", "self_check",
]

# 景别 → 主体占画面高度比例 tau。区间为业界常用容差。
# LensCraft(2025): ELS 3.0 / LS 1.5 / FS 1.0 / MCU 0.7 / ECU 0.5 (scale)
# scale 越大画面容纳越多 → tau = 1/scale 归一化到主体占画面比例。
SHOT_SIZE = {
    # name:      (tau,  scale, 说明)
    "ELS": (0.22, 3.0, "大远景，环境为主，人物小"),
    "LS":  (0.40, 1.5, "远景，全身+环境"),
    "FS":  (0.60, 1.0, "全景，人物占画面主体"),
    "MCU": (0.80, 0.7, "中近景，腰部以上"),
    "ECU": (1.00, 0.5, "特写，填满画面"),
}

# 机位角度 → 相机高度相对主体的比例 (0=主体底部, 1=主体顶部)
ANGLE = {
    "low":      (-0.25, "低机位仰视，主体显高大、有压迫感"),
    "eye":      ( 0.50, "平视，中性客观"),
    "high":     ( 1.30, "高机位俯视，压缩纵深、显渺小"),
    "bird":     ( 3.00, "鸟瞰，接近正俯视"),
}

F_OVER_IMAGE_H = 1.2  # f_px / H，约等于 55mm 全画幅竖构图等效


def focal_px(image_h: int, ratio: float = F_OVER_IMAGE_H) -> float:
    """焦距(像素) = 画面高 × 比例。与 _perspective.focal_px 同口径。"""
    return float(image_h) * float(ratio)


def distance_for_tau(h_subject_m: float, tau: float,
                     image_h: int, f_px: float = None) -> float:
    """景别决定距离：rho = f_px * h_subject / (tau * H)

    针孔模型：像高(px) = f_px * h / rho，要求像高 = tau * H。
    量纲：px = px * m / m ✓
    """
    f = focal_px(image_h) if f_px is None else float(f_px)
    if tau <= 0:
        raise ValueError("tau 必须 > 0")
    return f * float(h_subject_m) / (float(tau) * float(image_h))


def horizon_y(image_h: int, f_px: float, pitch_rad: float) -> float:
    """地平线在画面的 y = H/2 - f*tan(pitch)。pitch>0 为俯视(地平线上移)。"""
    return float(image_h) / 2.0 - float(f_px) * math.tan(float(pitch_rad))


def pitch_for_framing(y_target_m: float, h_cam_m: float, dist_m: float,
                      v_target_px: float, image_h: int, f_px: float) -> float:
    """求俯仰角，使世界点(距相机 dist, 高 y_target)投影到画面 v_target。

    局部线性模型（小角度精确，大角度由 solve 迭代收敛）：
        v = H/2 - f * ( (y-h_cam)*cos p + dist*sin p ) / ( dist*cos p - (y-h_cam)*sin p )
    以 p 为主元单调求解，用二分法保证收敛。
    """
    def v_of(p):
        dy, dz = y_target_m - h_cam_m, dist_m
        num = dy * math.cos(p) + dz * math.sin(p)
        den = dz * math.cos(p) - dy * math.sin(p)
        if den <= 1e-6:
            return float("-inf")
        return image_h / 2.0 - f_px * num / den

    lo, hi = -1.30, 1.30  # ±74.5°
    for _ in range(80):
        mid = (lo + hi) / 2.0
        if v_of(mid) > v_target_px:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def camera_height_for_angle(y_base_m: float, h_subject_m: float,
                            angle: str) -> float:
    """角度 → 相机高度：h_cam = y_base + ratio * h_subject"""
    if angle not in ANGLE:
        raise KeyError("未登记角度 %r，可用 %s" % (angle, sorted(ANGLE)))
    ratio = ANGLE[angle][0]
    return float(y_base_m) + ratio * float(h_subject_m)


def project_point(x_m, y_m, z_m, h_cam_m, z_cam_m, pitch_rad,
                  image_w, image_h, f_px):
    """把世界点投影到画面。相机在 (0, h_cam, z_cam)，光轴俯仰 pitch。

    forward=(0,-sin p,cos p)  up=(0,cos p,sin p)  right=(1,0,0)
    """
    dx = float(x_m)
    dy = float(y_m) - float(h_cam_m)
    dz = float(z_m) - float(z_cam_m)
    sp, cp = math.sin(pitch_rad), math.cos(pitch_rad)
    zc = -dy * sp + dz * cp
    yc = dy * cp + dz * sp
    if zc <= 1e-6:
        return None  # 在相机后方
    return (image_w / 2.0 + f_px * dx / zc,
            image_h / 2.0 - f_px * yc / zc,
            zc)


def solve(subject, must_include=None, shot_size="LS", angle="eye",
          image_w=540, image_h=960, v_target_ratio=0.55,
          f_ratio=F_OVER_IMAGE_H, dist_scale=1.0):
    """镜头意图 → 机位。

    subject:      dict{h_m, y_base_m, z_m, x_m} 主体（决定景别与距离）
    must_include: list[dict{name,h_m,y_base_m,z_m,x_m}] 必须同时入画的物体
    dist_scale:   距离倍数。景别给的是基准距离，共现约束装不下时须退远
                  （真实拍摄亦然：为了把两者都拍进去，摄影师往后退）。
                  退远会牺牲主体占比，tau_eff = tau/dist_scale 显式暴露。
    返回 dict，含 h_cam / z_cam / pitch / v_h / f_px / rho
    """
    if shot_size not in SHOT_SIZE:
        raise KeyError("未登记景别 %r，可用 %s" % (shot_size, sorted(SHOT_SIZE)))
    tau = SHOT_SIZE[shot_size][0]
    f_px = focal_px(image_h, f_ratio)
    if dist_scale < 1.0:
        raise ValueError("dist_scale 须 >= 1.0，景别只能退远不能推近")

    h_cam = camera_height_for_angle(subject["y_base_m"], subject["h_m"], angle)
    rho = distance_for_tau(subject["h_m"], tau, image_h, f_px) * float(dist_scale)
    # 相机在主体前方(更近) rho 处；沿 x 对齐主体，避免斜视
    z_cam = float(subject["z_m"]) - rho
    x_cam = float(subject.get("x_m", 0.0))

    v_target = v_target_ratio * image_h
    y_mid = float(subject["y_base_m"]) + 0.5 * float(subject["h_m"])
    pitch = pitch_for_framing(y_mid, h_cam, rho, v_target, image_h, f_px)
    v_h = horizon_y(image_h, f_px, pitch)

    return {
        "shot_size": shot_size, "angle": angle, "tau": tau,
        "dist_scale": float(dist_scale), "tau_eff": tau / float(dist_scale),
        "x_cam": x_cam, "h_cam": h_cam, "z_cam": z_cam,
        "pitch_rad": pitch, "pitch_deg": math.degrees(pitch),
        "f_px": f_px, "rho": rho, "v_h": v_h,
        "image_w": image_w, "image_h": image_h,
    }


def placeable_depth_range(cam, y_base_m=0.0, image_h=960, z_max=400.0):
    """机位定死后，给定平面高度上「仍在画面内」的深度区间 [z_near, z_far]。

    近端受画面下边限制（越近越往下出画），远端受地平线限制（无穷远收敛到 v_h）。
    返回 (z_near, z_far)；无解抛 ValueError —— 不返回伪区间。
    """
    import _perspective as P                  # 复用，不另写一份透视式
    v_h, f_px, h_cam = cam["v_h"], cam["f_px"], cam["h_cam"]
    # 高度 y_base_m 的平面 == 相机相对该平面高 (h_cam - y_base_m) 的地面
    def _y(z):
        return P.y_at_depth(z, v_h, f_px, h_cam - y_base_m)
    lo, hi = 1e-3, z_max
    if _y(z_max) > image_h:
        raise ValueError("该平面在 z<=%.0fm 内全部超出画面下边，须调整机位或平面高度" % z_max)
    for _ in range(80):                       # 二分求近端：y(z) 单调递减
        mid = 0.5 * (lo + hi)
        if _y(mid) > image_h:
            lo = mid
        else:
            hi = mid
    return (hi, z_max)


def solve_coappear(subject, must_include, image_w=540, image_h=960,
                   v_target_ratio=0.55, prefer=None, max_scale=12.0):
    """自动搜索满足共现约束的机位 —— 机位不该由人选，应由意图解出。

    在 (景别 × 角度) 网格上搜索：
      1. 满足 must_include 全部可见
      2. 优先 prefer(景别或角度)，其次取"主体占画面比例最大"者（画面最饱满）
    找不到就抛错并附每个候选的失败原因，绝不静默降级。
    """
    sizes = list(SHOT_SIZE)
    angles = list(ANGLE)
    # 退远档位由小到大；max_scale 是业务约束(退太远主体就没了)
    scales = [s for s in (1.0, 1.5, 2.0, 3.0, 5.0, 8.0, 12.0) if s <= max_scale]
    if not scales:
        raise ValueError("max_scale=%.1f 过小，无任何档位可用" % max_scale)
    if prefer:
        if prefer in SHOT_SIZE:
            sizes.sort(key=lambda s: (s != prefer, -SHOT_SIZE[s][0]))
        elif prefer in ANGLE:
            angles.sort(key=lambda a: a != prefer)
        else:
            raise KeyError("prefer 须为景别或角度，收到 %r" % prefer)

    tried, best = [], None
    for sc in scales:                      # 先小后退：主体尽量饱满
        for sz in sizes:
            for ang in angles:
                cam = solve(subject, shot_size=sz, angle=ang,
                            image_w=image_w, image_h=image_h,
                            v_target_ratio=v_target_ratio, dist_scale=sc)
                ok, rep = visibility_report(cam, must_include)
                tried.append((sz, ang, sc, ok))
                if ok:
                    # 画面最饱满 = tau_eff 最大
                    if best is None or cam["tau_eff"] > best["tau_eff"]:
                        best = cam
                        best["_report"] = rep
        if best is not None:
            break                          # 该退远档已可行，不再退
    if best is None:
        detail = "; ".join(
            "%s/%s×%.1f: %s" % (s, a, sc, ",".join(
                r["issue"] for r in visibility_report(
                    solve(subject, shot_size=s, angle=a, image_w=image_w,
                          image_h=image_h, dist_scale=sc), must_include)[1]
                if not r["ok"]))
            for s, a, sc, ok in tried if not ok)
        raise ValueError("无可行机位满足共现约束。已试 %d 组合：%s"
                         % (len(tried), detail[:600]))
    best["_tried"] = tried
    return best


def visibility_report(cam, must_include, margin_px=8.0):
    """共现校验：must_include 每个物体的底/顶是否都在画面内。

    返回 (ok, list[{name, ok, bottom_v, top_v, issue}])
    任一物体超出画面即 ok=False —— 这是叙事与几何的冲突点，须显式暴露。
    """
    out = []
    ok_all = True
    for o in (must_include or []):
        nb = project_point(o.get("x_m", 0.0), o["y_base_m"], o["z_m"],
                           cam["h_cam"], cam["z_cam"], cam["pitch_rad"],
                           cam["image_w"], cam["image_h"], cam["f_px"])
        nt = project_point(o.get("x_m", 0.0), o["y_base_m"] + o["h_m"], o["z_m"],
                           cam["h_cam"], cam["z_cam"], cam["pitch_rad"],
                           cam["image_w"], cam["image_h"], cam["f_px"])
        item = {"name": o.get("name", "?")}
        if nb is None or nt is None:
            item.update(ok=False, bottom_v=None, top_v=None,
                        issue="在相机后方或过近")
            ok_all = False
            out.append(item)
            continue
        bv, tv = nb[1], nt[1]
        issue = []
        if tv < -margin_px:
            issue.append("顶部超出画面上边 %.0fpx" % (-tv))
        if bv > cam["image_h"] + margin_px:
            issue.append("底部超出画面下边 %.0fpx" % (bv - cam["image_h"]))
        item.update(ok=not issue, bottom_v=bv, top_v=tv,
                    issue=";".join(issue) or "可见")
        if issue:
            ok_all = False
        out.append(item)
    return ok_all, out
