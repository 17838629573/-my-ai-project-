#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
摄影规则确定性层
==================================================
【原则】能确定的全部代码化，只留极少数给模型。

模型只填 3 个字段：
    shot_type   景别（枚举，不可自造）
    angle       角度（枚举）
    movement    运动（枚举）
其余全部由代码派生、校验、拒绝。

------------------------------------------------------------------
【规则来源（摄影/影视行业通用标准）】
------------------------------------------------------------------
1. 三轴分离：景别 / 角度 / 运动 是同一镜头的三个独立侧面。
   只写"中景" = 把另两项交给模型替你决定 —— 必须分开写。

2. 景别以【切点】定义，不以百分比定义。
   国内教材与英文标准交叉验证：
     大远景 人 = 画面高 1/4
     远景   人 = 画面高 1/2
     全景   人 ≈ 画幅高（不顶天立地）
     中景   膝盖以上（西式 MS 为腰部以上；cowboy 为大腿中部以上）
     中近景 胸部以上（MCU）
     近景   肩部以上（CU）
     特写   人头 ≈ 画面高
     大特写 局部细节（眼、手、物件）

3. 两条硬禁忌（多来源重复强调）：
   ① 不能"顶天立地"：头顶留白 10–20%，脚底留白 10–20%
   ② 不能在关节处切：膝、腰、肘、脖子、脚踝、手腕
      —— 切在关节会产生"截肢"错觉
      行业做法：切在关节【附近】而非关节【处】
      （如中景"腰部以上"实为腰部略上方 0.62，非 0.58）

4. 剪辑相邻原则：
   相邻镜头用相邻景别；相同景别必须换角度，否则会"跳"。

5. 视线留白（looking room / nose room）：
   人物望向画外时，视线方向要留空间，否则构图憋闷。

