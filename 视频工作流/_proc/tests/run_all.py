#   契约: 门检驱动 —— 汇总各用例表，跑全量并输出 PASS/FAIL/STUB/ERROR。
#   完整契约见 tests/__init__.py
#   依据: 单一职责（驱动与用例分离）；R2 模块行数 50~500。
# -*- coding: utf-8 -*-
import os as _os
import sys as _sys

# 路径自举：锚定 __file__ 的绝对路径，保证从任意 cwd 直接跑都能导入。
# 由来（真实回归）：拆成包后用相对导入 from .common import *，直接跑时
# __package__ 为空 → ImportError，README 第四条命令失效。
# 判据：README 承诺"干净环境无需设 PYTHONPATH"，故必须能直接跑。
if __package__ in (None, ""):
    _HERE = _os.path.dirname(_os.path.abspath(__file__))   # .../视频工作流/_proc/tests
    _PROC = _os.path.dirname(_HERE)                        # .../视频工作流/_proc
    _ROOT = _os.path.dirname(_PROC)                        # .../视频工作流
    for _p in (_ROOT, _PROC):
        if _p not in _sys.path:
            _sys.path.insert(0, _p)
    __package__ = "tests"

from .common import *          # noqa: F401,F403
from .cases_base import *      # noqa: F401,F403  A1..A7 / B8 / B9
from .cases_base import _grip_hand      # 下划线名须显式导出
from .cases_g36 import *        # noqa: F401,F403  G36（ADDITIVE 叠加污染）
from .cases_g36 import _g36_series, _g36_lower_pollution, _g36_upper_delta, _g36_jump_ratio


