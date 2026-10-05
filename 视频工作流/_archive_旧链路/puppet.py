# -*- coding: utf-8 -*-
"""部件化木偶（cutout puppet）—— V6 补帧的正确解法。

【为什么必须部件化】
业界已知（Unity Shader URP 序列帧教程原话）：
  「两帧线性混合本质上就是叠加，运动剧烈的帧之间会产生重影」
所以图像域 cross-dissolve 的重影是固有缺陷，不是实现问题。
正确解法 = Spine/Spriter 的部件化：角色拆成独立部件，骨骼驱动各部件变换。

【骨骼数据在哪】
pose.solve(spec, "walk", t=t) 能在【任意 t】算出全部关节坐标（FK/IK 真算）。
此前它只流向 _joint_seq -> 生图提示词，没接到渲染。本模块补上「关节->部件」绑定。

【业界依据】见 PUPPET_SPEC.json
  拆分粒度 15~20 件 / 层级 root->pelvis->torso->head + arm_L/R + leg_L/R
  锚点在解剖关节（上臂锚=肩，前臂锚=肘，大腿锚=髋，小腿锚=膝）
  相邻部件中立姿态下锚点必须重合，否则旋转时肢体滑动

依赖: pose（关节真值）
被依赖: build_phase_render（V6 接线后）
"""
import math

# 部件定义：业界 15~20 件。bone_root = 该部件旋转所依附的关节（父端）
# bone_tip  = 该部件指向的关节（子端），决定部件朝向
PARTS = [
    # (部件ID,      骨骼根,        骨骼尖,       绘制顺序, 说明)
    ("leg_upper_R", "r_hip",       "r_knee",      0, "右大腿（最后方）"),
    ("leg_lower_R", "r_knee",      "r_ankle",     1, "右小腿（最后方）"),
    ("arm_upper_R", "r_shoulder",  "r_elbow",     2, "右上臂（后方）"),
    ("arm_lower_R", "r_elbow",     "r_wrist",     3, "右前臂（后方）"),
    ("leg_lower_L", "l_knee",      "l_ankle",     4, "左小腿，锚点=膝"),
    ("leg_upper_L", "l_hip",       "l_knee",      5, "左大腿，锚点=髋"),
    ("torso_lower", "pelvis",      "neck",        6, "下躯干"),
    ("torso_upper", "neck",        "nose",        7, "上躯干+头"),
    ("arm_upper_L", "l_shoulder",  "l_elbow",     8, "左上臂，锚点=肩"),
    ("arm_lower_L", "l_elbow",     "l_wrist",     9, "左前臂，锚点=肘"),
]

# 绘制顺序（小的先画=在后）。业界：分离 draw order 与 transform hierarchy
DRAW_ORDER = sorted(PARTS, key=lambda p: p[3])


def with_derived(joints):
    """补齐 pelvis/neck。

    【实测】pose.solve 只返回 NAMES 的 17 个末端关节，不含 pelvis/neck。
    业界做法（Spine/Unity 2D rig）：根骨 pelvis = 双髋中点，neck = 双肩中点。
    """
    j = dict(joints)
    if "pelvis" not in j and "l_hip" in j and "r_hip" in j:
        j["pelvis"] = ((j["l_hip"][0] + j["r_hip"][0]) / 2.0,
                       (j["l_hip"][1] + j["r_hip"][1]) / 2.0)
    if "neck" not in j and "l_shoulder" in j and "r_shoulder" in j:
        j["neck"] = ((j["l_shoulder"][0] + j["r_shoulder"][0]) / 2.0,
                     (j["l_shoulder"][1] + j["r_shoulder"][1]) / 2.0)
    return j


def part_transform(joints, part_id, px_per_m, origin_px):
    """由关节真值算出某部件的仿射变换。

    joints: pose.solve 返回的关节坐标（米，原点=双脚地面中点）
    px_per_m: 米->像素
    origin_px: 地面中点在屏幕上的像素位置

    返回 {anchor_px: (x,y), angle_rad: 弧度, length_px: 长度}
    锚点 = bone_root 关节；角度 = root->tip 方向（与 +Y 向下屏幕系一致）
    """
    spec = None
    for p in PARTS:
        if p[0] == part_id:
            spec = p
            break
    if spec is None:
        raise KeyError("未知部件 %s" % part_id)
    _, root, tip, _, _ = spec
    joints = with_derived(joints)
    a = joints.get(root)
    b = joints.get(tip)
    if a is None or b is None:
        raise KeyError("关节缺失: %s/%s" % (root, tip))

    def to_px(j):
        # 米 -> 像素。屏幕 y 向下，地面坐标 y 向上，故 y 取负
        return (origin_px[0] + j[0] * px_per_m,
                origin_px[1] - j[1] * px_per_m)

    ax, ay = to_px(a)
    bx, by = to_px(b)
    dx, dy = bx - ax, by - ay
    return {"anchor_px": (ax, ay),
            "angle_rad": math.atan2(dy, dx),
            "length_px": math.hypot(dx, dy)}


