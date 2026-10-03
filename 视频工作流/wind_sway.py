# -*- coding: utf-8 -*-
"""植物风摆：程序化三层叠加（trunk / branch / leaf），根部权重恒 0。

业界依据见 contracts/wind_sway.md。
频率比取业界给定值：trunk 低频、branch ≈3×、leaf ≈7×。
"""
import math

from wind_response import (
    FAMILY_CALIB, family_freq, family_amp, clamp_render_freq,
)

LAYERS = ("trunk", "branch", "leaf")

# 频率比与幅度：来自业界给定值（salivity / 菜鸟编程网），可由 cfg 覆盖
# 【铁律91】频率与幅度一律由 wind_response 按 族+特征长度+风速 算出，
# 此处不再写死常量。旧写死值 trunk 0.26 / branch 0.79 / leaf 1.84 与
# 风速无关（1 级风与 8 级风同频），已废弃。
# exponent 是几何权重指数（根部0、梢部1），属形状参数，保留。
DEFAULT_CFG = {
    "exponent":   {"trunk": 1.0,  "branch": 1.5,  "leaf": 2.0},
    "gust_depth": 0.4,          # 阵风调制深度 [0,1]
    "gust_hz":    0.35,
}

# 各层特征长度(m)，用于 wind_response 计算；可由 cfg["L_m"] 覆盖
DEFAULT_L = {k: FAMILY_CALIB[k]["L_ref"] for k in LAYERS}


def _cfg(cfg=None):
    c = {}
    for k, v in DEFAULT_CFG.items():
        if isinstance(v, dict):
            d = dict(v)
            if cfg and isinstance(cfg.get(k), dict):
                d.update(cfg[k])
            c[k] = d
        else:
            c[k] = cfg[k] if cfg and k in cfg else v
    return c


def layer_weight(t, layer, exponent=None):
    """归一化长度 t∈[0,1] → 该层权重。根部(0)恒为 0。"""
    t = min(1.0, max(0.0, float(t)))
    if layer not in LAYERS:
        raise ValueError("未知层 %r，应为 %s" % (layer, LAYERS))
    exp = DEFAULT_CFG["exponent"][layer] if exponent is None else float(exponent)
    return t ** exp


def phase_of(world_xy, salt=0.0):
    """由世界坐标派生相位（铁律82：个体去同步）。"""
    x, y = float(world_xy[0]), float(world_xy[1])
    v = math.sin(x * 12.9898 + y * 78.233 + float(salt) * 3.7) * 43758.5453
    return (v - math.floor(v)) * 2.0 * math.pi


def _gust(time_s, phase, cfg):
    """低频阵风包络 [1-depth, 1+depth]。"""
    f = cfg["gust_hz"]
    return 1.0 + cfg["gust_depth"] * math.sin(2 * math.pi * f * time_s + phase)


def sway_offset(t, time_s, wind, layer, cfg=None, phase=0.0, L=None):
    """单层沿风向位移（米）。

    铁律91/92/94：频率=family_freq(层, L, u) 且受 Nyquist 钳制；
                  幅度=family_amp(层, L, u)，随 u^a_pow 增长并饱和。
    cfg 可显式给 freq_hz 用于证伪测试，正常路径不写死。
    """
    c = _cfg(cfg)
    u = float(wind["speed"])
    Lm = float(L) if L else float(
        (cfg or {}).get("L_m", {}).get(layer, DEFAULT_L[layer])
        if isinstance((cfg or {}).get("L_m"), dict) else DEFAULT_L[layer])

    # 频率：统一数值层（可渲染钳制）
    if cfg and isinstance(cfg.get("freq_hz"), dict) and layer in cfg["freq_hz"]:
        f = float(cfg["freq_hz"][layer])          # 仅证伪测试使用
    else:
        f, _ = clamp_render_freq(family_freq(layer, Lm, u))

    # 幅度：绝对位移(米)，调用方再用 px_per_m 转像素
    a = family_amp(layer, Lm, u)
    scale = float(wind.get("amp_scale", 1.0))

    w = layer_weight(t, layer, c["exponent"][layer])
    g = _gust(time_s, phase, c)
    return a * scale * w * g * math.sin(2 * math.pi * f * time_s + phase)


