# 契约: proc/shape/line
#   一句话: 骨架模板 → 胶囊形体(带 region) → SDF → 轮廓线与细节线
#   完整契约见 shape/__init__.py
"""第一部分：画线。

骨架模板 → 形体（胶囊/椭圆，每根带 region 标签）→ SDF 场 → 线（轮廓线 + 细节线）。

关键设计：颜色挂 region（胶囊），不挂像素。
骨架一动，形体跟着动，颜色自然跟着走 —— 杜绝"披帛飘出身体""脚朝后"那类病。

比例来源：Drillis & Contini 1966（Winter 1990 转引）
五官位置：面部归一化锚点（眼 35%/65% 宽、35% 高，鼻 52%，嘴 72%）
"""
import math
import numpy as np

# ---------------------------------------------------------------- 比例
# Drillis & Contini 1966，段长/身高
_DC = {
    "thigh": 0.245, "shank": 0.246, "foot_h": 0.039,
    "upperarm": 0.186, "forearm": 0.146,
    "head": 0.130, "neck": 0.052, "trunk": 0.288,
    "pelvis_w": 0.191, "shoulder_w": 0.259,
}

# ---------------------------------------------------------------- 骨架模板
# 每个模板 = 关节表 + 胶囊表（a, b, r, region）
# r 是归一化半径（×身高）

def _humanoid():
    """人形：22 关节，两足。喜羊羊这类拟人角色复用这套，只换 region 和装饰。"""
    joints = ["pelvis", "waist", "chest", "neck", "head",
              "sh_l", "elb_l", "wri_l", "hand_l",
              "sh_r", "elb_r", "wri_r", "hand_r",
              "hip_l", "knee_l", "ank_l", "toe_l", "heel_l",
              "hip_r", "knee_r", "ank_r", "toe_r", "heel_r"]
    caps = [
        ("pelvis", "waist", 0.082, "robe"),
        ("waist", "chest", 0.088, "robe"),
        ("chest", "neck", 0.070, "robe"),
        ("sh_l", "elb_l", 0.034, "robe"), ("elb_l", "wri_l", 0.029, "skin"),
        ("sh_r", "elb_r", 0.034, "robe"), ("elb_r", "wri_r", 0.029, "skin"),
        ("hip_l", "knee_l", 0.052, "robe"), ("knee_l", "ank_l", 0.042, "robe"),
        ("hip_r", "knee_r", 0.052, "robe"), ("knee_r", "ank_r", 0.042, "robe"),
    ]
    return joints, caps


def _quadruped():
    """四足：21 关节（人 22）。差异：脊柱 2 段、无脚趾（脚即末端）、有尾 2 段。
    来源：dog_std.bvh 标准骨架。"""
    joints = ["hips", "spine", "spine1", "neck", "head",
              "shoulder_l", "arm_l", "forearm_l", "foot_l",
              "shoulder_r", "arm_r", "forearm_r", "foot_r",
              "upleg_l", "leg_l", "hindfoot_l",
              "upleg_r", "leg_r", "hindfoot_r",
              "tail", "tail1"]
    caps = [
        ("hips", "spine", 0.090, "fur"), ("spine", "spine1", 0.088, "fur"),
        ("spine1", "neck", 0.062, "fur"),
        ("shoulder_l", "arm_l", 0.038, "fur"), ("arm_l", "forearm_l", 0.032, "fur"),
        ("shoulder_r", "arm_r", 0.038, "fur"), ("arm_r", "forearm_r", 0.032, "fur"),
        ("upleg_l", "leg_l", 0.048, "fur"), ("leg_l", "hindfoot_l", 0.038, "fur"),
        ("upleg_r", "leg_r", 0.048, "fur"), ("leg_r", "hindfoot_r", 0.038, "fur"),
        ("hips", "tail", 0.026, "fur"), ("tail", "tail1", 0.020, "fur"),
    ]
    return joints, caps


TEMPLATES = {"humanoid": _humanoid, "quadruped": _quadruped}

# ---------------------------------------------------------------- 末端：手 / 脚
# 手三级 LOD（Khronos：单胶囊最便宜，多数场景够用；抓握才升级）
# 手的胶囊交给 shape/hand.py（真实指节比例与外展角）
def HAND_LOD(lod, s, region="skin"):
    from . import hand as _H
    return _H.caps(lod, s, region)
FOOT_CAPS = [("ank_{s}", "toe_{s}", 0.024, "sole"),
             ("ank_{s}", "heel_{s}", 0.024, "sole")]

# ---------------------------------------------------------------- 五官锚点
# 头部局部归一化坐标：(右, 下)，原点=头心，单位=头宽/头高
FACE_ANCHORS = {
    "forehead": (0.00, -0.30),
    "eye_l":    (-0.15, -0.05),   # 水平 35% → 距中心 -0.15
    "eye_r":    (0.15, -0.05),    # 水平 65% → +0.15
    "nose":     (0.00, 0.16),     # 52% 处
    "mouth":    (0.00, 0.38),     # 72% 处
    "chin":     (0.00, 0.60),
    "ear_l":    (-0.42, 0.00),
    "ear_r":    (0.42, 0.00),
}

# 细节线：寥寥几笔（沿胶囊的笔画，不是几何外扩）
STROKE_SPEC = {
    "humanoid": [("chest", "waist", 3, "robe"),     # 衣纹 3 道
                 ("head", None, 2, "hair")],         # 发纹 2 道
    "quadruped": [("spine", "hips", 2, "fur")],
}


