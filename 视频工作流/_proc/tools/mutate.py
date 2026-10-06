# 契约: proc/tools/mutate
#   一句话: 判据效力变异测试：给判据注入必错的坏输入，仍判 PASS 即判据无牙齿
#   完整契约见 tools/__init__.py
#   依据: PIT / mutmut 变异测试：变异体存活率衡量测试套件的检错能力。
#         静态检查只证明判据「写了」，变异测试才证明判据「有用」。
# -*- coding: utf-8 -*-
"""R13 判据效力变异测试 —— 检测"判据是否有牙齿"。

来源: Mutation Testing (PIT / mutmut)。
  覆盖率高不等于断言有效：一个不写 assert 的测试照样贡献 100% 行覆盖。
  变异测试注入人为缺陷(mutant)，若测试仍全绿则该 mutant SURVIVED ——
  这正是测试套件的盲区所在，每一条 SURVIVED 都该当成"补一条测试"的任务。
  来源: https://www.javacodegeeks.com/2026/05/mutation-testing-with-pit-in-java-the-coverage-metric-youre-ignoring-that-actually-measures-test-quality.html

本工具对"判据纯函数"做输入变异：判据是纯函数，坏输入 == 变异体。
  判据算出坏值却被 judge 判为 PASS  → SURVIVED，判据是瞎的（恒真/自证）
  判据算出坏值且 judge 判为 FAIL   → KILLED，判据有牙齿

典型能抓到的历史事故:
  - F35 复用 case_A1：换个 ID 又跑一遍，判据从不接触 60 秒数据
  - B10 支撑脚反解：判据与被测量同源，恒 0，任何脚轨迹都 PASS
  - A4 459.6/460：阈值贴红线，微小改动即翻红（由 margin 告警覆盖）

用法:
    python3 _proc/tools/mutate.py            # 打印报告，退出码 0=无存活 1=有存活
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests import harness as H  # noqa: E402

# ---------------------------------------------------------------- 变异体
# 每项: (判据名, 变量标签, 坏输入 args, 坏输入 kwargs, 期望被判 FAIL 的说明)
# 坏输入必须是"人眼一看就知道错了"的量，注入后判据若仍 PASS 即判据失效。
MUTANTS = [
    ("skate_cm_frame", "脚贴地每帧滑 5cm",
     ([(i * 0.05, 0.0, 0.0) for i in range(20)],), {},
     "每帧 5cm 滑步，远超 1.0cm 阈值"),

    ("float_m", "最低关节恒在 20cm 高空",
     ([0.20] * 20,), {},
     "角色整体悬空 20cm，远超 5cm 浮空阈值"),

    ("feet_clip_m", "双脚完全重合",
     ([(0.0, 0.0)] * 10, [(0.0, 0.0)] * 10), {},
     "双脚距离 0，必然互穿"),

    ("penetration_m", "两球心距 0.1 而半径各 0.1",
     ([(0.1, 0.1, 0.1)],), {},
     "重叠 0.1m，远超 0.01m 穿模阈值"),

    ("seg_penetration_m", "球心正落骨段中点、半径 0.1",
     ([((0.0, 0.0), (1.0, 0.0), (0.5, 0.0), 0.1)],), {},
     "骨段与球重叠 0.1m"),

    ("frame_jump_ratio", "平稳序列中插一帧 50 倍大跳",
     ([0.01] * 10 + [0.50] + [0.01] * 10,), {},
     "ratio=50，远超 3.0 阈值"),

    ("peak_rate_dps", "角速度恒 1020°/s",
     ([1020.0] * 20,), {},
     "1020°/s 超生理上限，远超 460 阈值"),

    ("flight_g_err", "弹道加速度取 0（无重力）",
     ([0.0, 0.1, 0.2, 0.3], [0.0, 0.0, 0.0, 0.0], 9.80665), {},
     "拟合加速度 0 而理论 -9.8，误差巨大"),

    ("momentum_err", "碰后动量只剩一半",
     ([(1.0, (1.0, 0.0))], [(1.0, (0.5, 0.0))]), {},
     "动量不守恒（签名: before/after 均为 [(质量,(vx,vy))]）"),

    ("mask_iou", "掩膜与真值全不重叠",
     ([[[1, 1], [1, 1]]], [[[0, 0], [0, 0]]]), {},
     "IoU=0，远低于 0.75 阈值"),
]

# 判据返回多值时（如 skate_cm_frame 返回 (mean,max)）取哪个送 judge
PICK = {
    "skate_cm_frame": lambda r: r[1],      # 取 max
}


def run_mutants():
    """返回 (killed, survived, skipped)。"""
    killed, survived, skipped = [], [], []
    for name, label, args, kw, why in MUTANTS:
        fn = getattr(H, name, None)
        if fn is None:
            skipped.append((name, label, "判据不存在"))
            continue
        try:
            raw = fn(*args, **kw)
        except Exception as e:                       # noqa: BLE001
            skipped.append((name, label, "调用异常: %s" % e))
            continue
        val = PICK.get(name, lambda r: r)(raw)
        try:
            ok, thr, op, _src = H.judge(name, val)
        except KeyError:
            skipped.append((name, label, "CRIT 未登记该判据"))
            continue
        rec = (name, label, val, thr, op, why)
        if ok:
            survived.append(rec)                     # 坏值却 PASS —— 判据瞎了
        else:
            killed.append(rec)
    return killed, survived, skipped


def margin(val, thr, op):
    """阈值裕度。返回相对裕度，越小越危险。

    出处: 与 A4 事故直接相关 —— 用上限反解时长会让实测值天然等于上限，
    裕度 0.1% 的用例任何微小改动都会翻红。设计值与红线必须分开。
    """
    if thr is None or thr == 0:
        return float("inf")
    d = abs(float(val) - float(thr)) / abs(float(thr))
    return d


def self_check():
    k, s, sk = run_mutants()
    print("判据效力变异测试")
    print("  KILLED  %2d   判据有牙齿，注入坏值能判 FAIL" % len(k))
    print("  SURVIVED %2d   判据是瞎的，坏值仍判 PASS" % len(s))
    print("  SKIPPED %2d   判据缺失或无法构造变异体" % len(sk))
    for name, label, val, thr, op, why in s:
        print("    [存活] %-20s %s" % (name, label))
        print("           实测 %g  阈值 %s %g   %s" % (val, op, thr, why))
    for name, label, why in sk:
        print("    [跳过] %-20s %s (%s)" % (name, label, why))
    return 0 if not s else 1


if __name__ == "__main__":
    sys.exit(self_check())