6. 三分法：主体落在 1/3 线交点，不要居中呆板（对称构图除外）。
"""
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

# ================================================================ 人体比例
# 以身高为 1.0，从脚底起算。标准 7.5 头身。
BODY = {
    "foot":     0.00,
    "ankle":    0.04,
    "knee":     0.27,
    "above_knee": 0.31,     # 安全切点：膝盖上方（避开膝关节）
    "mid_thigh": 0.40,
    "hip":      0.50,
    "waist":    0.58,
    "above_waist": 0.62,    # 安全切点：腰部上方（避开腰关节）
    "chest":    0.70,
    "shoulder": 0.82,
    "neck":     0.87,
    "above_neck": 0.90,     # 安全切点：颈部上方（避开脖关节）
    "top":      1.00,
}

# 关节（禁止在此切）—— 硬禁忌 ②
JOINTS = {"ankle", "knee", "waist", "hip", "neck"}
# 注：shoulder/chest/mid_thigh 是安全切点


# ================================================================ 景别表
@dataclass
class ShotType:
    key: str
    cn: str
    en: str
    cut_at: str                 # 画面下边缘切在哪个部位
    headroom: Tuple[float, float]   # 头顶留白占画面高比例
    footroom: Tuple[float, float]   # 脚底留白（仅全身景别有意义）
    body_frac: Optional[float] = None  # 全身景别：人物高/画面高
    level: int = 0              # 景别梯度，用于剪辑相邻检查

    @property
    def visible(self) -> float:
        """从切点到头顶，占身高的比例"""
        return 1.0 - BODY[self.cut_at]

    @property
    def cuts_at_joint(self) -> bool:
        return self.cut_at in JOINTS


# headroom 经搜索确定(house-style默认,非普适定律):
#   Wide/establishing 15-20%画面高 | Medium(waist-up) 10-12%
#   Close-Up 5-8% | ECU near zero(可故意切头顶)
#   规律: 景别越紧 headroom 越小; 特写配远景式留白=构图事故
# 【修正】初版 EWS 37.5%(近业界2倍) / CU 11%(业界5-8%) / ECU 8.5%(应近0) → 已按上述纠正
# 【修正2】三字段矛盾: headroom+body_frac+footroom≠1(EWS只0.795, 声明17%实际渲染38%)
#     → 全身景别 footroom 改为由 headroom+body_frac 派生并人工收紧, 保证守恒
SHOT_TYPES = {
    "EWS": ShotType("EWS", "大远景", "Extreme Wide Shot",
                    cut_at="foot", headroom=(0.15, 0.22),
                    footroom=(0.565, 0.565), body_frac=0.25, level=0),
    "WS":  ShotType("WS", "远景", "Wide Shot / Long Shot",
                    cut_at="foot", headroom=(0.15, 0.2),
                    footroom=(0.325, 0.325), body_frac=0.5, level=1),
    "FS":  ShotType("FS", "全景", "Full Shot",
                    cut_at="foot", headroom=(0.1, 0.15),
                    footroom=(0.155, 0.155), body_frac=0.72, level=2),
    "MFS": ShotType("MFS", "中远景", "Medium Full / Cowboy",
                    cut_at="mid_thigh", headroom=(0.1, 0.12),
                    footroom=(0.0, 0.0), level=3),
    "MS":  ShotType("MS", "中景", "Medium Shot",
                    cut_at="above_waist", headroom=(0.1, 0.12),
                    footroom=(0.0, 0.0), level=4),
    "MCU": ShotType("MCU", "中近景", "Medium Close-Up",
                    cut_at="chest", headroom=(0.08, 0.12),
                    footroom=(0.0, 0.0), level=5),
    "CU":  ShotType("CU", "近景", "Close-Up",
                    cut_at="shoulder", headroom=(0.05, 0.08),
                    footroom=(0.0, 0.0), level=6),
    "ECU": ShotType("ECU", "大特写", "Extreme Close-Up",
                    cut_at="above_neck", headroom=(0.0, 0.05),
                    footroom=(0.0, 0.0), level=7),
}

# ================================================================ 角度 / 运动
ANGLES = {
    "eye":     "平视（默认，用得比想象中多）",
    "high":    "俯拍（削弱主体）",
    "low":     "仰拍（强化主体）",
    "dutch":   "荷兰角（失衡、不安）",
    "overhead": "鸟瞰（地理清晰/疏离）",
}

MOVEMENTS = {
    "static":  "固定机位（被低估，零成本）",
    "pan":     "摇（原地水平转）",
    "tilt":    "俯仰（原地垂直转）",
    "dolly":   "推/拉（机器在空间里走）",
    "truck":   "横移",
    "pedestal": "升降",
    "handheld": "手持（不稳定、即时感，易疲劳）",
}


# ================================================================ 派生计算
def body_pixels(shot: ShotType, H: int, headroom: Optional[float] = None):
    """
    由景别反算人物像素高度。
    【关键】中景及更紧的景别，人物是【出画】的 —— 脚在画面外。
    这正是我此前"占屏百分比"做不到的地方：
      中景可见段 = 1 - 0.58(腰) = 0.42
      人物高 = (H - 头顶留白) / 0.42 ≈ 2.1 × H  → 远超画面
    """
    hr = headroom if headroom is not None else sum(shot.headroom) / 2
    if shot.body_frac is not None:
        # 全身景别：直接按比例
        return int(round(H * shot.body_frac)), True   # True = 完整入画
    # 半身景别：由可见段反算，人物必然出画
    return int(round(H * (1 - hr) / shot.visible)), False


def ground_y(shot: ShotType, H: int, char_h: int, footroom=None):
    """脚底在画面中的 y（可能 > H，即出画）"""
    fr = footroom if footroom is not None else sum(shot.footroom) / 2
    return int(round(H * (1 - fr)))


def head_top_y(shot: ShotType, H: int, char_h: int, ground: int):
    return ground - char_h


# ================================================================ 校验
def validate_shot(shot_type: str, angle: str, movement: str,
                  H: int, W: int) -> List[str]:
    """单镜头校验。返回问题列表，空 = 通过。"""
    errs = []
    st = SHOT_TYPES.get(shot_type)
    if st is None:
        return [f"未知景别 '{shot_type}'，可选 {list(SHOT_TYPES)}"]
    if angle not in ANGLES:
        return [f"未知角度 '{angle}'，可选 {list(ANGLES)}"]
    if movement not in MOVEMENTS:
        return [f"未知运动 '{movement}'，可选 {list(MOVEMENTS)}"]

    # 硬禁忌 ②：不能在关节切
    if st.cuts_at_joint:
        errs.append(f"{st.cn} 切在关节 '{st.cut_at}' —— 会产生截肢错觉")

    # 硬禁忌 ①：不能顶天立地
    ch, full = body_pixels(st, H)
    gy = ground_y(st, H, ch)
    top = gy - ch
    if full:
        if top < H * 0.05:
            errs.append(f"{st.cn} 头顶留白 {top/H:.1%} 过小（顶天）")
        if gy > H * 0.97:
            errs.append(f"{st.cn} 脚底几乎贴边（立地）")
    return errs


def validate_sequence(seq: List[dict]) -> List[str]:
    """
    序列校验（剪辑相邻原则）：
      · 相邻镜头景别梯度差 ≤ 2，否则跳太狠
      · 梯度差 = 0（同景别）必须换角度，否则会"跳"
    """
    errs = []
    for i in range(1, len(seq)):
        a, b = seq[i - 1], seq[i]
        sa, sb = SHOT_TYPES.get(a["shot_type"]), SHOT_TYPES.get(b["shot_type"])
        if sa is None or sb is None:
            continue
        d = abs(sa.level - sb.level)
        if d == 0:
            if a.get("angle") == b.get("angle"):
                errs.append(
                    f"镜{i}→{i+1}：同景别({sa.cn})且同角度({a.get('angle')})，"
                    f"会跳 —— 必须换角度或换景别")
        elif d > 2:
            errs.append(
                f"镜{i}→{i+1}：景别跳级 {d}（{sa.cn}→{sb.cn}），超过 2，观感突兀")
    return errs


# ================================================================ CLI
if __name__ == "__main__":
    H, W = 960, 540
    print("=" * 76)
    print("摄影规则确定性层 · 景别反算")
    print("=" * 76)
    print(f"{'景别':<8}{'中文':<8}{'切点':<12}{'可见段':>7}{'人物高':>8}"
          f"{'占屏':>8}{'脚底y':>8}{'入画':>6}")
    print("-" * 76)
    for k, st in SHOT_TYPES.items():
        ch, full = body_pixels(st, H)
        gy = ground_y(st, H, ch)
        print(f"{k:<8}{st.cn:<8}{st.cut_at:<12}{st.visible:>7.2f}"
              f"{ch:>8}{ch/H:>8.0%}{gy:>8}{'是' if full else '否':>6}")
    print()
    print("注：中景及更紧的景别，人物【必然出画】—— 脚在画面外。")
    print("    这正是此前用『占屏百分比』做不出来的效果。")
    print()
    print("=" * 76)
    print("校验：单镜头硬禁忌")
    print("=" * 76)
    for k in SHOT_TYPES:
        e = validate_shot(k, "eye", "static", H, W)
        print(f"  {k:<6} {'PASS' if not e else ' | '.join(e)}")
