"""检查域2：chain 共振/逐级递推/transient 稳态与包络衰减。

依赖: _chk_base
被依赖: solver_check
改进措施记录: IMPROVE_solver_check.md（改前必读）
"""
from _chk_base import *
from _chk_base import _r


def check(ctx=None):
    ok = True
    spec = (ctx or {}).get("spec")
    a = (ctx or {}).get("a") or solve(BASE_SPEC)

    # 7) B 含泊松比项（铁律20同类：同名符号不同义）
    E, t, nu, W = 5.0e9, 2.0e-4, 0.34, 0.30
    b_exp = E * W * t**3 / (12.0 * (1.0 - nu*nu))
    ok &= _r("B含泊松比项E·h³/12(1-ν²)",
             abs(a["derived"]["B_nm2"] - b_exp) < 1e-12,
             "B=%.4e (漏项会差13.1%%)" % a["derived"]["B_nm2"])

    # 8) 缺 criteria 必须报错（铁律32：判据不许内置）
    r2 = False
    try:
        bad = {k: v for k, v in spec.items() if k != "criteria"}
        solve(bad)
    except ValueError:
        r2 = True
    ok &= _r("缺判据报错(禁内置文献)", r2)

    # 9) 换物性 -> regime 随之变（μ 判据下 σ 真起作用）
    heavy = dict(spec)
    heavy["material"] = dict(spec["material"], sigma=0.500)   # 唐麻布 500 g/m2
    a2 = solve(heavy)
    ok &= _r("物性驱动regime(μ判据)", a["regime"] != a2["regime"],
             "绢62g→%s  麻布500g→%s (μ=%.3f/%.3f)"
             % (a["regime"], a2["regime"],
                a["dimensionless"]["mu"], a2["dimensionless"]["mu"]))

    # 10) chain: 共振放大（r≈1 时 M 最大）
    lk = [{"L": 0.30, "m": 0.010, "EI": 1.0e-4}]          # 单级：发丝
    f_n = chain_response(lk, 1.0, 0.02)[0]["f_n_hz"]
    off = chain_response(lk, f_n * 3.0, 0.02)[0]           # 远离共振
    res = chain_response(lk, f_n, 0.02)[0]                 # 恰好共振
    ok &= _r("chain 共振放大 M>1", res["M"] > off["M"] and res["M"] > 1.0,
             "共振M=%.2f  远离M=%.2f  (f_n=%.2fHz)" % (res["M"], off["M"], f_n))

    # 11) chain: 缺物性即报错（铁律31 覆盖新族）
    c1 = False
    try:
        chain_response([{"L": 0.3, "m": 0.01}], 1.0, 0.02)
    except ValueError:
        c1 = True
    ok &= _r("chain 缺物性报错", c1)

    # 12) chain: 逐级递推（后级振幅 = 前级 × 自身放大）
    two = chain_response([{"L": 0.30, "m": 0.010, "EI": 1.0e-4},
                          {"L": 0.10, "m": 0.003, "EI": 2.0e-5}], 1.0, 0.02)
    exp2 = two[0]["amp_m"] * two[1]["M"]
    ok &= _r("chain 逐级递推", abs(two[1]["amp_m"] - exp2) < 1e-12,
             "L1=%.4f L2=%.4f m" % (two[0]["amp_m"], two[1]["amp_m"]))

    # 13) transient: 冲击后回到稳态值，不是 0
    #     断言须用 5τ（e^-5≈0.67%）——仅 1.14τ 剩 32% 属正常，非代码错
    f_n_hz, zeta_t = 0.91, 0.10
    tau0 = 1.0 / (zeta_t * 2 * math.pi * f_n_hz)
    tr = transient_envelope(f_n_hz, zeta_t, 5 * tau0, a_peak=0.30, a_steady=0.02)
    tail = tr["envelope"][-1]["amp_m"]
    # 残差是相对量：应为 (a_peak-a_steady)·e^-5 ≈ 0.28×0.0067=0.0019，
    # 不是绝对量。断言写绝对阈值会假 FAIL（本项已连错两次）。
    resid = (tail - 0.02) / (0.30 - 0.02)
    ok &= _r("transient 5τ后残差≈e^-5", abs(resid - math.exp(-5)) < 2e-3,
             "相对残差=%.5f（理论e^-5=%.5f）  末帧=%.5f"
             % (resid, math.exp(-5), tail))

    # 14) transient: 包络单调衰减（证伪：故意反向则必须失败）
    env = [e["amp_m"] for e in tr["envelope"]]
    mono = all(env[i + 1] <= env[i] + 1e-12 for i in range(len(env) - 1))
    ok &= _r("transient 包络单调衰减", mono and env[0] > env[-1],
             "起%.3f→末%.3f  N50=%.1f周期" % (env[0], env[-1], tr["N50_cycles"]))

    if ctx is not None:
        ctx["off"] = off
        ctx["mono"] = mono
    return ok
