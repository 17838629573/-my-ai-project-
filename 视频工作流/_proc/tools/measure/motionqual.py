# 契约: proc/tools/motionqual
#   一句话: 补齐业界动作质量指标中我们缺失的那几项（稳定性/抖动/自穿透/接触/步态/游动）
#   完整契约见 tools/__init__.py
#   依据: Yuan et al. 物理合理性指标组（Penetrate/Float/Skate）+ HUMOS(arXiv:2409.03944) 采用；
#         Karunratanakul et al. 2023 Jitter = 关节加速度变化均值；
#         PeneBone：每根骨建模为半径 2cm 的盒，量骨级碰撞深度；
#         CHOIS 接触指标：contact precision/recall/F1 + contact distance；
#         Hildebrand 1965 步态三变量（步幅时长 / 占空比 duty factor / 相对相位）；
#         Triantafyllou 1993 + Nudds 2014(JEB 217:2244) Strouhal 0.2~0.4。
# -*- coding: utf-8 -*-
"""R23 业界动作质量指标补齐。

背景（为什么要有这个工具）:
  把我们的判据库与业界通用指标组逐条对照后，确认有 5 项我们此前没有:
    1. 动力学稳定性 ZMP-BoS  —— Yuan et al. 指标组里的 Dyn.Stability / BoSDist
    2. 关节加速度抖动        —— 我们只有像素级 jitter_px，量的是图像不是关节
    3. 骨级自穿透 PeneBone   —— 我们只有"骨 vs 球"，没有"骨 vs 骨"
    4. 接触质量 F1           —— 我们只有穿透/贴合，没有接触的精确率召回率
    5. 步态三变量 / 游动波长 —— 只在注释里写了，没有可测的判据
    6. 振幅比 A* = A/L ∈ [0.1, 0.3]   —— Saadat 2017：光有 St 判不了高效游动
    7. 打滑帧占比 foot_skate_ratio     —— 业界按 ratio 报告，我们只有均值
    8. 稳定余量 bos_margin             —— 我们只测"越界多远"，测不了"离翻倒多近"

  本工具只做"测量"，不拍阈值。阈值一律登记进 tests/harness.CRIT，
  遵循 A1 铁律：先从独立来源定标，再跑测试；禁止先跑后调。

不适用范围（如实声明）:
  FID / Diversity / R-Precision / MM-Dist 属分布级指标，需要真实数据集作参照，
  本工程是程序化生成、无 ground-truth 数据集，这类指标不适用，不做。
  同理 MPJPE/MPVPE 需要真值标注，也不做。
"""

import math

# ---------------------------------------------------------------- 几何基元


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    return math.sqrt(_dot(a, a))


def _clamp01(t):
    return 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)


def seg_seg_dist(p1, q1, p2, q2):
    """两条线段最短距离（3D）。用于 PeneBone 骨级穿透。

    出处: Ericson《Real-Time Collision Detection》§5.1.9 Closest Point
          Between Two Segments；退化（平行/共线）时取端点距离，不除零。
    """
    d1 = _sub(q1, p1)
    d2 = _sub(q2, p2)
    r = _sub(p1, p2)
    a = _dot(d1, d1)
    e = _dot(d2, d2)
    f = _dot(d2, r)
    if a < 1e-12 and e < 1e-12:
        return _norm(r)
    if a < 1e-12:
        s = 0.0
        t = _clamp01(f / e)
    else:
        c = _dot(d1, r)
        if e < 1e-12:
            t = 0.0
            s = _clamp01(-c / a)
        else:
            b = _dot(d1, d2)
            denom = a * e - b * b
            s = _clamp01((b * f - c * e) / denom) if denom > 1e-12 else 0.0
            t = (b * s + f) / e
            if t < 0.0:
                t = 0.0
                s = _clamp01(-c / a)
            elif t > 1.0:
                t = 1.0
                s = _clamp01((b - c) / a)
    c1 = (p1[0] + d1[0] * s, p1[1] + d1[1] * s, p1[2] + d1[2] * s)
    c2 = (p2[0] + d2[0] * t, p2[1] + d2[1] * t, p2[2] + d2[2] * t)
    return _norm(_sub(c1, c2))


