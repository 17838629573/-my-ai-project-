"""pose 的自检/检查逻辑（由 _extract_tool.py 从 pose.py 抽出）

改前必读: IMPROVE_pose.md
"""
from __future__ import annotations
import math
from pose import NAMES, PoseError, SEGS, _MA, _MB, _chk, bone_lengths, fk, foot_target, hip_height, leg_of, solve, two_bone_ik

def self_check():
    # BEGIN EXAMPLES —— 示例区允许写死（示範用），扫描时剔除
    ANTHRO = {"trunk": 0.288, "head": 0.130, "neck": 0.052, "upperarm": 0.186,
              "lowerarm": 0.146, "hand": 0.108, "thigh": 0.245, "shank": 0.246,
              "shoulder_half": 0.1295, "hip_half": 0.095}
    FACE = {"eye_back": 0.15, "ear_back": 0.35, "face_side": 0.30}
    POSES = {
        "stand": {"a_trunk": 90, "a_head": 90, "a_shoulder_l": 180, "a_shoulder_r": 0,
                  "a_upperarm_l": -90, "a_upperarm_r": -90, "a_forearm_l": -90,
                  "a_forearm_r": -90, "a_hip_l": 180, "a_hip_r": 0,
                  "a_thigh_l": -90, "a_thigh_r": -90, "a_shank_l": -90, "a_shank_r": -90},
        "sit":   {"a_trunk": 90, "a_head": 90, "a_shoulder_l": 180, "a_shoulder_r": 0,
                  "a_upperarm_l": -90, "a_upperarm_r": -90, "a_forearm_l": 0,
                  "a_forearm_r": 0, "a_hip_l": 180, "a_hip_r": 0,
                  "a_thigh_l": 0, "a_thigh_r": 0, "a_shank_l": -90, "a_shank_r": -90},
        "lie":   {"a_trunk": 0, "a_head": 0, "a_shoulder_l": 90, "a_shoulder_r": -90,
                  "a_upperarm_l": 0, "a_upperarm_r": 0, "a_forearm_l": 0,
                  "a_forearm_r": 0, "a_hip_l": 90, "a_hip_r": -90,
                  "a_thigh_l": 0, "a_thigh_r": 0, "a_shank_l": 0, "a_shank_r": 0},
    }
    GAIT = {"speed_m_s": 1.5, "cycle_s": 1.0, "stride_m": 1.5, "stance_ratio": 0.60,
            "swing_height_m": 0.10,          # 髋高不填 -> 由步幅+腿长反算
            "arm_swing_deg": 25.0,           # 摆臂幅度(AI搜证)
            "elbow_bend_deg": 20.0,          # 肘弯曲
            "bob_m": 0.020,                  # 重心起伏半幅(峰峰=2×, 业界3-5cm)
            "torso_lean_deg": 4.0,           # 躯干侧倾
            "pelvis_rot_deg": 3.0,           # 骨盆前后倾
            "knee_land_bend_deg": 18.0}      # 落地屈膝缓冲(业界15-20°)
    SPEC = {"height_m": 1.70, "anthro": ANTHRO, "face": FACE, "poses": POSES, "gait": GAIT}
    # END EXAMPLES

    ok = []
    L = bone_lengths(SPEC)

    # 1 FK 骨长守恒
    p = fk((0.0, 0.9), L, POSES["stand"])
    err = max(abs(math.dist(p[a], p[b]) - L[lk]) for a, b, lk, _ in SEGS)
    ok.append(_chk("1 FK 骨长守恒", err < 1e-9, f"max_err={err:.2e}"))

    # 2 IK 闭环（起点=髋关节真实位置，非骨盆中心）
    p0 = fk((0.0, 0.9), L, POSES["stand"])
    hip = p0["l_hip"]
    tgt = (0.30, 0.30)          # 须在腿长可达范围内
    kp, t1, t2 = two_bone_ik(hip, tgt, L["thigh"], L["shank"])
    p2 = fk((0.0, 0.9), L, {"a_trunk": 90, "a_head": 90, "a_shoulder_l": 180, "a_shoulder_r": 0,
                     "a_upperarm_l": -90, "a_upperarm_r": -90, "a_forearm_l": -90,
                     "a_forearm_r": -90, "a_hip_l": 180, "a_hip_r": 0,
                     "a_thigh_l": t1, "a_shank_l": t2, "a_thigh_r": -90, "a_shank_r": -90})
    e2 = math.dist(p2["l_ankle"], tgt)
    ok.append(_chk("2 IK 闭环误差", e2 < 1e-9, f"{e2:.2e} m"))

    # 3 支撑期脚世界坐标恒定（铁律68 核心）
    duty = GAIT["stance_ratio"]
    a = GAIT["stride_m"] * duty / 2.0
    t0 = -a / GAIT["speed_m_s"]          # 左脚触地时刻（相位对齐后）
    xs = []
    for i in range(20):
        tt = t0 + (duty * GAIT["cycle_s"] - 1e-6) * i / 19
        ph = foot_target(tt, "l", GAIT)
        xs.append(ph[0][0])
    drift = max(xs) - min(xs)
    ok.append(_chk("3 支撑期脚世界坐标恒定", drift < 1e-9, f"drift={drift:.2e} m"))

    # 4 摆动期单调前进 + 抬起
    prev, mono, lifted = -1e9, True, False
    for i in range(11):
        s = duty + (1 - duty) * i / 10
        pt, ph = foot_target(s * GAIT["cycle_s"], "l", GAIT)
        if pt[0] < prev - 1e-12:
            mono = False
        prev = pt[0]
        if pt[1] > 1e-6:
            lifted = True
    ok.append(_chk("4 摆动期前进+抬起", mono and lifted))

    # 5 speed/cadence 一致（铁律69）
    cad = 120.0 / GAIT["cycle_s"]
    ok.append(_chk("5 cadence 在步行区间", 100 <= cad <= 120, f"{cad:.0f} 步/分"))

    # 6 站姿：踝贴地 + 鼻高由骨长累加（不硬编码）
    st = solve(SPEC, "stand")["joints"]
    nose_y = L["thigh"] + L["shank"] + L["trunk"] + L["head"]   # 落地后从地面累加
    ok.append(_chk("6 站姿鼻高=骨长累加", abs(st["nose"][1] - nose_y) < 1e-9,
                   f"{st['nose'][1]:.3f} vs {nose_y:.3f}"))

    # 7 坐姿：大腿水平（膝与髋等高）
    si = solve(SPEC, "sit")["joints"]
    ok.append(_chk("7 坐姿大腿水平", abs(si["l_knee"][1] - si["l_hip"][1]) < 1e-9,
                   f"Δ={si['l_knee'][1]-si['l_hip'][1]:.2e}"))

    # 8 躺姿：躯干水平（鼻与髋的 y 差 = -髋半宽，即躯干沿水平方向）
    li = solve(SPEC, "lie")["joints"]
    dy = li["nose"][1] - li["l_hip"][1]
    ok.append(_chk("8 躺姿躯干水平", abs(dy + L["hip_half"]) < 1e-9, f"Δ={dy:.3f} vs {-L['hip_half']:.3f}"))

    # 9 铁律72 禁硬编码坐标表（含证伪）
    import os
    src = open(os.path.abspath(__file__), encoding="utf-8").read()
    bad = _scan_hardcode(src)
    inj = src.replace("def _chk(", 'HACK = {"nose": (0.0, 0.955)}\ndef _chk(')
    bad2 = _scan_hardcode(inj)
    ok.append(_chk("9 铁律72 禁硬编码坐标表", not bad and bad2,
                   f"自身{len(bad)} 证伪检出{len(bad2)}"))

    # 10 缺物性槽位即报错（铁律70）
    try:
        bone_lengths({"height_m": 1.70, "anthro": {"trunk": 0.288}})
        ok.append(_chk("10 缺槽即报错", False, "未抛异常"))
    except PoseError:
        ok.append(_chk("10 缺槽即报错", True))

    # 11 髋高由步幅反算且 IK 全周期可达（铁律69 联算）
    hy = hip_height(GAIT, L)
    reach = True
    for i in range(30):
        tt = i * GAIT["cycle_s"] / 30.0
        r = solve(SPEC, "walk", tt)
        for s in ("l", "r"):
            tg = r["meta"][f"{s}_target"]
            # 侧视投影：左右髋重合于骨盆中心，判距用 (pelvis_x, hip_y)
            d = math.hypot(tg[0] - GAIT["speed_m_s"] * tt, tg[1] - r["meta"]["hip_y"])
            if d > leg_of(L) + 1e-6:
                reach = False
    ok.append(_chk("11 髋高反算+全周期IK可达", reach,
                   f"hip_y={hy:.3f} <= 腿长{leg_of(L):.3f}"))

    # 12 迈步位移 = speed×t（根治 foot sliding 的位移侧）
    j0 = solve(SPEC, "walk", 0.0)
    j1 = solve(SPEC, "walk", 0.5)
    dx = j1["joints"]["l_hip"][0] - j0["joints"]["l_hip"][0]
    ok.append(_chk("12 位移=速度×时间", abs(dx - 1.5 * 0.5) < 1e-9, f"Δx={dx:.3f} m"))

    print(f"\n{sum(ok)}/{len(ok)} 项 -> {'PASS' if all(ok) else 'FAIL'}")
    return all(ok)

def _scan_hardcode(src):
    """铁律72：逻辑区禁 {关节名:(x,y)} 字面量表（AST 扫描，剔除示例区）。"""
    import ast
    lines = src.splitlines()
    keep, skip = [], False
    for ln in lines:
        if _MA in ln:
            skip = True
            continue
        if _MB in ln:
            skip = False
            continue
        if not skip:
            keep.append(ln)
    try:
        tree = ast.parse("\n".join(keep))
    except SyntaxError:
        return ["语法错误"]
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            hit = False
            for k in node.keys:
                if isinstance(k, ast.Constant) and k.value in NAMES:
                    hit = True
            if not hit:
                continue
            for v in node.values:
                if isinstance(v, (ast.Tuple, ast.List)) and len(v.elts) == 2 and \
                   all(isinstance(e, ast.Constant) and isinstance(e.value, (int, float))
                       for e in v.elts):
                    bad.append(f"L{node.lineno} 硬编码关节坐标")
                    break
    return bad
