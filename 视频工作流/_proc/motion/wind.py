# 契约: proc/motion/wind
#   一句话: 风场：主弯曲 + 细节弯曲，相位纳入世界坐标使异株不同步
#   完整契约见 motion/__init__.py
# -*- coding: utf-8 -*-
"""风场 —— 主弯曲 + 细节弯曲

出处：GPU Gems 3, Chapter 16《Vegetation Procedural Animation and Shading in Crysis》
      NVIDIA Developer；CRYENGINE 官方文档 Detail Bending 页。

主弯曲（低频、大形变，主干整体倒伏）：
    fBF = z * bend_scale
    fBF += 1
    fBF = fBF*fBF - fBF
    pos.xy += wind.xy * fBF
    pos = normalize(pos) * len        ← 重缩放，避免拉伸

细节弯曲（高频、微颤，枝/叶）：
    相位纳入 **世界坐标** → 每株不同步（否则整片林子像节拍器）
    f = (1.975, 0.793, 0.375, 0.193)
    w = SmoothTriangleWave(frac((t+phase)*f)*2-1) * speed * detail_freq
    sum = w.xz + w.yw
    pos += sum.xxy * (edge_amp*n.xy, branch_amp)
"""
import numpy as np

# GPU Gems 3 Ch.16 原文给的四个频率："1.975, 0.793, 0.375, 0.193 are good frequencies"
FREQ = np.array([1.975, 0.793, 0.375, 0.193], dtype=np.float32)


def _frac(x):
    return x - np.floor(x)


def triangle_wave(x):
    """GPU Gems 3 Ch.16 原文逐字：abs(frac(x + 0.5) * 2.0 - 1.0) → [0,1]，周期 1。

    注意不是我先前写的 *2-1（那个是 [-1,1]，会让后面的 SmoothCurve 溢出到 5）。
    """
    return np.abs(_frac(x + 0.5) * 2.0 - 1.0)


def smooth_triangle_wave(x):
    """SmoothTriangleWave = SmoothCurve(TriangleWave(x))。

    SmoothCurve = x*x*(3-2x)，SmoothTriangleWave = SmoothCurve(TriangleWave(x))。
    原文用它是为了不做真 sin 也能得到平滑波形（省指令数）。
    输出恒在 [0,1] —— 这意味着风把叶/枝**往一侧推**，而不是对称来回摆，
    这一点是符合物理的：风吹是单向偏置，摆幅在"不动↔最大"之间脉动。
    """
    t = triangle_wave(x)
    return t * t * (3.0 - 2.0 * t)


def main_bend(z_norm, wind_xy, bend_scale=1.0):
    """主弯曲位移。z_norm=归一化高度（根0→顶1）。

    返回 (dx, dy) 像素或米，随高度单调增大 → 根不动、梢倒得最多。
    """
    z = np.asarray(z_norm, dtype=np.float32)
    fBF = z * bend_scale
    fBF = fBF + 1.0
    fBF = fBF * fBF - fBF
    w = np.asarray(wind_xy, dtype=np.float32)
    return w[0] * fBF, w[1] * fBF


def detail_phase(world_xyz, branch_phase=0.0):
    """相位纳入世界坐标（原文 fObjPhase = dot(worldPos.xyz, 1)）。

    这一步是"每株树不同步"的唯一来源 —— 没有它整片植被会齐刷刷地摆。
    """
    p = np.asarray(world_xyz, dtype=np.float32)
    return float(np.dot(p, np.ones_like(p)) + branch_phase)


