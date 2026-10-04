#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_common.py —— 跨模块原子复用库（单一定义，全局调用）

【存在理由】
审计发现以下逻辑在 8+ 个模块中被手写内联，每次改动都要改 N 处，
且各模块口径不一致（如 px_per_m 有的用画布高、有的用视口高）：
    px_per_m      出现 10 次  -> 统一为 pixels_per_meter()
    rad2deg       出现  5 次  -> 统一为 rad2deg / deg2rad
    beaufort      出现  3 次  -> 统一为 beaufort_scale()
    accel         同名 2 处    -> 统一为 uniform_accel / projectile
    ck (断言)     同名 4 处    -> 统一为 require()
    clamp         手写 3 处    -> 统一为 clamp()
    contact_shadow 同名 2 处   -> 统一为 contact_shadow()
    catmull_rom   仅 1 处      -> 收拢为 catmull_rom()

【铁律】
A. 新增数学/几何/单位换算原子，必须放本文件，禁止在业务模块内联。
B. 业务模块需用上述能力时，from _common import X，禁止复制实现。
C. 本文件只放无副作用的纯函数与常量，禁止 import 业务模块（防环）。
D. 改本文件 = 改全局口径，必须跑 _audit_dup.py 确认内联归零。
"""
import math
from typing import Sequence, Tuple

# ---------------- 常量 ----------------
PI = math.pi
DEG = 180.0 / PI   # 弧度 -> 度 的乘数
RAD = PI / 180.0   # 度  -> 弧度 的乘数

# 人体比例（业界定标，用于 biped 骨长）
# 来源：Dr. Jackie Chappell 人体比例研究 + 达芬奇维特鲁威人
HUMAN_PROPORTION = {
    "头":   0.125,   # 头高 / 身高
    "颈":   0.042,
    "躯干": 0.292,   # 肩到胯
    "上臂": 0.146,
    "前臂": 0.125,
    "手":   0.058,
    "大腿": 0.250,
    "小腿": 0.188,
    "足":   0.042,
}  # 合计 = 1.268 -> 归一化见 below
LEG_RATIO = (HUMAN_PROPORTION["大腿"] + HUMAN_PROPORTION["小腿"]) / sum(HUMAN_PROPORTION.values())  # 腿长/身高，归一化

# ---------------- 数值原子 ----------------
def clamp(x, lo, hi):
    """数值钳制。"""
    return max(lo, min(hi, x))

def lerp(a, b, t):
    """线性插值。t 在 [0,1]，越界按 clamp 处理。"""
    return a + (b - a) * clamp(t, 0.0, 1.0)

def smoothstep(edge0, edge1, x):
    """Smoothstep 平滑插值（Ken Perlin 定义）。"""
    t = clamp((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3 - 2 * t)

def catmull_rom(p0, p1, p2, p3, t):
    """Catmull-Rom 样条，过 p1,p2 两点。t∈[0,1]。
    业界足部轨迹标准：样条必须穿过落脚点（Girard & Maciejewski 1985）。
    """
    t2, t3 = t * t, t * t * t
    return 0.5 * (
        (2 * p1) +
        (-p0 + p2) * t +
        (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
        (-p0 + 3 * p1 - 3 * p2 + p3) * t3
    )

# ---------------- 角度/单位 ----------------
def rad2deg(r):
    return r * DEG

def deg2rad(d):
    return d * RAD

def normalize_deg(d):
    """角度归一化到 [0, 360)。"""
    return d % 360.0

def normalize_rad(r):
    """弧度归一化到 [0, 2π)。"""
    return r % (2 * PI)

# ---------------- 尺度（最关键：全局唯一口径） ----------------
def pixels_per_meter(view_h_px: float, view_h_m: float, crop_top: float = 0.0) -> float:
    """像素/米 换算。全局唯一实现，禁止各模块手写。

    Args:
        view_h_px: 画面可见高度（像素）。若用了顶部留天，须传入"实际可见高度"，
                   而非画布总高——这是过去 10 处内联口径不一致的 root cause。
        view_h_m:  画面可见高度对应的真实米数（由 camera.z + 视场决定）。
        crop_top:  顶部被裁掉的像素（天空/留白），用于从"画布高"反算"可见高"。
    Returns:
        px_per_m (float)
    """
    visible_px = view_h_px - crop_top
    if visible_px <= 0 or view_h_m <= 0:
        raise ValueError(f"pixels_per_meter: visible_px={visible_px} view_h_m={view_h_m} 非法")
    return visible_px / view_h_m

def meters_to_px(m: float, px_per_m: float) -> int:
    """米 -> 像素，四舍五入取整。"""
    return int(round(m * px_per_m))

def px_to_meters(px: int, px_per_m: float) -> float:
    return px / px_per_m

# ---------------- 风（蒲福 + 行业风速-频率关系） ----------------
# (等级, 名称, 风速下限 m/s, 风速上限 m/s, 旗帜 regime)
BEAUFORT = [
    (0,  "无风",   0.0,  0.2,  "垂挂"),
    (1,  "软风",   0.3,  1.5,  "微动"),
    (2,  "轻风",   1.6,  3.3,  "摆动"),
    (3,  "微风",   3.4,  5.4,  "飘扬"),
    (4,  "和风",   5.5,  7.9,  "展开"),
    (5,  "清风",   8.0, 10.7,  "猎猎"),
    (6,  "强风",  10.8, 13.8,  "平直"),
    (7,  "疾风",  13.9, 17.1,  "绷紧"),
    (8,  "大风",  17.2, 20.7,  "啪啪"),
    (9,  "烈风",  20.8, 24.4,  "剧烈"),
    (10, "狂风",  24.5, 28.4,  "撕裂"),
    (11, "暴风",  28.5, 32.6,  "失控"),
    (12, "飓风",  32.7, 99.0,  "破坏"),
]

def beaufort_scale(u: float) -> dict:
    """由风速 u(m/s) 得蒲福等级与旗帜 regime。
    过去在 environment / physics / physics_rules 三处重复，现统一。
    """
    for level, name, lo, hi, regime in BEAUFORT:
        if lo <= u <= hi:
            return {"level": level, "name": name, "regime": regime,
                    "u": u, "lo": lo, "hi": hi}
    raise ValueError(f"beaufort_scale: u={u} 超出范围")

def flag_undulation_period(L: float, u: float, c: float = 0.33) -> float:
    """【已废弃·铁律89】保留仅为兼容旧调用，新代码一律用 flag_motion()。

    废弃理由：Strouhal 涡脱落给的是高频颤动(10-40Hz)，不是整体飘扬。
    T=c·L/u 相当于 St=1/c=3.0，而文献 St_L≈0.23 → 频率快约 13 倍，
    实测 3 级风算出 5.33Hz（肉眼"抖成一片"），即为此 bug。
    """
    if u <= 0:
        return float("inf")
    return c * L / u


# 旗帜运动：按 regime 查表（铁律89）
# 依据：NWS 蒲福表逐风级旗帜描述 + MDPI 实测(inverted flag 6m/s≈2Hz, 8m/s≈1.5Hz)
#       + Virot 实验(高频颤动 flutter 可达 10-40Hz，属边缘振动非整体飘扬)
# 字段：(regime, 周期下限s, 周期上限s, A/L幅度比下限, 上限, 颤动Hz或None)
FLAG_MOTION = {
    "垂挂": (float("inf"), float("inf"), 0.00, 0.00, None),
    "微动": (6.00, 10.00, 0.01, 0.03, None),
    "摆动": (3.00,  6.00, 0.03, 0.08, None),
    "飘扬": (1.60,  3.00, 0.10, 0.22, None),   # 3级 light flag extended
    "展开": (1.00,  1.60, 0.25, 0.45, None),   # 4级 heavy flag flaps limply
    "猎猎": (0.70,  1.00, 0.55, 0.90, None),   # 5级 flaps over entire length
    "平直": (0.50,  0.70, 1.00, 1.40, 6.0),    # 6级 extends & flaps vigorously
    "绷紧": (0.38,  0.50, 1.40, 1.60, 10.0),   # 7级+
    "啪啪": (0.30,  0.38, 1.60, 1.60, 14.0),
    "剧烈": (0.25,  0.30, 1.60, 1.60, 18.0),
    "撕裂": (0.20,  0.25, 1.60, 1.60, 22.0),
    "失控": (0.18,  0.20, 1.60, 1.60, 26.0),
    "破坏": (0.15,  0.18, 1.60, 1.60, 30.0),
}


def flag_motion(regime: str, u: float = 0.0) -> dict:
    """旗帜整体运动：按 regime 查表得 (周期s, 幅度比A/L, 颤动Hz)。

    铁律89：不用裸 Strouhal。regime 由 beaufort_scale(u)['regime'] 提供。
    周期内按 u 在该风级区间的位置线性插值（风越大越快、幅度越大）。
    """
    if regime not in FLAG_MOTION:
        raise ValueError(f"flag_motion: 未知 regime={regime!r}，须先过 beaufort_scale")
    t_lo, t_hi, a_lo, a_hi, flutter = FLAG_MOTION[regime]
    if t_lo == float("inf"):
        return {"period_s": float("inf"), "freq_hz": 0.0,
                "amp_ratio": 0.0, "flutter_hz": None}
    bf = beaufort_scale(u)
    lo, hi = bf["lo"], bf["hi"]
    s = 0.0 if hi <= lo else max(0.0, min(1.0, (u - lo) / (hi - lo)))
    # 区间内：u 越大 -> 周期越短(越快)、幅度越大
    T = t_lo + (t_hi - t_lo) * (1.0 - s)
    A = a_lo + (a_hi - a_lo) * s
    return {"period_s": T, "freq_hz": (1.0 / T) if T > 0 else 0.0,
            "amp_ratio": A, "flutter_hz": flutter}

# ---------------- 运动学原子 ----------------
def uniform_accel(v0: float, a: float, t: float) -> Tuple[float, float]:
    """匀加速：返回 (位移, 末速度)。s = v0*t + 0.5*a*t^2"""
    return v0 * t + 0.5 * a * t * t, v0 + a * t

def projectile(v0: float, angle_deg: float, g: float = 9.8, t: float = 0.0) -> Tuple[float, float]:
    """抛体：返回 (x, y)，y 向上为正。"""
    a = deg2rad(angle_deg)
    return v0 * math.cos(a) * t, v0 * math.sin(a) * t - 0.5 * g * t * t

def gait_cycle_from_speed(speed_mps: float, stride_m: float) -> float:
    """由速度与步幅反推步态周期。铁律：speed = stride / cycle 必须成立。
    过去 T_MAN 硬编码 0.5s -> cadence=240 步/分（超跑步），现已废。
    """
    if stride_m <= 0:
        raise ValueError("gait_cycle_from_speed: stride_m 须 > 0")
    if speed_mps <= 0:
        return float("inf")
    return stride_m / speed_mps

def cadence_bpm(cycle_s: float) -> float:
    """步频（步/分）。步行 100-120，慢跑 160-180；>200 视为异常须告警。"""
    if cycle_s <= 0:
        return float("inf")
    return 120.0 / cycle_s

# ---------------- 校验原子 ----------------
def require(cond, msg: str):
    """断言：条件不成立即抛 ValueError。替代 4 处手写 ck()。"""
    if not cond:
        raise ValueError(f"[require] {msg}")

def contact_shadow(xy: Tuple[float, float], ground_y: float, tol: float = 1.0) -> bool:
    """支撑脚是否与地面接触。过去 chroma / composite 各写一份。

    注意语义：本函数是【判定函数】（触地与否），不是生成投影的那个
    contact_shadow。同名易混，新增判定请走 foot_contact()，
    它与生成投影的 composite.contact_shadow 语义不同，勿合并。
    """
    return abs(xy[1] - ground_y) <= tol


# ---- X_d 触地时刻标注 ----
# 业界启发式（准确率约 90%）：趾关节【全局速度模长】低于阈值即视为触地，
# 再叠趾高 sanity check 排除"脚在远处慢慢移动"的误判。
# 纯几何判定（contact_shadow 只看 |y-ground_y|<=tol）判不了滑动：
# 脚贴着地面滑行时位置条件依然成立 —— 这正是 foot sliding 的盲区。
CONTACT_V_MAX = 0.5      # m/s，趾关节速度上限（业界 0.1-0.5）
CONTACT_H_MAX = 0.10     # m，趾离地高度 sanity 上限
# 60Hz 数据优于 30Hz：速度用差分求，帧率越低噪声越大


def foot_contact(toe_xy, toe_vel, ground_y,
                 v_max: float = CONTACT_V_MAX,
                 h_max: float = CONTACT_H_MAX) -> bool:
    """触地判定：位置 + 速度 + 高度 三条件同时成立。

    toe_xy  : (x, y) 趾关节世界坐标（米）
    toe_vel : (vx, vy) 趾关节全局速度（m/s）
    ground_y: 地面高度（米）

    返回 True 视为该帧脚已锁定在地面（可进入 stance）。
    """
    import math
    dy = abs(toe_xy[1] - ground_y)
    if dy > h_max:
        return False                      # 离地太远，sanity 排除
    v = math.hypot(float(toe_vel[0]), float(toe_vel[1]))
    return v <= v_max                     # 速度超阈值 = 正在滑


def foot_contact_batch(toe_xy_seq, toe_vel_seq, ground_y, **kw):
    """批量判定：一次跑完整段序列，返回 bool 数组。"""
    import numpy as np
    xy = np.asarray(toe_xy_seq, dtype=np.float64)
    vel = np.asarray(toe_vel_seq, dtype=np.float64)
    dy = np.abs(xy[:, 1] - ground_y)
    v = np.hypot(vel[:, 0], vel[:, 1])
    return (dy <= kw.get("h_max", CONTACT_H_MAX)) & (v <= kw.get("v_max", CONTACT_V_MAX))

# ---------------- 帧工具 ----------------
def phase_of(t: float, period: float, phase_shift: float = 0.0) -> float:
    """归一化相位 φ∈[0,1)。period<=0 视为静止（返回 0）。"""
    if period <= 0:
        return 0.0
    return (t / period + phase_shift) % 1.0

def nearest_frame(t: float, fps: float) -> int:
    """时间 -> 帧序号。"""
    return int(round(t * fps))
