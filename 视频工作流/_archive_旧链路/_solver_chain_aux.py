"""chain 求解子函数真身（自拆分前快照恢复）

依赖/被依赖
  依赖: math, framerate, _solver_base(CONSTANTS/AMP_BY_LEVEL_DEFAULT/CHAIN_REQUIRED*)
  被依赖: _solver_chain（wrapper 转调）

改前必读
  IMPROVE_solver.md  —— 真身曾在重复拆分中丢失，勿再对 wrapper 做二次抽取
"""
import math
import framerate
from _solver_base import (
    CONSTANTS, AMP_BY_LEVEL_DEFAULT, CHAIN_REQUIRED, CHAIN_REQUIRED_SPEC, REQUIRED,
)

def flag_lift_deg(U):
    """Rule of 4：旗面平均扬起角（离杆的角度）θ ≈ U(mph)×4，钳制 [0,90]。"""
    return max(0.0, min(90.0, float(U) * CONSTANTS["MPH_PER_MS"] * 4.0))

def amp_over_L(level, criteria=None):
    """峰峰振幅/特征长度 —— 按风级查表，表由 AI 传入（铁律32）。"""
    tbl = ((criteria or {}).get("amp_by_level") or AMP_BY_LEVEL_DEFAULT)
    lv = int(level)
    if lv in tbl:
        return float(tbl[lv])
    return float(tbl.get(max(tbl, key=lambda k: int(k)), 0.0))

def _check_spec(spec):
    """缺槽即报错，绝不静默填默认值（铁律31）"""
    errs = []
    fam = spec.get("family")
    if fam not in REQUIRED["family"]:
        errs.append("family 非法/缺失: %r（应为 %s）"
                    % (fam, list(REQUIRED["family"])))
    elif fam == "chain":
        # 【铁律20】风驱动时 drive 由代码从 fluid.U 算出，不要求 AI 填
        u_wind = float((spec.get("fluid") or {}).get("U", 0.0) or 0.0)
        for k, fs in CHAIN_REQUIRED_SPEC.items():
            if k == "drive" and u_wind > 0.0:
                continue
            if k not in spec:
                errs.append("缺 spec['%s']（chain 族必需）" % k)
            else:
                for f in fs:
                    if f not in spec[k]:
                        errs.append("缺 spec['%s']['%s']" % (k, f))
                if k == "links" and not spec[k]:
                    errs.append("spec['links'] 为空（AI 须给各级物性）")
    else:
        for k, v in REQUIRED.items():
            if k not in spec:
                errs.append("缺 spec['%s']" % k)
                continue
            if isinstance(v, tuple) and k == "family":
                continue
            for f in v:
                if f not in spec[k]:
                    errs.append("缺 spec['%s']['%s']" % (k, f))
    if errs:
        raise ValueError("spec 不完整（AI 需补齐物性）:\n  " + "\n  ".join(errs))
    return True

def chain_response(links, f_drive, amp_drive, zeta_default=0.10):
    """逐级递推：每级驱动 = 上一级末端响应。返回各级 [ω_n, r, M, φ, A]。"""
    if not links:
        raise ValueError("chain: links 为空（AI 须提供各级物性）")
    w_drive = 2.0 * math.pi * f_drive
    out, amp_in = [], float(amp_drive)
    for i, lk in enumerate(links):
        for k in CHAIN_REQUIRED:
            if k not in lk:
                raise ValueError("chain: links[%d] 缺 '%s'（AI 须搜物性）" % (i, k))
        L = float(lk["L"])
        m = float(lk["m"])
        EI = float(lk["EI"])
        zeta = float(lk.get("zeta", zeta_default))
        m_eq = 33.0 / 140.0 * m * L          # 分布质量等效（悬臂梁一阶模态）
        w_n = math.sqrt(3.0 * EI / (m_eq * L ** 3))
        r = w_drive / w_n
        den = math.sqrt((1 - r * r) ** 2 + (2 * zeta * r) ** 2)
        M = r * r / den                       # base excitation 相对位移放大
        phi = math.atan2(2 * zeta * r, 1 - r * r)
        amp = M * amp_in
        out.append({"level": i, "f_n_hz": w_n / (2 * math.pi), "r": r,
                    "M": M, "phase_lag_deg": math.degrees(phi),
                    "amp_m": amp, "resonant": 0.8 < r < 1.25})
        amp_in = amp                          # 下一级的驱动 = 本级末端响应
    return out