# ---------------------------------------------------------------- 1 稳定性


def com_2d(pose, joints, masses):
    """质心（水平 x、竖直 z），质量加权。"""
    mx = mz = mt = 0.0
    for j, m in zip(joints, masses):
        p = pose[j]
        mx += m * p[0]
        mz += m * p[2]
        mt += m
    if mt <= 0.0:
        return (0.0, 0.0)
    return (mx / mt, mz / mt)


def zmp_series(frames, joints, masses, g=9.80665):
    """ZMP 水平位置序列。

    出处: Vukobratović & Borovac 零力矩点；平面简化式
          x_zmp = x_com - (z_com / g) * a_x_com
          （Sardain & Bessonnet 平面 ZMP 定义）。
    """
    coms = [com_2d(f, joints, masses) for f in frames]
    n = len(coms)
    out = []
    for i in range(n):
        x, z = coms[i]
        if i == 0 or i >= n - 1:
            out.append(x)
            continue
        ax = coms[i + 1][0] - 2.0 * coms[i][0] + coms[i - 1][0]
        out.append(x - (z / g) * ax)
    return out


def zmp_stability(frames, joints, masses, feet, contact_thresh=0.02):
    """动力学稳定性: ZMP 落在支撑多边形（2D 退化为支撑区间）外的帧占比。

    返回 (out_pct, bos_dist_m):
      out_pct   —— ZMP 在支撑区间外的帧数占比（业界 Dyn.Stability）
      bos_dist_m—— ZMP 到支撑区间最近边的距离；区间内为 0（业界 BoSDist）
    支撑区间由"贴地足端"（z 低于阈值）的 x 范围给出。
    """
    n = len(frames)
    if n == 0:
        return (0.0, 0.0)
    zmps = zmp_series(frames, joints, masses)
    out_cnt = 0
    dist_sum = 0.0
    for i, f in enumerate(frames):
        xs = [f[j][0] for j in feet if f[j][2] <= contact_thresh]
        if not xs:
            continue
        lo, hi = min(xs), max(xs)
        zx = zmps[i]
        if zx < lo:
            out_cnt += 1
            dist_sum += lo - zx
        elif zx > hi:
            out_cnt += 1
            dist_sum += zx - hi
    return (out_cnt / float(n), dist_sum / float(n))


# ---------------------------------------------------------------- 2 抖动


def jitter_accel(frames, joints):
    """关节加速度抖动。

    出处: Karunratanakul et al. 2023 —— Jitter 为"所有关节加速度变化的均值"。
    此处 a_t = p_{t+1} - 2 p_t + p_{t-1}（二阶差分），jitter = 均值 ||a_{t+1}-a_t||。
    与我们的 jitter_px 区别：jitter_px 量的是帧图灰度差（产物级），
    本函数量的是关节运动学（骨架级），两者不可互相替代。
    """
    n = len(frames)
    if n < 4:
        return 0.0
    acc = []
    for i in range(1, n - 1):
        row = []
        for j in joints:
            p0, p1, p2 = frames[i - 1][j], frames[i][j], frames[i + 1][j]
            row.append((p2[0] - 2 * p1[0] + p0[0],
                        p2[1] - 2 * p1[1] + p0[1],
                        p2[2] - 2 * p1[2] + p0[2]))
        acc.append(row)
    tot = 0.0
    cnt = 0
    for i in range(len(acc) - 1):
        for a, b in zip(acc[i], acc[i + 1]):
            tot += _norm(_sub(b, a))
            cnt += 1
    return tot / cnt if cnt else 0.0


# ---------------------------------------------------------------- 3 自穿透


