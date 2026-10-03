#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础层：共享常量 + 纯算术。零业务依赖。

契约: contracts/solver_split.md
改前必读: IMPROVE_solver_split.md
"""

import math



CONSTANTS = {
    "G":           9.81,      # 重力加速度
    "RHO_AIR":     1.225,     # 空气密度 kg/m3, 海平面 15C
    "NU_AIR":      1.5e-5,    # 空气运动粘度 m2/s
    "BETA1":       1.8751,    # 悬臂梁(clamped-free)一阶模态特征值，经典解
    "ST_TARGET":   0.2,       # Connell & Yue 2007: flapping 时 St≈0.2
    "MPH_PER_MS":  2.23694,   # 单位换算，非知识
}



# 【铁律32 教训】A_OVER_L=1.6 是 Izawa 实测的 **flapping 态** 峰峰比，
# 原代码无条件乘它 → 4级风下摆幅=旗长1.67倍，与蒲福表"flaps limply"矛盾。
# 现改为按风级查表，表由 AI 搜证后传入 criteria['amp_by_level']（铁律32）。
# 搜证来源：
#  - NWS 蒲福表逐风级旗帜描述（3级 extends light flag / 4级 flaps limply /
#    6级 extends & flaps vigorously / 7级 extends fully, flaps only at end /
#    8级 straight out and whipping）
#  - Rule of 4（射击/航海界经验定式）：旗面扬起角 θ ≈ 风速(mph)×4，
#    90°≈22.5mph、45°≈11.25mph、20°≈5mph
AMP_BY_LEVEL_DEFAULT = {
    0: 0.00, 1: 0.03, 2: 0.15, 3: 0.35, 4: 0.55,
    5: 0.85, 6: 1.20, 7: 1.60, 8: 1.60,
}




# ------------------------------------------------------------ 图集每格容纳性
# 【铁律47】业界搜证（contracts/sheet_cell.md）：
#  - lobehub agent-sprite-forge：exact shape / solid bg / **frame containment**
#    / same scale across frames —— 四条并列硬要求
#  - SummerEngine STRICT atlas：完整留在自己格内、格顶留净边距、放不下就缩小；
#    PLANTED FRAMING（各格同一足迹，绝不整体平移）
#  - Seele："Lock character height at 90% of frame height across all frames"
#  - AutoSprite：一格按最大姿态定尺寸；格间留 1–2px padding 防过滤采到邻格
# 【诚实说明】我前几轮口头的"60–70% 安全区"未在本轮搜证中直接命中；命中的
# 是 containment + 留边 + 同尺度 三条可量化更强的要求，百分比各源不一。
# 故这里不硬编码单一百分比（铁律32），上下限均可由 AI 在 spec 中覆盖。
CONTAINMENT = {
    "max_fill_w": 0.80,      # 主体 bbox 宽 ≤ 格宽 × 此值（防溢出触边）
    "max_fill_h": 0.80,      # 主体 bbox 高 ≤ 格高 × 此值
    "min_fill":   0.25,      # 主体 bbox 面积 ≥ 格面积 × 此值
    "margin_px":  8,         # 四边净边距 ≥ 此值
    "centroid_max": 0.10,    # planted 时质心漂移 ≤ 格宽 × 此值
    # 质心动不动是【语义判断】，不是算术：角色须立足不动，幡旗/枝条质心本来
    # 就该动。故由 AI 声明，缺失即报错（铁律31），不静默默认（铁律18）。
    "centroid_policy": None,   # "planted" | "free"，必填
    "area_spread":   0.35,     # 探针一致性阈值（铁律32 外置）
    "scale_spread":  0.25,
    "color_maxdist": 60.0,
}



# ============================================================ 普适常数
# 不随物体变，故留代码。凡随物体变的值一律由 AI 传入。
# 【铁律40】素材一张图集的最大格数：超过就必须拆成多次调用，
# 而跨调用一致性无法保证（实测跨图集差异是同图集内 1.77 倍）。
# 4x4=16 是清晰度与一致性的平衡点。
MAX_MAT_FRAMES = 16



# 【铁律48】先探针后升级：业界实测"第7格开始人物就开始变异"；
# 直接出 N=35 格，变异发生在第 30 格才发现 → 整张报废。
PROBE_MAX = 8




# 【铁律39】风向必须全局唯一：所有物体的风向角由 scene 顶层广播，
# 逐物体 solve 结果须携带同一 wind_dir，不一致即报错（禁各物体各吹各的）。
# 约定：dir_deg 表示风 **吹向** 的方向，屏幕坐标系
#   0=吹向右  90=吹向下  180=吹向左  270=吹向上
WIND_DIR_DEFAULT = 0.0


# 【铁律32】regime 判据是文献知识，不是普适常数，一律由 AI 搜证后传入。
# 教训：Izawa 2024 的 B* 区间 [1.72e-3, 4.06e-3] 属 INVERTED flag
#       （下游端固定、倒着飘），不可用于常规旗（迎风边固定）。
# 常规旗用 Connell & Yue 2007 的质量比 μ 判据。

# AI 必填槽位（缺一即报错，铁律31）
# family 只接受「五类」（铁律88），物理形态由 _family_map 转换
REQUIRED = {
    "family":   ("biped", "quadruped", "vegetation", "rigid", "cloth"),
    "geometry": ("L", "W"),
    "material": ("sigma",),          # 面密度 kg/m2
    "fluid":    ("U",),              # 风速 m/s
    "criteria": ("regime_by",),      # regime 判据来源，AI 搜证（铁律32）
}



# 骨架绘制参数（被吹平后的形态系数，随 regime 变）
DRAW_PARAM = {
    # 常规旗 regime（Connell & Yue 2007 的 μ 判据命名）
    "stable":   {"mean": 0.55, "vfactor": 0.62},   # 小μ：稳定，垂下轻摆
    "flapping": {"mean": 0.90, "vfactor": 0.38},   # 中μ：周期大幅拍打
    "chaotic":  {"mean": 0.95, "vfactor": 0.28},   # 大μ：混沌猛烈抽打
    # 兼容旧名
    "straight": {"mean": 0.98, "vfactor": 0.22},
    "deflected": {"mean": 0.55, "vfactor": 0.62},
    "n/a":       {"mean": 0.70, "vfactor": 0.50},
}




# ------------------------------------------------------------ chain（受迫阻尼链）
# 统一结构：驱动点(动) -> 附属体(被动响应)
#   树干→枝条  头皮→发丝  肩腰→衣摆  幡身末端→垂带
# 依据 Moore 2002: 枝条振荡频率≈整树自然频率，枝条=受迫阻尼谐振子
CHAIN_REQUIRED = ("L", "m", "EI")




# ------------------------------------------------------------ 校验
# chain 族不吃 geometry/material/fluid——它吃 drive+links（铁律34）
CHAIN_REQUIRED_SPEC = {"drive": ("f_hz",), "links": ()}




def wind_sign(dir_deg):
    """风向在骨架 x 轴上的投影符号（+1 向右 / -1 向左）。"""
    return math.copysign(1.0, math.cos(math.radians(float(dir_deg)))) \
        if abs(math.cos(math.radians(float(dir_deg)))) > 1e-9 else 1.0




# ------------------------------------------------------------ 骨架几何
def _interp(pts, s, col):
    if s <= pts[0][0]:
        return pts[0][col]
    if s >= pts[-1][0]:
        return pts[-1][col]
    for i in range(len(pts) - 1):
        s0, s1 = pts[i][0], pts[i + 1][0]
        if s0 <= s <= s1:
            r = 0 if s1 == s0 else (s - s0) / (s1 - s0)
            return pts[i][col] + r * (pts[i + 1][col] - pts[i][col])
    return pts[-1][col]




# ------------------------------------------------------------ 图集排布
def _grid_for(n):
    """按素材张数选最小够用的网格（行优先），保证一张图集装得下。"""
    for r, c in ((1, 1), (1, 2), (2, 2), (2, 3), (3, 3), (3, 4), (4, 4),
                 (4, 5), (5, 5), (5, 6), (6, 6), (7, 6), (7, 7), (8, 8)):
        if r * c >= n:
            return r, c
    import math as _m
    s = int(_m.ceil(_m.sqrt(n)))
    return s, s