def chain_response_multi(links, drives, zeta_default=0.10, weights=None,
                         n_sample=2000):
    """多驱动叠加（例：gait 步频 + wind 风）——**位移域 additive**。

    【铁律42·修订】旧版在**振幅域**做 SRSS（sqrt(ΣA²)），是地震工程
    非相干随机振动定式；而步频与风都是**确定性周期驱动**，相位明确存在，
    振幅域相加等于把两个周期驱动当噪声——丢相位，无物理依据。

    【业界定式】Qt 3D AdditiveClipBlend / Unity Animation Layer Additive：
        result = base + additiveFactor × additive
    且 additive 必须是 **difference clip（相对中性姿态的差值）**。
    本工程 chain_response 输出的 amp_m 是"相对驱动点的位移放大"，
    已是差值语义，故可直接叠加。

    位移域合成（逐帧求值，不是振幅合成）：
        x_i(t) = Σ_j w_j · A_ij · sin(2π·f_j·t − φ_ij)
    峰值：在 base 周期 [0, 1/f_0) 上采样 n_sample 点求 max−min。
    """
    if not drives:
        raise ValueError("chain_response_multi: drives 为空")
    if len(drives) == 1:
        return chain_response(links, drives[0][0], drives[0][1], zeta_default)
    ws = [1.0] * len(drives) if weights is None else list(weights)
    if len(ws) != len(drives):
        raise ValueError("chain_response_multi: weights 长度须等于 drives")
    resps = [chain_response(links, float(d[0]), float(d[1]), zeta_default)
             for d in drives]
    f0 = float(drives[0][0])
    if f0 <= 0:
        raise ValueError("chain_response_multi: base 驱动频率须 > 0")
    T0 = 1.0 / f0
    ts = [T0 * k / n_sample for k in range(n_sample)]
    out = []
    for i in range(len(links)):
        comp = []
        for j, (r, d) in enumerate(zip(resps, drives)):
            comp.append({"drive": d[2], "f_hz": float(d[0]),
                         "amp_m": r[i]["amp_m"],
                         "phase_lag_deg": r[i]["phase_lag_deg"],
                         "weight": float(ws[j])})
        xs = []
        for t in ts:
            s = 0.0
            for c in comp:
                s += c["weight"] * c["amp_m"] * math.sin(
                    2.0 * math.pi * c["f_hz"] * t
                    - math.radians(c["phase_lag_deg"]))
            xs.append(s)
        pp = max(xs) - min(xs)
        row = dict(resps[0][i])
        row["amp_m"] = pp / 2.0          # 单边振幅，与单驱动语义一致
        row["amp_pp_m"] = pp
        row["components"] = comp
        row["amp_by_drive"] = {c["drive"]: c["amp_m"] * c["weight"] for c in comp}
        row["resonant"] = any(r[i]["resonant"] for r in resps)
        out.append(row)
    return out

def frame_durations(N, T, tail_ratio=1.0, intentional_hold=False):
    """逐帧时长（秒）。默认**均匀**，不是末帧加长。

    【铁律43·修订】上一版默认 tail_ratio=1.8（末帧停留）是错的。
    framesprite 权威原文：
      "Should a loop include the first frame again at the end? Usually no.
       The engine returns from the last unique frame to the first automatically."
      "Remove duplicate endpoints" —— 末帧重复首帧会被播放两次，表现为每圈顿一下。
      "Separate a designed hold from a duplicate" —— 有意停顿须用 per-frame time
      显式声明，不能靠复制端点（否则成 invisible technical debt）。

    循环时长 T = 唯一帧数 / 播放fps。闭合不住 = **缺过渡姿态**，
    应补生成姿态，不是改时长掩盖。

    intentional_hold=True 时才启用末帧加长，且反解基础帧长使总长仍精确 = T：
        (N-1)·d + k·d = T  ->  d = T/(N-1+k)
    """
    N = int(N)
    T = float(T)
    if N < 1:
        raise ValueError("frame_durations: N>=1")
    if not intentional_hold:
        return [T / N] * N
    if N < 2:
        return [T]
    k = float(tail_ratio)
    if k < 1.0:
        raise ValueError("intentional_hold 时 tail_ratio 须 >= 1（否则末帧变短）")
    d = T / ((N - 1) + k)
    return [d] * (N - 1) + [k * d]

def loop_seam_ratio(frames_pose_diff, internal_mean):
    """闭合检验：d(last,first) / 内部相邻差均值。

    铁律43：> 1.5 判为**缺过渡姿态**（应补姿态），不是改时长。
    framesprite: "If last->first changes much more than internal pairs,
                  replace or retime a missing transition pose"
    """
    if internal_mean <= 1e-9:
        return float("inf")
    return float(frames_pose_diff) / float(internal_mean)

def transient_envelope(f_n_hz, zeta, t_end, a_peak, a_steady, fps=None,
                       t0=0.0):
    """冲击后回到 a_steady（原扰动量），不是回到 0。"""
    fps = fps or framerate.FPS
    w_n = 2.0 * math.pi * f_n_hz
    w_d = w_n * math.sqrt(1 - zeta * zeta) if zeta < 1 else 0.0
    tau = 1.0 / (zeta * w_n) if zeta > 0 else float("inf")
    n50 = math.log(2) / (2 * math.pi * zeta) if zeta > 0 else float("inf")
    n5 = 1.0 / (2 * zeta) if zeta > 0 else float("inf")
    n = int(round(t_end * fps))
    env = []
    for i in range(n + 1):
        t = i / fps
        dt = max(0.0, t - t0)
        a = a_steady + (a_peak - a_steady) * math.exp(-zeta * w_n * dt)
        env.append({"frame": i, "t": t, "amp_m": a})
    return {"tau_s": tau, "N50_cycles": n50, "N5_cycles": n5,
            "w_d_hz": w_d / (2 * math.pi), "envelope": env}