def pene_bone(frames, bones, radius=0.02, skip_adjacent=True):
    """骨级穿透深度 PeneBone。

    出处: 业界 PeneBone —— 每根骨建模为半径 2cm 的胶囊，量胶囊间穿透深度；
         相邻骨共享关节，天然接触，默认跳过（skip_adjacent）。
    返回: 所有帧所有非相邻骨对的最大穿透深度（米），无穿透为 0。
    """
    worst = 0.0
    for f in frames:
        segs = []
        for a, b in bones:
            if a in f and b in f:
                segs.append(((f[a], f[b]), (a, b)))
        for i in range(len(segs)):
            for k in range(i + 1, len(segs)):
                # 相邻判定看"是否共享关节名"，不能看列表下标位置
                shared = set(segs[i][1]) & set(segs[k][1])
                if skip_adjacent and shared:
                    continue
                d = seg_seg_dist(segs[i][0][0], segs[i][0][1],
                                 segs[k][0][0], segs[k][0][1])
                pen = 2.0 * radius - d
                if pen > worst:
                    worst = pen
    return max(0.0, worst)


# ---------------------------------------------------------------- 4 接触


def contact_f1(pred_contact, gt_contact, hand_obj_dist=None):
    """接触质量: 精确率 / 召回率 / F1 / 接触距离。

    出处: CHOIS(lijiaman) 接触指标 —— 以真值接触帧为基准比对预测接触帧。
      precision = TP/(TP+FP), recall = TP/(TP+FN), F1 = 2PR/(P+R)
      contact_distance = 真值接触帧上手到物体的最小距离
    """
    tp, fp, fn = _confusion(pred_contact, gt_contact)
    prec = tp / float(tp + fp) if (tp + fp) else 0.0
    rec = tp / float(tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"precision": prec, "recall": rec, "f1": f1,
            "contact_distance": _contact_dist(pred_contact, gt_contact,
                                              hand_obj_dist)}


def _confusion(pred_contact, gt_contact):
    """混淆计数 TP/FP/FN（真值接触帧为基准）。"""
    n = min(len(pred_contact), len(gt_contact))
    tp = fp = fn = 0
    for i in range(n):
        p = bool(pred_contact[i])
        g = bool(gt_contact[i])
        if p and g:
            tp += 1
        elif p and not g:
            fp += 1
        elif g and not p:
            fn += 1
    return tp, fp, fn


def _contact_dist(pred_contact, gt_contact, hand_obj_dist):
    """真值接触帧上，手到物体的最小距离。"""
    if not hand_obj_dist:
        return None
    n = min(len(pred_contact), len(gt_contact))
    ds = [hand_obj_dist[i] for i in range(min(n, len(hand_obj_dist)))
          if gt_contact[i]]
    return min(ds) if ds else 0.0


# ---------------------------------------------------------------- 5 步态/游动


def duty_factor(contact_seq):
    """占空比 duty factor: 一个步幅周期内该足触地的时长占比。

    出处: Hildebrand 1965《Symmetrical gaits of horses》三变量之一。
    """
    n = len(contact_seq)
    if n == 0:
        return 0.0
    return sum(1 for c in contact_seq if c) / float(n)


def footfall_phases(contact_seq):
    """提取落脚相位（触地起始时刻 / 周期），用于算相对相位。"""
    n = len(contact_seq)
    # 周期序列：i=0 的前一帧是末帧；否则"开局即触地"会漏掉首个起跳沿
    starts = [i for i in range(n) if contact_seq[i]
              and not contact_seq[i - 1]]
    if not starts:
        return []
    period = n / float(len(starts))
    return [(s % n) / n for s in starts], period