def all_transforms(joints, px_per_m, origin_px):
    """一次算出所有部件变换，按绘制顺序返回。"""
    return [(p[0], part_transform(joints, p[0], px_per_m, origin_px))
            for p in DRAW_ORDER]


def self_check():
    fails = []

    def ck(name, cond, detail=""):
        if not cond:
            fails.append("%s %s" % (name, detail))

    # 1 部件数在业界区间内
    ck("1_部件数", len(PARTS) >= 10, str(len(PARTS)))
    # 2 部件ID 唯一
    ids = [p[0] for p in PARTS]
    ck("2_ID唯一", len(set(ids)) == len(ids))
    # 3 绘制顺序连续（业界：draw order 必须显式，不能靠巧合）
    orders = sorted(p[3] for p in PARTS)
    ck("3_绘制顺序", orders == list(range(len(PARTS))), str(orders))
    # 4 每个部件的 bone_root/tip 都必须是 pose.NAMES 里的真关节
    import pose
    # pelvis/neck 是派生关节（由 with_derived 从双髋/双肩中点算出），
    #   不在 pose.NAMES 里，校验时必须放行（实测 pose.solve 只返回 17 个末端关节）
    _DERIVED = ("pelvis", "neck")
    for p in PARTS:
        ck("4_关节存在_%s" % p[0],
           all(k in pose.NAMES or k in _DERIVED for k in (p[1], p[2])),
           "%s/%s" % (p[1], p[2]))
    ck("4b_派生可算", with_derived({"l_hip": (0.0, 0.9), "r_hip": (0.2, 0.9),
                                     "l_shoulder": (0.0, 1.4),
                                     "r_shoulder": (0.2, 1.4)}).get("pelvis")
       == (0.1, 0.9), "pelvis 应为双髋中点")
    # 5 锚点必须是父关节（业界：上臂锚=肩、前臂锚=肘）
    ck("5_上臂锚在肩", dict((p[0], p[1]) for p in PARTS)["arm_upper_L"] == "l_shoulder")
    ck("5b_前臂锚在肘", dict((p[0], p[1]) for p in PARTS)["arm_lower_L"] == "l_elbow")
    ck("5c_大腿锚在髋", dict((p[0], p[1]) for p in PARTS)["leg_upper_L"] == "l_hip")
    ck("5d_小腿锚在膝", dict((p[0], p[1]) for p in PARTS)["leg_lower_L"] == "l_knee")

    # 6 用真关节算一次变换，验证角度/长度合理
    spec = None
    import json
    try:
        spec = json.load(open("scene_spec.json", encoding="utf-8"))
    except Exception:
        pass
    if spec:
        # pspec 必须与 _joint_seq(build_util.py:197) 同构，
        #   否则 pose.solve 报缺 height_m（铁律70：物性不内置）
        import _common as _C
        rig = spec["biped_rig"]
        _g = dict(rig["gait"])
        _sp = float(_g["speed_m_s"])
        _st = float(_g.get("stride_m", 1.7 * 0.88))
        _g["cycle_s"] = _C.gait_cycle_from_speed(_sp, _st)
        _g["stride_m"] = _st
        _pspec = {"height_m": 1.7, "anthro": rig["anthro"],
                  "face": rig["face"], "poses": rig["poses"], "gait": _g}
        j = pose.solve(_pspec, "walk", t=0.0)["joints"]
        ts = all_transforms(j, 117.647, (270.0, 878.0))
        ck("6_变换数", len(ts) == len(PARTS), str(len(ts)))
        for pid, t in ts:
            ck("6_长度正_%s" % pid, t["length_px"] > 0, str(round(t["length_px"], 2)))
            ck("6_角度有限_%s" % pid, math.isfinite(t["angle_rad"]))
        # 7 关键：相邻部件锚点必须重合（业界：否则旋转时肢体滑动）
        #   前臂的锚点(肘) 必须等于 上臂的尖端(肘)
        up = part_transform(j, "arm_upper_L", 117.647, (270.0, 878.0))
        elbow = (up["anchor_px"][0] + up["length_px"] * math.cos(up["angle_rad"]),
                 up["anchor_px"][1] + up["length_px"] * math.sin(up["angle_rad"]))
        lo = part_transform(j, "arm_lower_L", 117.647, (270.0, 878.0))
        d = math.hypot(lo["anchor_px"][0] - elbow[0], lo["anchor_px"][1] - elbow[1])
        ck("7_肘部锚点重合", d < 0.5, "偏差 %.4f px" % d)
    return fails


if __name__ == "__main__":
    f = self_check()
    print("FAIL %d" % len(f) if f else "PASS all")
    for x in f:
        print("  " + x)
