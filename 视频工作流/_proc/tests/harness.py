"""物理与动作判据库（测试第一步：判定）

契约: tests/harness
  输入: 关节序列 / 物体轨迹（世界坐标，米·秒），可选帧图序列（像素）
  输出: 各判据实测值 + 是否越界
  依赖: numpy
  被依赖: tests/cases  tests/run_all
  约束: 每个判据必须带 SOURCE 出处，不许拍阈值；
        几何量一律世界坐标米制（像素随距离变，不可作判据）；
        越界即 FAIL，绝不静默降级

判据单位约定
  时间 秒   长度 米   速度 m/s   角度 弧度（对外报告用度）
"""
import math
import os
import sys

import numpy as np

# 自举：__file__ 锚定，把项目根插进 sys.path（禁用相对路径 ../..）
#   项目根 → 支持 from _proc.xxx import
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
for _p in (_ROOT, os.path.dirname(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# name -> (阈值, 比较符, 出处)
# 穿模容差（单点定义，多处引用——禁止复制粘贴传播，见 A2）
# 出处：Box2D v2.4.1 源码 include/box2d/b2_common.h:65
#       `#define b2_linearSlop (0.005f * b2_lengthUnitsPerMeter)`
# 此为官方默认值；若本机实测穿透超过它，应修物理求解器（提高迭代/减小步长），
# 而不是放宽本阈值——阈值定标必须先于测试，不得"跑不过→调阈值→补出处"（见 A1）
_SLOP = 0.005

CRIT = {
    # Zhang et al. 2018：s = v(2 - 2h/H)，H 取 2.5cm；动捕真值约 0.10 cm/frame
        # UE Layered Blend per Bone：additive 层不得污染下半身
    "lower_pollution":  (1e-9, "<", "UE Layered Blend per Bone: additive 只作用于 mask 覆盖骨，下半身零污染"),
    "box_rest_m":       (1e-9, "<", "放箱 detach 后 owner=world，箱体底面贴合台面（carry.box_release 契约）"),
"skate_cm_frame":   (1.0, "<", "Zhang et al.2018 foot skating s=v(2-2h/H), H=2.5cm; 动捕真值0.10cm/frame"),
    # ReinDiffuse：最低关节离地 >5cm 判 float
    "float_m":          (0.05, "<",
        "ReinDiffuse(arXiv:2410.07296, Han et al.) §Evaluation Metrics 原文: "
        "'Ground floating measures the distance between the ground and the lowest joint "
        "positions above the ground (> 5 cm)' —— 5cm 阈值出自该文正文，非自定"),
    # ReinDiffuse：双脚距离 <5cm 判 clip
    "feet_clip_m":      (0.05, ">",
        "ReinDiffuse(arXiv:2410.07296) §Evaluation Metrics 原文: "
        "'Foot clipping measures the distance between the left and right feet when it is "
        "less than a certain distance threshold (5 cm)' —— 5cm 阈值出自该文正文"),
    # 穿模容差：Box2D 官方默认 b2_linearSlop = 0.005 m
    # 出处：Box2D v2.4.1 源码 include/box2d/b2_common.h:65
    #       `#define b2_linearSlop (0.005f * b2_lengthUnitsPerMeter)`
    # 注意：此前误用 0.01（=官方 2 倍）并复制进 4 个判据，已按官方值统一修正。
    "penetration_m":    (_SLOP, "<",
        "穿模深度：Box2D 官方 b2_linearSlop=0.005m (v2.4.1 b2_common.h:65)；实测 C16 max=5.57e-4"),
    # 工程自测值：帧图灰度平均帧间绝对差（0~255）。
    # 注意：原引 SMPTE 属概念错用——SMPTE jitter 是广电时钟级概念(单位 UI/ps，
    # 见 SMPTE RP184 / ST 2059)，不存在"Jitter Score <0.1px"动画像素条款。
    "jitter_px":        (0.1, "<",
        "工程经验值(非SMPTE)：帧图灰度平均帧间绝对差；阈值由本工程自测标定"),
    # 骨段-球穿模：球心到骨段的最短距离 < 半径即穿模，容差同 _SLOP
    "seg_penetration_m": (_SLOP, "<",
        "骨段(胶囊)与球最短距离 < 半径即穿模；容差同 Box2D 官方 slop=0.005m"),
    # 帧间位移不得大于本帧应有位移的若干倍——抓时间跳变
    "frame_jump_ratio": (3.0, "<", "帧间位移/段内中位位移，比值过大即时间跳变"),
    # 长程漂移：WorldCycle（港科大&腾讯视频）RCS = 重复/级联执行时相位对齐帧漂移，
    # 长档 >381 帧；1mm 为动画可感知下限，故取 1e-3 m
    "pos_drift_m":      (1e-6, "<", "动机出处：WorldCycle/CycleBench（港科大·武大·腾讯视频AI技术中心, 2026-08）RCS=重复循环稳定性，长程档381帧。阈值非取自该文，为本工程自测标定：双精度1440帧累加9.7e-13留6量级余量，单精度1.7e-4会FAIL"),
    # 长程里程累积：辛积分（Velocity Verlet）误差有界振荡不漂移，显式欧拉才发散
    "mileage_rel_err":  (1e-9, "<", "GROMACS 辛积分：误差有界振荡不漂移；双精度实测2.9e-14留5量级余量，单精度5e-6会FAIL"),
    # 转角时序判据：jitter_px 是像素级(帧图灰度差)，用在角度序列上属口径错用，
    # 改用有实证上限的峰值角速度。
    "peak_rate_dps":    (460.0, "<",
        "【自测标定值，非取自文献】动机出处 Zago et al., ISBS 2015 Proceedings 33(1):1335-1338，"
        "但该文样本为 10 名 U-13 亚精英球员/29 次试验/5m 运球后脚底半转身，人群与任务均与原地转身错配；"
        "且公开渠道未能核实原文报告过 '414 (90) °/s' 骨盆峰值角速度，故不引用该数值。"
        "460 °/s 系本工程自测标定：实测转身峰值 399.6 °/s（裕度 13%）；"
        "定标顺序为 1020→460 收紧方向，非放宽（见 A1 铁律：阈值先定标再跑测试）"),
    # h_n = h_0 * e^(2n)，e = sqrt(h1/h0)
    "restitution_err":  (0.05, "<", "COR: e=sqrt(h1/h0), h_n=h_0*e^(2n)（UA PH125 实验手册）"),
    # 动量守恒相对误差
    "momentum_err":     (0.02, "<", "动量守恒 m1v1+m2v2 前后不变"),
    # 能量不得凭空增加（反弹越来越高）
    "energy_gain":      (1e-9, "<=", "物理不守恒：总能量不得增加(浮点容差 1e-9)"),
    # 肩→抓握中心：ARM 17.3 + FOREARM 15.5 + WRIST TO CENTRE OF GRIP 3.8 = 36.6% 身高
    # 另一独立来源（Dempster/Table 3.7）：0.1877+0.151+0.038 = 0.3767
    "arm_reach":        (0.377, "<", "Table M: ARM17.3+FOREARM15.5+WRIST-TO-GRIP3.8=36.6%H; Dempster 0.1877+0.151+0.038=0.3767H"),
    # 肘被动活动范围：过伸 5° → 屈曲 145°，超出即反折/超伸
    "elbow_reflex":     (0.0, "<=", "肘ROM 过伸5°~屈145°(Neumann/Kinesiology, Musculoskeletal Key)；实测=反折帧计数"),
    # 接触相浮空：跑步/跳跃触地相足底必须贴地
    "contact_float_m":       (_SLOP, "<",
        "接触相浮空：同 Box2D 官方 b2_linearSlop=0.005m (v2.4.1 b2_common.h:65)"),
    # 穿地：地面半空间穿透，容差同上
    "ground_penetration_m":  (_SLOP, "<",
        "穿地深度：同 Box2D 官方 b2_linearSlop=0.005m (v2.4.1 b2_common.h:65)"),
    # 抛体顶点高度 Δs = g·T_F²/8，相对误差 5%
    "flight_apex_err":       (0.05, "<", "抛体 Δs=g·T_F²/8(UA PH125 实验手册 Projectile Motion)，相对误差5%"),
    # 渲染剪影在 头顶→脚底 内的最长空行段（像素）。
    # 出处：Live 3D Human Reconstruction 用 2D Hausdorff 距离比对剪影，
    # 原文称其 "especially sensitive to holes and missing limbs"
    "flight_g_err":          (0.05, "<", "抛体轨迹二次拟合 a=-g/2(UA PH125 Projectile Motion 手册, 匀加速运动 y=y0+v0t-gt²/2)"),
    "silhouette_gap_px":     (2.0, "<", "2D Hausdorff between silhouette masks: sensitive to holes and missing limbs(Integrated Platform for Live 3D Human Reconstruction)"),
    # 渲染剪影纵向跨度 / 关节投影的头顶点—脚底点像素距离
    "silhouette_span_ratio": (0.90, ">", "同上：剪影须覆盖头到脚，比值过小即缺肢体"),
    # 渲染剪影 vs 胶囊几何真值掩膜的 IoU
    "mask_iou":              (0.75, ">",
        "IoU/Jaccard index（Jaccard P. 1912, New Phytologist 11:37-50, §相似度系数）；"
        "阈值 0.75 为本工程自测标定（实测 D22 剪影 IoU=0.9357 留 25% 余量）。"
        "撤除说明：原引 ResiHMR(arXiv:2604.28025) 主题为残肢人群单图 3D 人体网格恢复，"
        "与本判据无方法论关联，属语义贴牌，已撤除"),
}


def _thr(name):
    return CRIT[name]


def judge(name, val):
    """返回 (是否通过, 阈值, 比较符, 出处)"""
    if name not in CRIT:
        raise KeyError("未知判据 %r，先在 CRIT 登记并写出处" % name)
    t, op, src = CRIT[name]
    if op == "<":
        ok = val < t
    elif op == "<=":
        ok = val <= t
    elif op == ">":
        ok = val > t
    elif op == ">=":
        ok = val >= t
    else:
        raise ValueError(op)
    return ok, t, op, src


# ---------------------------------------------------------------- 滑步 / 浮空
def skate_cm_frame(foot_xy_h, fps=24.0, H=0.025):
    """脚滑步。foot_xy_h: [(x, y, h)] 每帧，x/y 水平米，h 离地高（米）。

    s = v * (2 - 2h/H)，仅当 h < H 才计（脚被认为接触地面）
    返回 cm/frame 的平均与最大。
    """
    a = np.asarray(foot_xy_h, float)
    if len(a) < 2:
        return 0.0, 0.0
    d = np.linalg.norm(np.diff(a[:, :2], axis=0), axis=1)      # m/frame
    h = a[:-1, 2]
    mask = h < H
    s = np.zeros_like(d)
    s[mask] = (d[mask] * 100.0) * (2.0 - 2.0 * h[mask] / H)    # cm/frame
    return float(s.mean()), float(s.max())


def float_m(lowest_joint_h):
    """最低关节离地高度序列 → 最大值（>5cm 判浮空）"""
    a = np.asarray(lowest_joint_h, float)
    return float(a.max()) if a.size else 0.0


def feet_clip_m(foot_a_xy, foot_b_xy):
    """双脚水平距离最小值（<5cm 判互穿）"""
    a = np.asarray(foot_a_xy, float)
    b = np.asarray(foot_b_xy, float)
    if len(a) < 1:
        return 9.9
    d = np.linalg.norm(a - b, axis=1)
    return float(d.min())


# ---------------------------------------------------------------- 穿模
def penetration_m(pairs):
    """穿模深度（2D 简化：胶囊/圆重叠深度，取所有对的最大值）。

    pairs: [(dist, rA, rB)]  dist=中心距，rA/rB=半径
    重叠深度 = rA + rB - dist，正值即穿透
    """
    m = 0.0
    for dist, rA, rB in pairs:
        d = (rA + rB) - dist
        if d > m:
            m = d
    return float(max(m, 0.0))


def seg_penetration_m(seg_pairs):
    """线段(骨)-圆(物体) 最短距离 → 穿模深度。
    seg_pairs: [((ax,ay),(bx,by),(cx,cy),r)] 返回最大穿透
    """
    worst = 0.0
    for (ax, ay), (bx, by), (cx, cy), r in seg_pairs:
        ax, ay, bx, by, cx, cy, r = map(float, (ax, ay, bx, by, cx, cy, r))
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = 0.0 if L2 <= 1e-12 else max(0.0, min(1.0, ((cx - ax) * dx + (cy - ay) * dy) / L2))
        px, py = ax + t * dx, ay + t * dy
        dist = math.hypot(cx - px, cy - py)
        worst = max(worst, r - dist)
    return float(max(worst, 0.0))


# ---------------------------------------------------------------- 时间连续性
def frame_jump_ratio(disp_seq):
    """disp_seq: 每帧位移（像素或米）。返回 max/中位；中位为 0 时给 inf。"""
    a = np.asarray(disp_seq, float)
    if len(a) < 3:
        return 0.0
    med = float(np.median(a[a > 0])) if np.any(a > 0) else 0.0
    if med <= 1e-12:
        return float("inf")
    return float(a.max() / med)


def peak_rate_dps(rate_seq):
    """角速度序列(°/s) → 峰值。转身/摆臂等旋转动作的时序平滑度判据。

    与 jitter_px 的区别：jitter_px 量的是帧图灰度差（像素），
    对角度序列无意义；旋转动作应量角速度峰值是否超生理上限。
    """
    if not rate_seq:
        return 0.0
    return float(max(abs(float(x)) for x in rate_seq))


def jitter_px(frames):
    """帧图序列（灰度数组）→ 平均帧间绝对差（0~255）"""
    if len(frames) < 2:
        return 0.0
    g = [np.asarray(f, float) for f in frames]
    return float(np.mean([np.abs(g[i + 1] - g[i]).mean() for i in range(len(g) - 1)]))


# ---------------------------------------------------------------- 物理守恒
def restitution(h0, h1):
    """e = sqrt(h1/h0)"""
    if h0 <= 1e-9:
        return 0.0
    return math.sqrt(max(h1, 0.0) / h0)


def restitution_err(peaks, e):
    """peaks: 各次反弹最高点 [h0, h1, h2...]，检查 h_n = h0 * e^(2n)

    返回最大相对误差。"""
    if len(peaks) < 2:
        return 0.0
    err = 0.0
    for n, h in enumerate(peaks):
        pred = peaks[0] * (e ** (2 * n))
        if pred > 1e-9:
            err = max(err, abs(h - pred) / pred)
    return float(err)


def momentum_err(before, after):
    """before/after: [(m, (vx,vy))] → 总动量相对误差"""
    p1 = np.zeros(2)
    for m, v in before:
        p1 += m * np.asarray(v, float)
    p2 = np.zeros(2)
    for m, v in after:
        p2 += m * np.asarray(v, float)
    n = max(np.linalg.norm(p1), 1e-9)
    return float(np.linalg.norm(p2 - p1) / n)


def energy_gain(states):
    """states: [(m, v, h)] 每帧 → 若末态能量大于初态则正（能量凭空增加）"""
    if len(states) < 2:
        return 0.0
    g = 9.80665

    def E(s):
        return sum(m * (0.5 * float(np.dot(v, v)) + g * h) for m, v, h in s)

    return float((E([states[-1]]) - E([states[0]])) / max(abs(E([states[0]])), 1e-9))


# ---------------------------------------------------------------- 关节
def knee_reflex(hip, knee, ankle, facing=1.0):
    """膝盖是否反折。facing=+1 表示人物朝 +u。

    正常：膝在髋-踝连线的「前方」（朝 facing 一侧）凸出
    返回 (是否反折, 凸出量米)
    """
    hx, hy = hip
    kx, ky = knee
    axx, ayy = ankle
    # 髋->踝 连线，膝相对该线的有符号横向偏移
    dx, dy = axx - hx, ayy - hy
    L = math.hypot(dx, dy)
    if L < 1e-9:
        return False, 0.0
    cross = (dx * (ky - hy) - dy * (kx - hx)) / L
    off = cross * facing
    return bool(off < -1e-6), float(off)


def elbow_reflex(shoulder, elbow, wrist, facing=1.0):
    return knee_reflex(shoulder, elbow, wrist, facing)


# 臂展的几何实现属于人体比例层（motion/character/proportions.py），不在测试层。
#   此前 pass_ball.py 直接 `from tests.harness import arm_reach`，造成
#   motion → tests 的反向依赖（R1 违规），已下沉；此处转发以保持 H.arm_reach 调用点不变。
from _proc.motion.character.body.proportions import arm_reach, ARM_REACH_MAX  # noqa: E402,F401


def _run_len_false(seg):
    best = cur = 0
    for v in seg:
        cur = 0 if v else cur + 1
        if cur > best:
            best = cur
    return best


def silhouette_gap_px(mask):
    """剪影在 头顶→脚底 区间内的最长空行段（像素）。

    mask: (H,W) bool，人物掩膜。断带 = 缺肢体（只画头/只画手）。
    """
    m = np.asarray(mask, dtype=bool)
    rows = m.any(axis=1)
    ys = np.nonzero(rows)[0]
    if ys.size == 0:
        return float("inf")
    return float(_run_len_false(rows[int(ys[0]):int(ys[-1]) + 1]))


def silhouette_span_ratio(mask, top_y, bot_y):
    """剪影纵向跨度 / 关节投影的头顶点—脚底点距离。"""
    m = np.asarray(mask, dtype=bool)
    ys = np.nonzero(m.any(axis=1))[0]
    if ys.size == 0:
        return 0.0
    denom = max(float(bot_y) - float(top_y), 1.0)
    return float(ys[-1] - ys[0] + 1) / denom


def mask_iou(a, b):
    """渲染掩膜 vs 胶囊几何真值掩膜的 IoU。"""
    a = np.asarray(a, dtype=bool)
    b = np.asarray(b, dtype=bool)
    inter = float(np.count_nonzero(a & b))
    union = float(np.count_nonzero(a | b))
    return inter / union if union else 0.0


def report(checks):
    """checks: [(判据名, 实测值)] → 打印表"""
    lines = ["%-18s %12s  %4s %-10s %s" % ("判据", "实测", "", "阈值", "结论")]
    allok = True
    for name, val in checks:
        ok, t, op, _ = judge(name, val)
        allok = allok and ok
        lines.append("%-18s %12.5g  %4s %-10.5g %s" % (name, val, op, t, "PASS" if ok else "FAIL"))
    lines.append("总判定: %s" % ("PASS" if allok else "FAIL"))
    return "\n".join(lines), allok


def self_check():
    """判据库自检：构造已知答案，确认公式没写反。"""
    out = []
    # 1 滑步：脚离地 0（贴地）水平每帧走 0.01m → s = 1cm/frame * 2 = 2cm/frame
    seq = [(0.01 * i, 0.0, 0.0) for i in range(10)]
    m, mx = skate_cm_frame(seq)
    out.append(("skate_贴地应为2cm/frame", abs(m - 2.0) < 1e-6, m))
    # 2 脚抬高到 H 以上 → 不计滑步
    seq2 = [(0.01 * i, 0.0, 0.025) for i in range(10)]
    m2, _ = skate_cm_frame(seq2)
    out.append(("skate_离地>=H应归零", abs(m2) < 1e-9, m2))
    # 3 弹性：h0=1, e=0.8 → h1=0.64
    e = restitution(1.0, 0.64)
    out.append(("restitution_e应为0.8", abs(e - 0.8) < 1e-9, e))
    err = restitution_err([1.0, 0.64, 0.4096], 0.8)
    out.append(("反弹序列符合e^(2n)", err < 1e-9, err))
    # 4 动量：等质量 1kg，2m/s 撞静止 1kg → 速度交换，总动量守恒
    err2 = momentum_err([(1.0, (2.0, 0)), (1.0, (0.0, 0))], [(1.0, (0.0, 0)), (1.0, (2.0, 0))])
    out.append(("动量守恒", err2 < 1e-12, err2))
    # 5 穿模：两圆半径各 0.5，中心距 0.8 → 穿透 0.2
    p = penetration_m([(0.8, 0.5, 0.5)])
    out.append(("穿模深度应为0.2", abs(p - 0.2) < 1e-12, p))
    # 6 不接触 → 0
    p2 = penetration_m([(1.5, 0.5, 0.5)])
    out.append(("不接触应为0", abs(p2) < 1e-12, p2))
    # 7 膝盖反折：朝 +x，膝向后(-x)凸 → 反折
    bad, off = knee_reflex((0, 1), (-0.1, 0.5), (0, 0), facing=1.0)
    out.append(("膝向后应判反折", bad is True, off))
    good, off2 = knee_reflex((0, 1), (0.1, 0.5), (0, 0), facing=1.0)
    out.append(("膝向前应判正常", good is False, off2))
    # 8 帧跳变：正常序列比值应接近 1
    r = frame_jump_ratio([1.0] * 10 + [1.2])
    out.append(("无跳变比值<3", r < 3.0, r))
    r2 = frame_jump_ratio([1.0] * 10 + [50.0])
    out.append(("有一帧跳变应>3", r2 > 3.0, r2))
    # 9 能量：自由下落能量守恒（不计碰撞）不应增加
    # 下降 0.05m，自由落体速度 v=sqrt(2*g*dh)，能量应严格守恒
    dh = 0.05
    v = math.sqrt(2 * 9.80665 * dh)
    st = [(1.0, (0.0, 0.0), 1.0), (1.0, (0.0, -v), 1.0 - dh)]
    g = energy_gain(st)
    out.append(("自由落体能量守恒", abs(g) < 1e-9, g))
    # 反向：给一个比自由落体更大的速度 → 应检出能量增加
    st2 = [(1.0, (0.0, 0.0), 1.0), (1.0, (0.0, -3.0), 0.95)]
    g2 = energy_gain(st2)
    out.append(("能量凭空增加应检出", g2 > 0, g2))
    for name, ok, v in out:
        print("%-24s %-6s %g" % (name, "PASS" if ok else "FAIL", v))
    return all(ok for _, ok, _ in out)


# ---------------------------------------------------------------- 接触/穿地/抛体
def contact_float_m(lows, contact_mask):
    """接触相浮空：只在标记为触地的帧上量最低关节离地高度，取最大值。

    lows:     每帧最低关节离地高度(m)
    contact_mask: 每帧是否处于触地相
    """
    vals = [float(h) for h, c in zip(lows, contact_mask) if c]
    return float(max(vals)) if vals else 0.0


def ground_penetration_m(heights):
    """地面半空间穿透深度(m)：h<0 即穿地，取最大。"""
    return float(max(0.0, -min([float(h) for h in heights]))) if len(heights) else 0.0


def flight_g_err(t_rel, h_m, g=9.80665):
    """抛体段二次拟合: h=a t²+b t+c, 弹道应满足 a=-g/2。返回 |(-2a)-g|/g"""
    import numpy as _np
    t = _np.asarray(t_rel, dtype=float)
    y = _np.asarray(h_m, dtype=float)
    if len(t) < 3:
        return 0.0
    A = _np.vstack([t * t, t, _np.ones_like(t)]).T
    a = _np.linalg.lstsq(A, y, rcond=None)[0][0]
    return float(abs(-2.0 * a - g) / g)


def flight_apex_err(apex_rise_m, flight_time_s, g=9.80665):
    """抛体顶点相对误差：实测升高 vs Δs=g·T_F²/8。"""
    tf = float(flight_time_s)
    pred = g * tf * tf / 8.0
    if pred <= 1e-12:
        return 0.0
    return float(abs(float(apex_rise_m) - pred) / pred)


if __name__ == "__main__":
    print("harness 自检:", "PASS" if self_check() else "FAIL")
