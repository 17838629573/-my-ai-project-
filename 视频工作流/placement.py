# -*- coding: utf-8 -*-
"""语义定位点：把一个语义点 → 世界坐标落位。

只算坐标，不画像素。
业界依据见 contracts/placement.md。
"""
import math

SEMANTIC_KINDS = ("ground_contact", "base", "root", "center_mass", "attach")

# 语义点定义：(u 取法, v 取法, 是否需要 shape)
#   u/v 均为源画布（未裁剪）坐标系，左上原点
_SPEC = {
    "ground_contact": (0.5, 1.0, False),   # 底部中心接地
    "base":           (0.5, 1.0, False),   # 基座/杆底中心
    "root":           (0.5, 1.0, False),   # 根部中心
    "center_mass":    (0.5, 0.5, False),   # 质心
    "attach":         (None, None, True),  # 附着点，比例由 AI 声明
}


def semantic_point(kind, canvas_w, canvas_h, shape=None):
    """源画布内语义点像素坐标。shape 仅 attach 需要：{"ratio":(rx,ry)}"""
    if kind not in SEMANTIC_KINDS:
        raise ValueError("未知语义点类型 %r，可选 %s" % (kind, list(SEMANTIC_KINDS)))
    ru, rv, need_shape = _SPEC[kind]
    if need_shape:
        if not shape or "ratio" not in shape:
            raise ValueError("attach 语义点必须由 AI 声明 shape['ratio']=(rx,ry)")
        rx, ry = shape["ratio"]
        for r in (rx, ry):
            if not (0.0 <= r <= 1.0):
                raise ValueError("attach ratio 必须在 [0,1]，收到 %r" % (shape["ratio"],))
        ru, rv = rx, ry
    return (canvas_w * ru, canvas_h * rv)


def attach_point(kind, canvas_w, canvas_h, ratio=None):
    """附着类语义点。ratio=(rx,ry) 由 AI 声明。"""
    return semantic_point(kind, canvas_w, canvas_h, {"ratio": ratio} if ratio else None)


def place(regpoint, target_xy, scale=None):
    """把 regpoint 的语义点落到 target_xy，返回落位矩形 {x0,y0,w,h}。

    regpoint: {"kind","canvas_w","canvas_h","trim":(tx,ty,tw,th)|None,"shape":...}
    target_xy: 语义点应落在的世界像素 (x, y)
    """
    if not isinstance(regpoint, dict):
        raise ValueError("regpoint 必须是 dict")
    kind = regpoint.get("kind")
    if kind not in SEMANTIC_KINDS:
        raise ValueError("regpoint 缺合法 kind，收到 %r" % (kind,))
    cw = regpoint.get("canvas_w")
    ch = regpoint.get("canvas_h")
    if not cw or not ch:
        raise ValueError("regpoint 必须给 canvas_w/canvas_h（未裁剪源尺寸）")

    u, v = semantic_point(kind, cw, ch, regpoint.get("shape"))

    trim = regpoint.get("trim")
    if trim is None:
        tx, ty, tw, th = 0.0, 0.0, float(cw), float(ch)
    else:
        if len(trim) != 4:
            raise ValueError("trim 必须是 (tx,ty,tw,th)")
        tx, ty, tw, th = [float(t) for t in trim]
        if tx < 0 or ty < 0 or tx + tw > cw + 1e-9 or ty + th > ch + 1e-9:
            raise ValueError("trim 矩形越出源画布: trim=%s canvas=%sx%s"
                             % (trim, cw, ch))

    s = 1.0 if scale is None else float(scale)
    if s <= 0:
        raise ValueError("scale 必须 > 0，收到 %r" % (scale,))

    # 语义点在裁剪图内的相对位置 → 缩放后偏移
    x0 = target_xy[0] - s * (u - tx)
    y0 = target_xy[1] - s * (v - ty)
    return {"x0": x0, "y0": y0, "w": tw * s, "h": th * s}


def verify(regpoint, target_xy, rect, tol=1e-6):
    """反算：给定落位矩形，语义点是否真的在 target_xy 上。"""
    kind = regpoint["kind"]
    cw = regpoint["canvas_w"]
    ch = regpoint["canvas_h"]
    u, v = semantic_point(kind, cw, ch, regpoint.get("shape"))
    trim = regpoint.get("trim")
    tx, ty = (0.0, 0.0) if trim is None else (float(trim[0]), float(trim[1]))
    s = rect["w"] / ((trim[2] if trim else cw) or cw)
    px = rect["x0"] + s * (u - tx)
    py = rect["y0"] + s * (v - ty)
    err = math.hypot(px - target_xy[0], py - target_xy[1])
    return {"err_px": err, "ok": err <= tol, "point": (px, py)}