def build_body(template="humanoid", hand_lod=0, body_h=1.70):
    """返回 (关节名表, 胶囊表[(a,b,r,region)], 末端脚表)。"""
    if template not in TEMPLATES:
        raise KeyError(f"未知模板 {template}，可用 {list(TEMPLATES)}")
    joints, caps = TEMPLATES[template]()
    if template == "humanoid":
        from . import hand as _H
        for s in ("l", "r"):
            joints += _H.joints(hand_lod, s)
            caps += _H.caps(hand_lod, s, "skin")
            caps += [(a.format(s=s), b.format(s=s), r, reg)
                     for a, b, r, reg in FOOT_CAPS]
    return joints, caps, _DC


# ---------------------------------------------------------------- SDF 基元
def sd_capsule(px, py, ax, ay, bx, by, r):
    pax, pay = px - ax, py - ay
    bax, bay = bx - ax, by - ay
    h = np.clip((pax * bax + pay * bay) / (bax * bax + bay * bay + 1e-12), 0.0, 1.0)
    dx, dy = pax - bax * h, pay - bay * h
    return np.sqrt(dx * dx + dy * dy) - r


def sd_ellipse(px, py, cx, cy, rx, ry):
    qx, qy = (px - cx) / rx, (py - cy) / ry
    return (np.sqrt(qx * qx + qy * qy) - 1.0) * min(rx, ry)


def smin(a, b, k=0.0):
    if k <= 0:
        return np.minimum(a, b)
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0.0, 1.0)
    return b * (1 - h) + a * h - k * h * (1 - h)


# ---------------------------------------------------------------- 场
def field(caps_ell, pad=6.0, smooth=1.0):
    """caps_ell = (胶囊表[(ax,ay,bx,by,r)], 头椭圆表[(cx,cy,rx,ry)])
    返回 (d, (x0,y0), d_head)。d_head 供肤色蒙版用。"""
    caps, ell = caps_ell
    xs, ys, rs = [], [], []
    for ax, ay, bx, by, r in caps:
        xs += [ax, bx]; ys += [ay, by]; rs.append(r)
    for cx, cy, rx, ry in ell:
        xs += [cx - rx, cx + rx]; ys += [cy - ry, cy + ry]; rs.append(max(rx, ry))
    m = 2.0 * max(rs) + pad
    x0 = float(int(min(xs) - m)); y0 = float(int(min(ys) - m))
    W = max(8, int(max(xs) + m - x0)); H = max(8, int(max(ys) + m - y0))
    gx = np.arange(W, dtype=np.float32) + x0
    gy = np.arange(H, dtype=np.float32) + y0
    PX, PY = np.meshgrid(gx, gy)
    d = np.full((H, W), 1e6, np.float32)
    for ax, ay, bx, by, r in caps:
        d = smin(d, sd_capsule(PX, PY, ax, ay, bx, by, r), k=smooth)
    dh = None
    for cx, cy, rx, ry in ell:
        e = sd_ellipse(PX, PY, cx, cy, rx, ry)
        dh = e if dh is None else np.minimum(dh, e)
        d = smin(d, e, k=smooth)
    if dh is None:
        dh = np.full((H, W), 1e6, np.float32)
    return d, (x0, y0), dh


# ---------------------------------------------------------------- 线
def outline(d, w=1.6):
    """轮廓线 = SDF 的天然副产品：abs(d) - w。一行数学，不用几何外扩。
    因为 d 每帧按关节重算，轮廓自动跟着骨架走。"""
    return np.abs(d) - w


def detail_lines(d, density=120.0, w=0.9):
    """内部等高线（衣纹/发纹/肌理）。density 就是线密度，可调。"""
    return np.abs(0.8 + 0.2 * np.cos(density * d)) - w


def stroke_mask(d, w=1.6, inner=0.9):
    """轮廓 + 内部等高线，合成描边蒙版。"""
    o = outline(d, w) < 0
    i = np.logical_and(d < -1.5, detail_lines(d, w=inner) < 0)
    return np.logical_or(o, i)


# ---------------------------------------------------------------- 五官
def face_points(head_xy, head_r, yaw=90.0, front=False):
    """五官锚点 → 屏幕坐标。挂在头骨局部，头一转五官跟着转。
    front=False（侧脸）只画靠观众那半边。"""
    hx, hy = head_xy
    out = {}
    for name, (rx, ry) in FACE_ANCHORS.items():
        # 侧脸时横向压缩（脸只剩一半宽）
        sx = rx * head_r * (1.0 if front else 0.45)
        out[name] = (hx + sx, hy + ry * head_r)
    return out


def draw_face(cv, pts, ink=(40, 30, 26), front=False, w=2):
    """寥寥几笔画出眼鼻嘴耳。"""
    d = cv.d
    if front:
        for k in ("eye_l", "eye_r"):
            x, y = pts[k]
            d.ellipse([x - 4, y - 2, x + 4, y + 2], fill=ink)
        x, y = pts["mouth"]
        d.line([x - 6, y, x + 6, y], fill=ink, width=w)
    else:
        x, y = pts["eye_r"] if "eye_r" in pts else pts["eye_l"]
        d.ellipse([x - 3, y - 2, x + 3, y + 2], fill=ink)
    x, y = pts["nose"]
    d.line([x, y - 3, x, y + 3], fill=ink, width=w)
    return pts