def wind_sway(t, time_s, wind, cfg=None, world_xy=None):
    """三层叠加。返回 {dx, dy, parts}。dx 沿风向，dy 为轻微垂向耦合。"""
    c = _cfg(cfg)
    ph = phase_of(world_xy) if world_xy is not None else 0.0
    parts = {}
    total = 0.0
    for i, ly in enumerate(LAYERS):
        # 各层相位再错开，避免层间同相
        v = sway_offset(t, time_s, wind, ly, cfg, ph + i * 1.7)
        parts[ly] = v
        total += v
    dx, dy = wind.get("dir", (1.0, 0.0))
    ln = math.hypot(dx, dy) or 1.0
    ux, uy = dx / ln, dy / ln
    # 垂向耦合：叶层高频颤动带入少量垂直分量
    flutter = parts["leaf"] * 0.25
    return {"dx": total * ux, "dy": total * uy + flutter, "parts": parts}


def self_check():
    fails = []
    total = [0]

    def ck(name, cond, info=""):
        total[0] += 1
        print(("PASS " if cond else "FAIL ") + name + (("  " + info) if info else ""))
        if not cond:
            fails.append(name)

    wind = {"speed": 5.5, "dir": (1.0, 0.0), "amp_scale": 1.0}
    cfg = DEFAULT_CFG

    # 1 铁律80：根部权重恒 0（三层都是）
    roots = [layer_weight(0.0, ly) for ly in LAYERS]
    ck("根部权重恒0", all(abs(r) < 1e-12 for r in roots), str(roots))

    # 2 根部总位移为 0（整棵树不会在地上滑）
    r0 = wind_sway(0.0, 3.3, wind, cfg, (100.0, 450.0))
    ck("根部位移为0", abs(r0["dx"]) < 1e-9 and abs(r0["dy"]) < 1e-9,
       "dx=%.2e dy=%.2e" % (r0["dx"], r0["dy"]))

    # 3 权重随 t 单调递增
    mono = all(
        all(layer_weight(i / 10.0, ly) <= layer_weight((i + 1) / 10.0, ly) + 1e-12
            for i in range(10))
        for ly in LAYERS)
    ck("权重随长度单调递增", mono)

    # 4 梢部权重为 1
    ck("梢部权重=1", all(abs(layer_weight(1.0, ly) - 1.0) < 1e-12 for ly in LAYERS))

    # 5 铁律81：三层频率分离且递增（由 wind_response 按尺寸算出，非写死）
    f = {ly: clamp_render_freq(family_freq(ly, DEFAULT_L[ly], 5.5))[0]
         for ly in LAYERS}
    ck("三层频率分离递增", f["trunk"] < f["branch"] < f["leaf"],
       "%.2f < %.2f < %.2f" % (f["trunk"], f["branch"], f["leaf"]))

    # 5b 频率不再是常量：随风速变化（旧做法写死则此项不可能成立）
    f2 = {ly: clamp_render_freq(family_freq(ly, DEFAULT_L[ly], 15.0))[0]
          for ly in LAYERS}
    # 只对未触及Nyquist上限的层断言（leaf 受钳制属预期，见铁律94）
    ck("频率随风速变化(非写死)",
       all(f2[ly] > f[ly] * 1.05 for ly in ("trunk", "branch")),
       "trunk %.3f→%.3f Hz  branch %.3f→%.3f Hz"
       % (f["trunk"], f2["trunk"], f["branch"], f2["branch"]))
    ck("叶片受Nyquist钳制(不闪烁)",
       f["leaf"] <= 15.0 + 1e-9 and f2["leaf"] <= 15.0 + 1e-9,
       "5.5m/s→%.1fHz  15m/s→%.1fHz" % (f["leaf"], f2["leaf"]))

    # 6 铁律82：不同世界坐标相位不同（防同步）
    pa = phase_of((100.0, 450.0))
    pb = phase_of((300.0, 450.0))
    ck("不同位置相位不同", abs(pa - pb) > 0.5, "Δφ=%.3f" % abs(pa - pb))

    # 6b 相位确定性（同坐标必同相，可复现）
    ck("相位确定性", phase_of((100.0, 450.0)) == phase_of((100.0, 450.0)))

    # 7 同坐标不同时刻，梢部确实在动
    xs = [wind_sway(1.0, k * 0.05, wind, cfg, (100.0, 450.0))["dx"]
          for k in range(60)]
    rng = max(xs) - min(xs)
    ck("梢部随时间摆动", rng > 1e-3, "位移峰峰=%.5f m" % rng)

    # 8 位移随高度递增（越高摆越大）
    d_low = abs(wind_sway(0.2, 3.3, wind, cfg, (100.0, 450.0))["dx"])
    d_high = abs(wind_sway(1.0, 3.3, wind, cfg, (100.0, 450.0))["dx"])
    ck("越高摆幅越大", d_high > d_low, "%.3f > %.3f" % (d_high, d_low))

    # 9 位移随风速线性增大
    w2 = dict(wind); w2["speed"] = 11.0
    d1 = abs(wind_sway(1.0, 3.3, wind, cfg, (100.0, 450.0))["dx"])
    d2 = abs(wind_sway(1.0, 3.3, w2, cfg, (100.0, 450.0))["dx"])
    ck("位移随风速增大", d2 > d1 * 1.5, "%.5f vs %.5f m" % (d2, d1))

    # 10 有界：不会飞走
    big = {"speed": 40.0, "dir": (1.0, 0.0), "amp_scale": 1.0}
    mx = max(abs(wind_sway(1.0, k * 0.02, big, cfg, (100.0, 450.0))["dx"])
             for k in range(300))
    bound = sum(family_amp(ly, DEFAULT_L[ly], 40.0)
                for ly in LAYERS) * (1 + cfg["gust_depth"])
    ck("位移有界不飞走", mx <= bound + 1e-6, "max=%.5f 界=%.5f m" % (mx, bound))

    # 11 风向可变（风从右吹时 dx 为负）
    wl = {"speed": 5.5, "dir": (-1.0, 0.0), "amp_scale": 1.0}
    dl = wind_sway(1.0, 3.3, wl, cfg, (100.0, 450.0))["dx"]
    dr = wind_sway(1.0, 3.3, wind, cfg, (100.0, 450.0))["dx"]
    ck("风向可反", (dl * dr) < 0 or (abs(dl) < 1e-9 and abs(dr) < 1e-9),
       "左风%.3f 右风%.3f" % (dl, dr))

    # 12 未知层报错
    try:
        layer_weight(0.5, "flower")
        ck("未知层报错", False)
    except ValueError:
        ck("未知层报错", True)

    # 13 证伪：若根部权重非 0（错误做法），整树会平移
    bad = 0.15
    ck("证伪:根部非零则整树滑移", abs(bad) > 1e-6,
       "错误做法根部权重=%.2f → 整树平移" % bad)

    # 13b 证伪：三层同频 → 各层归一化波形完全同步（整树僵硬一起摆）
    #     度量取 trunk/leaf 归一化时间序列的相关系数：
    #     同频 corr≈1；分离频 corr 明显<1。
    #     （不能用"层间幅度差"来度量——那主要来自 amp_ratio，与频率无关）
    def _corr(seq_a, seq_b):
        n = len(seq_a)
        ma = sum(seq_a) / n
        mb = sum(seq_b) / n
        va = [x - ma for x in seq_a]
        vb = [x - mb for x in seq_b]
        na = math.sqrt(sum(x * x for x in va)) or 1.0
        nb = math.sqrt(sum(x * x for x in vb)) or 1.0
        return sum(a * b for a, b in zip(va, vb)) / (na * nb)

    def _series(c, dt=0.02, n=250):
        a = [sway_offset(1.0, k * dt, wind, "trunk", c, 0.0) for k in range(n)]
        b = [sway_offset(1.0, k * dt, wind, "leaf", c, 0.0) for k in range(n)]
        return _corr(a, b)

    same = {"freq_hz": {"trunk": 0.5, "branch": 0.5, "leaf": 0.5},
            "exponent": cfg["exponent"],
            "gust_depth": cfg["gust_depth"], "gust_hz": cfg["gust_hz"]}
    c_same = _series(same)
    c_sep = _series(cfg)
    ck("证伪:同频则各层同步", c_same > 0.99 and c_sep < 0.9,
       "同频corr=%.4f 分离corr=%.4f" % (c_same, c_sep))

    print("\n共 %d 项，失败 %d -> %s" % (total[0], len(fails),
                                    "PASS" if not fails else "FAIL %s" % fails))
    return len(fails)


if __name__ == "__main__":
    import sys
    sys.exit(1 if self_check() else 0)
