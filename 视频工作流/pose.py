#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pose —— 统一姿态求解器：FK 引擎 + 解析 IK + 笛卡尔足端轨迹

业界依据（本轮搜证）
  · FK：姿势 = 每关节局部旋转，经骨架层级递归合成世界坐标
        （Puppeteer / Learned-Motion-Matching / Jacobson LBS 一致）
  · Girard & Maciejewski 1985：足部轨迹必须在【笛卡尔空间】定义，
    关节空间插值无法让脚沿曲线走或落在指定地面点
  · 足端摆动：x = step·(3s²-2s³)，z = h·4s(1-s)（起终点速度为零）
  · 支撑期：脚世界坐标恒定（TOWR+ 参数化：stance = constant position）
  · 站/坐/躺 = 同一套关节角度的不同配置；过渡用余弦 (0~π) 归一化
  · speed = stride / cycle，cadence = 120 / cycle

铁律67 统一 COCO-17 输出，禁自定义骨架
铁律68 足部轨迹在笛卡尔空间定义；支撑期脚世界坐标恒定
铁律69 speed=stride/cycle，cadence=120/cycle，禁各自手填
铁律70 环节长度/关节角度属物性，由 AI 搜证传入，代码禁内置
铁律72 禁硬编码关节坐标表——姿态必须由 FK 从「角度+骨长」算出