def self_check():
    fails = []
    total = [0]
    def ck(name, cond, info=""):
        total[0] += 1
        print(("PASS " if cond else "FAIL ") + name + (("  " + info) if info else ""))
        if not cond:
            fails.append(name)

    # 1 语义点基本正确
    u, v = semantic_point("ground_contact", 360, 360)
    ck("接地=底部中心", (u, v) == (180.0, 360.0), "(%g,%g)" % (u, v))
    u, v = semantic_point("center_mass", 200, 400)
    ck("质心=正中", (u, v) == (100.0, 200.0), "(%g,%g)" % (u, v))

    # 2 attach 必须声明比例
    try:
        semantic_point("attach", 100, 100)
        ck("attach缺比例报错", False)
    except ValueError:
        ck("attach缺比例报错", True)

    # 3 未知类型报错
    try:
        semantic_point("head", 100, 100)
        ck("未知类型报错", False)
    except ValueError:
        ck("未知类型报错", True)

    # 4 无 trim 落位：语义点命中 target
    rp = {"kind": "ground_contact", "canvas_w": 360, "canvas_h": 360}
    tgt = (500.0, 800.0)
    r = place(rp, tgt)
    ck("无trim落位命中", verify(rp, tgt, r)["ok"],
       "err=%.2e" % verify(rp, tgt, r)["err_px"])

    # 5 trim 后仍命中（铁律74 核心）
    #    源 360×360，可见内容在 (40,20)-(300,340)，裁剪后 260×320
    rp2 = dict(rp, trim=(40, 20, 260, 320))
    r2 = place(rp2, tgt)
    vd2 = verify(rp2, tgt, r2)
    ck("trim后仍命中", vd2["ok"], "err=%.2e" % vd2["err_px"])
    # 且裁剪图更小，落位左上角不同 —— 证明 trim 真被用上
    ck("trim改变落位", abs(r2["x0"] - r["x0"]) > 1e-6,
       "Δx0=%.1f" % (r2["x0"] - r["x0"]))

    # 6 缩放后仍命中
    r3 = place(rp, tgt, scale=0.5)
    ck("缩放后仍命中", verify(rp, tgt, r3)["ok"],
       "err=%.2e" % verify(rp, tgt, r3)["err_px"])

    # 7 铁律73：逐帧复用同一 regpoint，语义点世界坐标恒定
    #    模拟 8 帧不同可见宽度（业界 145→189 的例子）
    worlds = []
    for vis_w in (145, 160, 175, 189, 150, 168, 182, 155):
        tw, th = vis_w, 320
        tx = (360 - tw) / 2.0     # 水平居中摆放可见内容
        ty = 360 - th
        frp = dict(rp, trim=(tx, ty, tw, th))
        fr = place(frp, tgt)
        wpt = verify(frp, tgt, fr)
        worlds.append(wpt["point"])
    spread = max(math.hypot(p[0] - tgt[0], p[1] - tgt[1]) for p in worlds)
    ck("逐帧语义点恒定", spread < 1e-6, "最大偏差=%.2e px" % spread)

    # 7b 证伪：逐帧自动居中（业界禁止）会让接地点相对目标漂移
    #     做法是把裁剪矩形中心对到 target，此时"接地"语义点会偏离 h/2
    drift = []
    for vis_w in (145, 160, 175, 189, 150, 168, 182, 155):
        th2 = 320.0
        cy = tgt[1] - th2 / 2.0                   # 矩形中心对齐 target
        ground_y = cy + th2                       # 该帧"底边"实际所在
        drift.append(abs(ground_y - tgt[1]))      # 与期望接地点之差
    worst = max(drift)
    ck("证伪:auto-centering接地点漂移", worst > 1.0,
       "底边偏离目标 %.1f px（应为 0）" % worst)

    # 8 base 与 ground_contact 语义不同但同源公式
    rpb = {"kind": "base", "canvas_w": 120, "canvas_h": 480}
    ub, vb = semantic_point("base", 120, 480)
    ck("杆底=底部中心", (ub, vb) == (60.0, 480.0), "(%g,%g)" % (ub, vb))

    # 9 旗帜插墙头：杆底语义点落在墙顶 baseline
    wall_top = 450.0
    r_flag = place(rpb, (300.0, wall_top))
    vd = verify(rpb, (300.0, wall_top), r_flag)
    ck("旗杆底对齐墙顶", vd["ok"] and abs(r_flag["y0"] + r_flag["h"] - wall_top) < 1e-6,
       "杆底y=%.1f 墙顶=%.1f" % (r_flag["y0"] + r_flag["h"], wall_top))

    # 10 越界 trim 报错
    try:
        place(dict(rp, trim=(300, 300, 200, 200)), tgt)
        ck("越界trim报错", False)
    except ValueError:
        ck("越界trim报错", True)

    print("\n共 %d 项，失败 %d -> %s" % (total[0], len(fails), "PASS" if not fails else "FAIL %s" % fails))
    return len(fails)


if __name__ == "__main__":
    import sys
    sys.exit(1 if self_check() else 0)