def detail_bend(t, world_xyz, speed=1.0, detail_freq=1.0,
                edge_amp=1.0, branch_amp=1.0, n_xy=(1.0, 0.0),
                branch_phase=0.0):
    """细节弯曲。返回 (dx, dy, dz)，前两项是边缘摆动，第三项沿法向上下。"""
    ph = detail_phase(world_xyz, branch_phase)
    waves_in = np.array([t + ph, t + ph + branch_phase], dtype=np.float32)
    v = np.concatenate([waves_in, waves_in]) * np.concatenate([FREQ[[0, 1]], FREQ[[2, 3]]])
    w = (_frac(v) * 2.0 - 1.0) * speed * detail_freq
    w = smooth_triangle_wave(w)
    s = np.array([w[0] + w[2], w[1] + w[3]], dtype=np.float32)  # vWaves.xz + vWaves.yw
    nx, ny = n_xy
    return float(s[0] * edge_amp * nx), float(s[0] * edge_amp * ny), float(s[1] * branch_amp)


def sway(t, world_xyz, wind_xy, z_norm=1.0, bend_scale=1.0,
         speed=1.0, detail_freq=1.0, edge_amp=1.0, branch_amp=1.0,
         n_xy=(1.0, 0.0), branch_phase=0.0):
    """主弯曲 + 细节弯曲的合成 —— 树/草/旗统一走这个函数，共享同一个风场。"""
    mx, my = main_bend(z_norm, wind_xy, bend_scale)
    dx, dy, dz = detail_bend(t, world_xyz, speed, detail_freq,
                             edge_amp, branch_amp, n_xy, branch_phase)
    return float(mx + dx), float(my + dy)


# ------------------------------------------------------------------ 自检
def _selfcheck():
    ok = {}
    # 1 三角波周期与范围
    xs = np.linspace(0, 4, 401)
    tw = triangle_wave(xs)
    ok["tri 范围[0,1]"] = bool(np.all(tw >= -1e-6) and np.all(tw <= 1.0 + 1e-6))
    ok["tri 周期1"] = bool(abs(triangle_wave(0.0) - triangle_wave(1.0)) < 1e-6)
    # 2 平滑化后仍在同一范围（原文 SmoothCurve(x)=x²(3-2x) 仅在 x∈[0,1] 值域 [0,1]）
    st = smooth_triangle_wave(xs)
    ok["smooth 范围[0,1]"] = bool(np.all(st >= -1e-6) and np.all(st <= 1.0 + 1e-6))
    # 2b 且必须真的在脉动（不是常数）
    ok["smooth 有脉动"] = bool(float(np.std(st)) > 0.05)
    # 3 主弯曲：根不动、梢最大
    zs = np.linspace(0, 1, 11)
    d = main_bend(zs, (10.0, 0.0), bend_scale=1.0)[0]
    ok["主弯曲根=0"] = bool(abs(d[0]) < 1e-6)
    ok["主弯曲单调递增"] = bool(np.all(np.diff(d) > -1e-6))
    # 4 相位入世界坐标 → 不同位置的树不同步（关键：否则像节拍器）
    a = [detail_bend(t, (0.0, 0.0, 0.0), speed=1.0)[0] for t in np.linspace(0, 2, 60)]
    b = [detail_bend(t, (7.3, 0.0, 2.1), speed=1.0)[0] for t in np.linspace(0, 2, 60)]
    corr = float(np.corrcoef(a, b)[0, 1])
    ok["异株不同步(|corr|<0.9)"] = bool(abs(corr) < 0.9)
    # 5 同株可复现（确定性）
    ok["同参数可复现"] = bool(
        abs(detail_bend(1.234, (1.0, 2.0, 3.0))[0]
            - detail_bend(1.234, (1.0, 2.0, 3.0))[0]) < 1e-12)
    # 6 风越大摆越大
    w1 = abs(sway(0.5, (0, 0, 0), (2.0, 0), z_norm=1.0)[0])
    w2 = abs(sway(0.5, (0, 0, 0), (8.0, 0), z_norm=1.0)[0])
    ok["风大摆幅大"] = bool(w2 > w1)
    return ok


if __name__ == "__main__":
    for k, v in _selfcheck().items():
        print("  %-24s %s" % (k, "PASS" if v else "FAIL"))
    print("SELF_CHECK:", "PASS" if all(_selfcheck().values()) else "FAIL")