依赖: 无
被依赖: solver（拟）, build_video（拟）
改前必读: IMPROVE_pose.md
"""
from __future__ import annotations
import math

# ---------- COCO-17 ----------
NAMES = ["nose", "l_eye", "r_eye", "l_ear", "r_ear",
         "l_shoulder", "r_shoulder", "l_elbow", "r_elbow", "l_wrist", "r_wrist",
         "l_hip", "r_hip", "l_knee", "r_knee", "l_ankle", "r_ankle"]
BONES = [(0, 1), (0, 2), (1, 3), (2, 4), (5, 6), (5, 7), (6, 8), (7, 9), (8, 10),
         (5, 11), (6, 12), (11, 12), (11, 13), (12, 14), (13, 15), (14, 16),
         (0, 5), (0, 6)]

# 骨段：(父, 子, 骨长键, 角度键)  —— 结构属于骨架定义，不是物性
SEGS = [
    ("pelvis", "neck", "trunk", "a_trunk"),
    ("neck", "nose", "head", "a_head"),
    ("neck", "l_shoulder", "shoulder_half", "a_shoulder_l"),
    ("neck", "r_shoulder", "shoulder_half", "a_shoulder_r"),
    ("l_shoulder", "l_elbow", "upperarm", "a_upperarm_l"),
    ("r_shoulder", "r_elbow", "upperarm", "a_upperarm_r"),
    ("l_elbow", "l_wrist", "forearm", "a_forearm_l"),
    ("r_elbow", "r_wrist", "forearm", "a_forearm_r"),
    ("pelvis", "l_hip", "hip_half", "a_hip_l"),
    ("pelvis", "r_hip", "hip_half", "a_hip_r"),
    ("l_hip", "l_knee", "thigh", "a_thigh_l"),
    ("r_hip", "r_knee", "thigh", "a_thigh_r"),
    ("l_knee", "l_ankle", "shank", "a_shank_l"),
    ("r_knee", "r_ankle", "shank", "a_shank_r"),
]

# 面部特征：由 neck→nose 段按【比例】推出（比例属物性，AI 传）
FACE_KEYS = ("eye_back", "ear_back", "face_side")


class PoseError(ValueError):
    pass


def _need(d, key, where):
    if not isinstance(d, dict) or key not in d:
        raise PoseError(f"缺必填槽位 {where}.{key}（铁律70：物性由 AI 搜证传入，代码不内置）")
    return d[key]


def bone_lengths(spec):
    """身高 × 环节比例 -> 骨长(米)。比例由 AI 搜证传入。"""
    H = _need(spec, "height_m", "spec")
    anthro = _need(spec, "anthro", "spec")
    out = {}
    for k in ("trunk", "head", "neck", "upperarm", "lowerarm", "hand",
              "thigh", "shank", "shoulder_half", "hip_half"):
        out[k] = H * _need(anthro, k, "anthro")
    out["forearm"] = out["lowerarm"] + out["hand"]
    return out


def fk(root, lengths, angles):
    """正向运动学：层级递归 child = rotate(parent) * offset + parent（2D）。"""
    pts = {"pelvis": (float(root[0]), float(root[1]))}
    for parent, child, lk, ak in SEGS:
        px, py = pts[parent]
        L = _need(lengths, lk, "lengths")
        a = math.radians(_need(angles, ak, "angles"))
        pts[child] = (px + L * math.cos(a), py + L * math.sin(a))
    return pts


def two_bone_ik(hip, target, L1, L2, knee_sign=-1):
    """解析两骨 IK（余弦定理），业界 Nicholls/Kyutech 同款闭式解。
    返回 (knee_pt, thigh_deg, shank_deg)。"""
    hx, hy = hip
    tx, ty = target
    dx, dy = tx - hx, ty - hy
    d = math.hypot(dx, dy)
    d = max(1e-9, min(d, L1 + L2 - 1e-9))
    gamma = math.acos(max(-1.0, min(1.0, (L1 * L1 + d * d - L2 * L2) / (2 * L1 * d))))
    phi = math.atan2(dy, dx)
    th1 = phi - knee_sign * gamma
    kx = hx + L1 * math.cos(th1)
    ky = hy + L1 * math.sin(th1)
    th2 = math.atan2(ty - ky, tx - kx)
    return (kx, ky), math.degrees(th1), math.degrees(th2)


def leg_of(L):
    """腿长（髋->踝）= 大腿 + 小腿。"""
    return L["thigh"] + L["shank"]


def hip_height(gait, L):
    """髋高由【步幅+腿长】反算（不手填）——保证 IK 可达。
    支撑期脚相对髋的最大水平偏移 a = stride·duty/2；
    髋到踝的垂直分量 v 需满足 v² + a² ≤ 腿长²（刚体约束）。"""
    stride = _need(gait, "stride_m", "gait")
    duty = _need(gait, "stance_ratio", "gait")
    ankle = float(gait.get("ankle_y_m", 0.065))
    a = stride * duty / 2.0
    L1, L2 = L["thigh"], L["shank"]
    # 铁律103：膝保持【落地屈膝角】，不可锁死 0°（业界 loading response 15~20°）
    kb = math.radians(float(gait.get("knee_land_bend_deg", 0.0)))
    # 余弦定理：膝弯 kb 时 髋->踝 距离 d
    d = math.sqrt(L1 * L1 + L2 * L2 + 2.0 * L1 * L2 * math.cos(kb))
    v2 = d * d - a * a
    if v2 <= 0:
        raise PoseError(
            f"步幅过大不可达: stride({stride}) duty({duty}) -> 半偏移{a:.3f} > 髋踝距{d:.3f}")
    return ankle + math.sqrt(v2)


from foot_lock import FootLock, cubic_inertialize as _cubic_inertialize, \
    FOOT_LOCK_DIST, FOOT_UNLOCK_DIST, FOOT_INERT_TIME

def foot_target(t, side, gait):
    """笛卡尔足端轨迹（铁律68）。
    支撑期：脚【世界坐标恒定】= 落脚点（灭 foot sliding）
    摆动期：x = step·(3s²-2s³)，z = h·4s(1-s)
    相位对齐：触地瞬间脚位于髋【前方】a=step·duty/2，离地时位于髋后方同量（对称）。"""
    cycle = _need(gait, "cycle_s", "gait")
    stride = _need(gait, "stride_m", "gait")
    duty = _need(gait, "stance_ratio", "gait")
    hgt = _need(gait, "swing_height_m", "gait")
    speed = _need(gait, "speed_m_s", "gait")
    ankle = float(gait.get("ankle_y_m", 0.065))
    a = stride * duty / 2.0
    step = stride / 2.0                            # 单步长（双脚交替间隔）
    X = speed * t
    side_off = 0.0 if side == "l" else step        # 双脚交替：同序列，差 half stride
    k = math.floor((X + a - side_off) / stride + 1e-9)  # eps 防浮点落上一步
    x0 = k * stride + side_off
    t_start = (x0 - a) / speed                 # 该脚触地时刻
    u = ((t - t_start) / cycle) % 1.0
    if u > 1.0 - 1e-9:                             # 触地瞬间的浮点回绕保护
        u = 0.0
    if u < duty:                               # 支撑期：世界坐标锁定
        return (x0, ankle), "stance"
    s = (u - duty) / max(1e-9, 1.0 - duty)
    return (x0 + stride * (3 * s * s - 2 * s ** 3),
            ankle + hgt * 4 * s * (1 - s)), "swing"


def blend_poses(a, b, w):
    """姿势过渡：余弦 (0~π) 加权（业界 STS 曲线）。"""
    w = max(0.0, min(1.0, w))
    we = 0.5 - 0.5 * math.cos(math.pi * w)
    out = {}
    for k in set(a) | set(b):
        va = _need(a, k, "pose_a") if k in a else 0.0
        vb = _need(b, k, "pose_b") if k in b else 0.0
        out[k] = va + (vb - va) * we
    return out


def _face(pts, face):
    nx, ny = pts["neck"]
    sx, sy = pts["nose"]
    ux, uy = sx - nx, sy - ny
    eb = _need(face, "eye_back", "face")
    ab = _need(face, "ear_back", "face")
    sd = _need(face, "face_side", "face")
    px, py = -uy, ux          # 头部方向的垂直单位向量
    def at(back, s):
        return (nx + ux * (1 - back) + px * s * sd,
                ny + uy * (1 - back) + py * s * sd)
    pts["l_eye"], pts["r_eye"] = at(eb, 1.0), at(eb, -1.0)
    pts["l_ear"], pts["r_ear"] = at(ab, 1.0), at(ab, -1.0)
    return pts


def solve(spec, mode, t=0.0):
    """统一入口 -> COCO-17 米制坐标（原点=地面脚下，y 向上）。"""
    L = bone_lengths(spec)
    poses = _need(spec, "poses", "spec")

    if mode in ("walk", "run"):                       # 笛卡尔足端驱动
        gait = _need(spec, "gait", "spec")
        speed = _need(gait, "speed_m_s", "gait")
        cycle = _need(gait, "cycle_s", "gait")
        stride = _need(gait, "stride_m", "gait")
        duty = _need(gait, "stance_ratio", "gait")
        hip_y = float(gait.get("hip_height_m", hip_height(gait, L)))
        hmax = hip_height(gait, L)                     # 可达上限（反算）
        if hip_y > hmax + 1e-9:
            raise PoseError(
                f"髋高{hip_y:.3f} 超过可达上限{hmax:.3f}（腿长{leg_of(L):.3f}，"
                f"步幅{stride} 需要更低髋部）")
        if abs(speed - stride / cycle) > 1e-6:         # 铁律69
            raise PoseError(f"铁律69 违反: speed({speed}) != stride/cycle({stride/cycle})")
        base = _need(poses, "stand", "poses")
        angles = dict(base)
        # 侧视投影：左右髋重合于骨盆正下方 hip_half 处（铁律99）
        # root=骨盆中心，故抬高 hip_half 使【髋点】恰好落在 hip_y，与 IK 起点一致
        angles["a_hip_l"] = -90.0
        angles["a_hip_r"] = -90.0
        root_y = hip_y + L["hip_half"]
        # 髋部垂直起伏 bob：业界 3~5cm，每步一次 => 一周期两次（铁律100）
        # 生理：双支撑期(u≈0/0.5)髋最低，单支撑中期(u≈0.25/0.75)髋最高
        bob = _need(gait, "bob_m", "gait")
        phase_u = (t / cycle) % 1.0
        # 只降不升：dy ∈ [-2·bob, 0]。若允许抬高，髋升高会把腿拉直到膝弯 0°，
        # 抵消铁律103 的落地屈膝（实测冲突：抬高位出现 0.0° 锁死）
        dy = -bob * math.cos(2.0 * math.pi * 2.0 * phase_u) - bob
        root_y += dy
        meta = {"hip_y": hip_y, "hip_y_max": hmax, "bob_dy": dy}
        for side in ("l", "r"):
            tgt, ph = foot_target(t, side, gait)
            meta[f"{side}_phase"] = ph
            meta[f"{side}_target"] = tgt
            # IK 起点 = 【实际髋点】（FK 中 l_hip/r_hip 的位置），不可再取骨盆中心
            hp = (speed * t, root_y - L["hip_half"])
            _, th, sh = two_bone_ik(hp, tgt, L["thigh"], L["shank"])
            angles[f"a_thigh_{side}"] = th
            angles[f"a_shank_{side}"] = sh
        # 手臂反相摆动（业界 counter-swing：手臂与同侧腿相位差半周期）
        # 角度约定 0=右 90=上 -90=下 180=左；摆幅由 AI 声明 gait.arm_swing_deg
        A = _need(gait, "arm_swing_deg", "gait")
        B = _need(gait, "elbow_bend_deg", "gait")
        # 归一化基准 = 支撑期脚相对髋的最大偏移 a，而非 stride/2
        # （用 stride/2 会把摆幅缩到 60%，业界实测手臂应与腿等幅反相）
        a = stride * duty / 2.0
        for side in ("l", "r"):
            # 同侧腿相对髋的前后量 -> 手臂反相（腿在前则臂在后，对角步态）
            rel = (meta[f"{side}_target"][0] - speed * t) / a
            rel = max(-1.0, min(1.0, rel))
            meta[f"{side}_rel"] = rel
            angles[f"a_upperarm_{side}"] = -90.0 - A * rel
            angles[f"a_forearm_{side}"] = angles[f"a_upperarm_{side}"] + B
        # 躯干侧倾：向支撑侧倾（业界 3~5°），由双脚前后差驱动（铁律101）
        lean = _need(gait, "torso_lean_deg", "gait")
        angles["a_trunk"] = 90.0 + lean * (meta["r_rel"] - meta["l_rel"]) * 0.5
        # 骨盆前后倾（侧视表现为 trunk 基座的相位摆动）（铁律102）
        rot = _need(gait, "pelvis_rot_deg", "gait")
        angles["a_trunk"] += rot * math.sin(2.0 * math.pi * phase_u)
        out = fk((speed * t, root_y), L, angles)
        meta["stance_lock"] = all(
            meta[f"{s}_phase"] == "stance" for s in ("l", "r"))
    else:                                              # 静态姿势：纯角度配置 + 落地约束
        angles = dict(_need(poses, mode, "poses"))
        out = fk((0.0, 0.0), L, angles)
        ymin = min(v[1] for v in out.values())         # 最低点贴地
        out = {k: (x, y - ymin) for k, (x, y) in out.items()}
        meta = {"mode": mode, "grounded": True}

    out = _face(out, _need(spec, "face", "spec"))
    joints = {n: out[n] for n in NAMES}
    return {"joints": joints, "meta": meta if mode in ("walk", "run") else {"mode": mode}}


# ================== 自检 ==================
def _chk(name, ok, info=""):
    print(f"{'PASS' if ok else 'FAIL'} {name}" + (f"  {info}" if info else ""))
    return bool(ok)


_MA = "BEGIN EXA" + "MPLES"      # 拼接避免扫描器删掉自己（自检自指）
_MB = "END EXA" + "MPLES"


def _scan_hardcode(*a, **k):
    from pose_selfcheck import _scan_hardcode as _f
    return _f(*a, **k)


def self_check(*a, **k):
    from pose_selfcheck import self_check as _f
    return _f(*a, **k)


if __name__ == "__main__":
    raise SystemExit(0 if self_check() else 1)