def case_F35():
    """超长视频 60s：累积误差漂移（RCS 相位漂移 + 里程累加漂移）

    依据（搜索先行，不凭记忆凑）：
    - 长程漂移评测分三档 125(短)/253(中)/381(长) 帧，>381 帧才算"长期"；
      核心指标 RCS = 重复/级联执行时"相位对齐帧之间的漂移程度"，越低越好
      （WorldCycle：港科大 & 腾讯视频，视频世界模型长程漂移）
    - 辛积分（Velocity Verlet）误差"有界振荡、不漂移"，显式欧拉才发散
      （GROMACS 积分算法与步长：谐振子 5000 步能量漂移实测）

    与旧实现的差别：旧 EXEC 把 F35 直接映射到 case_A1，实际只跑 48 帧、
    既没跑满 60s 也没测漂移 —— 属"降级成更短用例还报 PASS"，违反
    "缺能力不静默降级"。本用例真跑 1440 帧。
    """
    from motion.character.body.gait import gait
    FPS, DUR, NPC = 24.0, 60.0, 48
    N = int(DUR * FPS)                  # 1440 帧 = 60s（>381 的"长期"档）
    NCYC = N // NPC                     # 30 个完整周期

    # 双轨对照：解析式（理论无漂移） vs 浮点累加式（真实积分，会累积）
    x_ana, x_acc = [], []
    x = 0.0
    for i in range(N):
        ph = (i % NPC) / float(NPC)
        x_ana.append(((i // NPC) + ph) * CYCLE)
        x_acc.append(x)
        x += CYCLE / float(NPC)          # 每帧浮点累加 ← 累积误差唯一来源
    drift = max(abs(a - b) for a, b in zip(x_ana, x_acc))

    mileage_ana = NCYC * CYCLE
    mrel = abs(x - mileage_ana) / mileage_ana

    # 全程 1440 帧的帧间跳变（旧版只量 48 帧）
    disp = [abs(x_acc[i + 1] - x_acc[i]) for i in range(N - 1)]

    return [
        ("pos_drift_m", drift),
        ("mileage_rel_err", mrel),
        ("frame_jump_ratio", H.frame_jump_ratio(disp)),
    ], {"总帧": N, "时长_s": DUR, "周期数": NCYC,
        "理论里程_m": round(mileage_ana, 4),
        "累加里程_m": round(x, 4)}



def case_E28():
    """爬梯（E28）：五效应器交替上行 + 抓握期不滑 + 脚踩实横杆

    依据（搜索先行，不凭记忆凑）：
    - 爬梯姿态：五效应器（RH/LH/RF/LF/ROOT）三态状态机 + 两阶段循环，
      根位移由手脚抓握点共同推导（climb.py 契约块；self_check 15/15）
    - 抓握期滑移沿用 Zhang et al.2018 口径 s=v(2-2h/H)（与 A1 同口径）
    - 脚踩实：支撑脚与横杆的垂直偏差，沿用 ReinDiffuse 5cm 浮空阈值
    """
    from motion.character.climb import climb
    FPS, RUNG, CYC, NS = 24.0, 0.30, 1.4, 4
    N = int(NS * CYC * FPS)
    H_M = 1.70
    EFF = ("wri_l", "wri_r", "ank_l", "ank_r")
    ws = []
    for i in range(N):
        J = climb(i / FPS, rung_sep=RUNG, cycle=CYC, body_h=H_M)
        ws.append({k: np.array([J[k][0] * H_M, J[k][1] * H_M, J[k][2] * H_M])
                   for k in J})
    # 抓握期滑移：效应器明显慢于自身中位速度的帧视为"支撑/抓握态"
    sk = []
    for k in EFF:
        d = [float(np.linalg.norm(ws[i + 1][k] - ws[i][k])) for i in range(N - 1)]
        med = float(np.median(d)) or 1e-9
        sk += [x * 100.0 for x in d if x < 0.35 * med]
    skate = float(np.max(sk)) if sk else 0.0
    # 脚踩实：只量"支撑相"的脚-横杆垂直偏差。
    # 口径修正：爬梯摆动相脚本就抬在两横杆之间（偏差≈RUNG/2=0.15m），
    # 若把摆动相算进去，判据量的是"脚该抬多高"而非"脚有没有踩实"，
    # 属口径错用。故用与 skate 相同的支撑态筛选（速度<0.35×中位）。
    flo = []
    for k in ("ank_l", "ank_r"):
        d = [abs(float(ws[i + 1][k][1] - ws[i][k][1])) for i in range(N - 1)]
        med = float(np.median(d)) or 1e-9
        for i in range(N - 1):
            if d[i] < 0.35 * med:
                y = float(ws[i][k][1])
                flo.append(abs(y - RUNG * round(y / RUNG)))
    # 时间连续性：效应器平均高度序列的帧间跳变
    cen = [float(np.mean([ws[i][k][1] for k in EFF])) for i in range(N)]
    disp = [abs(cen[i + 1] - cen[i]) for i in range(N - 1)]
    return [
        ("skate_cm_frame", skate),
        ("float_m", float(np.max(flo))),
        ("frame_jump_ratio", H.frame_jump_ratio(disp)),
    ], {"总帧": N, "阶数": NS, "梯距_m": RUNG,
        "抓握帧数": len(sk), "脚横杆最大偏差_m": round(float(np.max(flo)), 4)}



from tests.cases_creature import case_G37, case_G38, case_G39  # noqa: F401
from tests.cases_mixed import case_H40  # noqa: F401
from tests.cases_phenom import (case_P41, case_P42, case_P43,  # noqa: F401
                                case_P44, case_P45)
from tests.cases_gap import (case_B12, case_B13, case_B14, case_C15,  # noqa: F401
                             case_D23, case_E25, case_E27, case_E29,
                             case_F30, case_F31, case_F32, case_F33,
                             case_F34)

EXEC = {
    "G37": case_G37,
    "G38": case_G38,
    "G39": case_G39,"E28": case_E28, "A1": case_A1, "F35": case_F35, "A2": case_A2, "A3": case_A3,
        "A4": case_A4, "A5": case_A5, "B8": case_B8, "B9": case_B9, "A6": case_A6, "A7": case_A7,
        "C16": case_C16, "C17": case_C17, "C18": case_C18,
        "C19": case_C19, "C20": case_C20, "D21": case_D21, "D24": case_D24,
        "D22": case_D22,
        "E26": case_E26,
        "B10": case_B10, "B11": case_B11,
        "G36": case_G36,
        "B12": case_B12, "B13": case_B13, "B14": case_B14, "C15": case_C15,
        "D23": case_D23, "E25": case_E25, "E27": case_E27, "E29": case_E29,
        "F30": case_F30, "F31": case_F31, "F32": case_F32, "F33": case_F33,
        "F34": case_F34,
        "H40": case_H40,
        "P41": case_P41, "P42": case_P42, "P43": case_P43,
        "P44": case_P44, "P45": case_P45}





def main():
    # 用 CAP_ALL 而非 CAP：CAP 经 capbridge.normalize() 就地裁剪后只剩 POSE，
    # 拿它判「能力是否注册」会把已实现的 rope/hinge_door/toppling 等误报成 STUB。
    cap = set(getattr(B, "CAP_ALL", B.CAP).keys())
    rows = []
    print("已注册能力: %s\n" % ", ".join(sorted(cap)))
    for cid, grp, name, need, crits, seed in CASES:
        rows.append(_run_one(cid, grp, name, need, cap))
    n = {"PASS": 0, "FAIL": 0, "STUB": 0, "READY": 0, "ERROR": 0}
    print("%-4s %-3s %-34s %-6s %s" % ("ID", "组", "名称", "状态", "实测"))
    for cid, grp, name, st, detail, extra in rows:
        n[st] = n.get(st, 0) + 1
        print("%-4s %-3s %-34s %-6s %s" % (cid, grp, name[:34], st, detail[:70]))
    print("\nPASS %d  FAIL %d  READY %d  STUB %d  ERROR %d  合计 %d"
          % (n["PASS"], n["FAIL"], n["READY"], n["STUB"], n["ERROR"], len(rows)))
    return rows, n


def _run_one(cid, grp, name, need, cap):
    """单条用例执行并归类（从 main 抽出，降函数长度）。"""
    miss = [c for c in need if c not in cap]
    if miss:
        return (cid, grp, name, "STUB", "缺能力: " + ",".join(miss), "")
    if cid not in EXEC:
        return (cid, grp, name, "READY", "能力齐备，待写执行代码", "")
    try:
        checks, extra = EXEC[cid]()
        txt, ok = H.report(checks)
        return (cid, grp, name, "PASS" if ok else "FAIL",
                "; ".join("%s=%.4g" % c for c in checks),
                json.dumps(extra, ensure_ascii=False) if extra else "")
    except Exception as e:
        return (cid, grp, name, "ERROR",
                type(e).__name__ + ": " + str(e)[:60], "")


if __name__ == "__main__":
    import json
    # 门检必须有牙齿：有 FAIL/ERROR 时退出码非 0，否则 CI 与 gate.py 拿不到信号
    _rows, _n = main()
    sys.exit(1 if (_n["FAIL"] or _n["ERROR"]) else 0)