def relative_phase(ref_seq, other_seq):
    """相对相位: other 足相对参考足（如 LH）的触地相位滞后，归一到 [0,1)。

    出处: Hildebrand 1965 三变量之一；对称步态以 LH 为参考，
         walk 各足约 0.25 间隔，trot 对角同相（0.0/0.5）。
    """
    pr = footfall_phases(ref_seq)
    po = footfall_phases(other_seq)
    if not pr or not po:
        return None
    d = (po[0][0] - pr[0][0]) % 1.0
    return d


def wave_ratio(spine, body_len):
    """游动波长 / 体长比。

    出处: 鱼类游动学通常用"每单位体长的波长数"描述行波；
          鲹科体鲹型（carangiform）巡航时体波波长约为 1 个体长量级，
          本函数返回实测波长与体长之比，供判据比对（不在此处拍阈值）。
    算法: 对脊椎各点横向位移做逐点相位，取相邻零 crossings 间距的两倍为波长。
    """
    n = len(spine)
    if n < 4 or body_len <= 0:
        return None
    ys = [p[1] for p in spine]
    cross = []
    for i in range(n - 1):
        if ys[i] <= 0.0 < ys[i + 1] or ys[i] >= 0.0 > ys[i + 1]:
            cross.append(i)
    if len(cross) < 2:
        return None
    gaps = [cross[k + 1] - cross[k] for k in range(len(cross) - 1)]
    mean_gap = sum(gaps) / float(len(gaps))
    seg = body_len / float(n - 1)
    return (2.0 * mean_gap * seg) / body_len


def strouhal(freq_hz, amp_m, speed_mps):
    """Strouhal 数 St = f * A / U。

    出处: Triantafyllou 1993 生物巡航 St 约 0.2~0.4；
         Nudds et al. 2014 (J Exp Biol 217:2244)  trout 实测 0.19~0.22。
    """
    if speed_mps <= 0:
        return None
    return freq_hz * (2.0 * amp_m) / speed_mps


# ------------------------------------------------- 6 振幅比 A* / 打滑帧占比 / 稳定余量
# 这三项是"业界有、我们此前没有"的真缺口（见 tools/anchors.GAPS），本轮补齐。
# 口径一律先查原文定标（A1），不沿用我们自己猜的定义。


def amp_ratio(amp_pp_m, body_len_m):
    """振幅比 A* = A / L。

    出处: Saadat et al. 2017《On the rules for aquatic locomotion》
         PhysRevFluids 2, 083102：St 单独不足以判定高效游动，需附加 A* ∈ [0.1, 0.3]。
         论文原文 "A* (=A/L)"，与 "St(=fA/U)" 共用同一个 A。

    口径（关键，已核实）: 该 A 是**峰峰振幅** A_p-p，不是单边振幅。
         Arellano《Biomechanics and Medicine in Swimming》: "St = A_p-p·f/U, where
         A_p-p is the tail-beat peak-to-peak amplitude"；
         机器人鱼文献同口径: "A is peak-to-peak stroke amplitude of the tail tip"。
         中文报道亦为"来回摆动的距离"在体长 1/10~3/10 之间，即峰峰。
         —— 若误用单边振幅，A* 会小一半，判据口径即错。

    参数: amp_pp_m 尾端峰峰振幅（米）；单边振幅请先乘 2。
    """
    if body_len_m <= 0:
        return None
    return amp_pp_m / body_len_m


def foot_skate_ratio(frames, foot_joints, contact_seq=None,
                     thresh_m=0.01, contact_thresh=0.02, up_axis=2):
    """打滑帧占比：业界按 ratio 报告，而不是只报均值。

    出处: Motion Toolbox evaluation config —— foot_skating_joint 按 ratio 评估，
         good < 0.40，moderate < 0.60（越小越好）。
         与其均值口径（我们的 skate_cm_frame）互补：均值会被少数极端帧拉偏，
         占比能回答"有多少帧在滑"，业界主流按占比报告。

    口径: 分母取**接触帧**（与 CHOIS 的 contact-based 定义一致：只在
         足端贴地期间才谈得上打滑）。位移取**世界坐标**下的足端水平位移——
         必须相对地面，不能相对身体（相对身体会把"整体前进"误判成滑步，
         我们此前在四足步态上踩过这个坑）。
         thresh_m 为单帧打滑判定阈值，取项目现役 skate_cm_frame=1.0cm/frame；
         注意该值经锚点比对被标为动捕真值(0.10cm/frame)的 10 倍，属偏离项，
         故本函数只用它做"单帧是否打滑"的口径，占比阈值 0.40 才是外部来源。

    返回: (ratio, n_contact, n_skate)；无接触帧时 ratio 为 None（不是 0.0——
          0.0 会被误读成"零打滑"，实际是"没得测"）。

    up_axis（关键，显式声明）: 竖直轴下标。本模块内部（zmp_series/_demo_frames）
          约定 (x, y, z) 中 **z 为上**，故默认 up_axis=2。但项目内另有
          (x=前进, h=高度, z=侧向) 的世界坐标约定（tests/common._world），
          那里竖直轴是 index 1。两处口径不一致，必须显式传参，禁止靠猜——
          猜错会把"抬脚高度变化"当成水平滑移（我们此前在混合场景里因坐标口径
          不一致踩过 NaN 污染，属同类病）。
    """
    n = len(frames)
    if n < 2:
        return (None, 0, 0)
    horiz = [a for a in (0, 1, 2) if a != up_axis]
    n_contact = 0
    n_skate = 0
    for i in range(1, n):
        if contact_seq is not None:
            if i >= len(contact_seq) or not contact_seq[i]:
                continue
        elif all(frames[i][j][up_axis] > contact_thresh for j in foot_joints):
            continue
        n_contact += 1
        slide = False
        for j in foot_joints:
            if j not in frames[i] or j not in frames[i - 1]:
                continue
            dx = frames[i][j][horiz[0]] - frames[i - 1][j][horiz[0]]
            dz = frames[i][j][horiz[1]] - frames[i - 1][j][horiz[1]]
            if math.sqrt(dx * dx + dz * dz) > thresh_m:
                slide = True
                break
        if slide:
            n_skate += 1
    if n_contact == 0:
        return (None, 0, 0)
    return (n_skate / float(n_contact), n_contact, n_skate)


def bos_margin(frames, joints, masses, feet, contact_thresh=0.02, g=9.80665):
    """稳定余量：ZMP 到支撑区间最近边的有符号距离（区间内为正，越界为负）。

    出处: 人形/bipedal 导航与步行的通行做法——ZMP 不仅要落在支撑多边形内，
         还要留有稳定余量(stability margin)，业界常用 0.05~0.10 m。
         我们原有的 bos_dist_m 只在**越界**时累加距离，测的是"越界多远"，
         在区间内恒为 0 —— 那不是余量，无法回答"离翻倒还有多近"。

    返回: (min_margin, mean_margin)；无贴地足的帧不参与统计。
    """
    n = len(frames)
    if n == 0:
        return (None, None)
    zmps = zmp_series(frames, joints, masses, g=g)
    margins = []
    for i, f in enumerate(frames):
        xs = [f[j][0] for j in feet if f[j][2] <= contact_thresh]
        if not xs:
            continue
        lo, hi = min(xs), max(xs)
        mid = 0.5 * (lo + hi)
        half = 0.5 * (hi - lo)
        zx = zmps[i]
        # 到最近边的距离：中心距 - 半宽，正=在内且有余量，负=已越界
        margins.append(half - abs(zx - mid))
    if not margins:
        return (None, None)
    return (min(margins), sum(margins) / float(len(margins)))


# ---------------------------------------------------------------- 自检

def self_check():
    """转发到 tools.corpus.motionqual_selfcheck（样本与驱动已分文件）。

    为什么延迟 import: 自检语料反过来依赖本模块，模块级 import 会成环。
    """
    from tools.corpus.motionqual_selfcheck import self_check as _sc
    return _sc()
