#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cloth_wire — 布料（衣摆/幡/旗）的气动受力接线层

把 cloth_aero 的受力计算真正接进成片链路（此前 cloth_aero 零调用，属断链）。

业界结构（NvCloth / Unreal Clothing Tool / Bullet btSoftBody 同构）：
    幅值不是经验魔法数，而是 气动力 / 重力 的比值的函数：
        ratio = F_lift / (m·g)
        ratio < 1  布料贴体，仅小幅摆动
        ratio ≥ 1  离体（被吹起/吹飞）
    摆动幅值随 ratio 单调增并饱和 —— 力再大幅值也不会无限大（受布料长度约束）。

依赖: cloth_aero（受力）, param_decl（反问）, wind_response（频率）
被依赖: build_video
铁律99  代码内不存在的参数 → 反问 AI → AI 给「值+来源+区间」→ 代码运算
铁律102 衣摆/布料幅值必须由气动比值算出，禁调用处写死 amp_scale
铁律103 布料几何（面积/质量）由 AI 声明，代码不猜；缺失即反问
改前必读: IMPROVE_cloth_wire.md
"""

import math

import cloth_aero as CA
import param_decl as PD
import wind_response as WR

__all__ = ["garment_geom", "garment_state", "garment_amp_m", "self_check"]


def garment_geom(spec_obj):
    """从物体声明里取布料几何，缺失即反问（铁律103）。

    必填: 面积 area_m2 [m²]、质量 mass_kg [kg]
    二者都不许代码猜 —— 僧衣 0.3kg vs 厚袍 1.2kg 差 4 倍，吹飞判定完全不同。
    """
    def _get(key, why, unit, hint):
        # 【已修】两处 bug：① require() 返回值被丢弃 → v 仍是 None，float 崩；
        # ② 只查顶层，而声明写在 garment 子字典里 → 永远查不到。
        g = spec_obj.get("garment") or {}
        v = spec_obj.get(key, g.get(key))
        if v is None:
            # 铁律99：反问，不兜底（返回值必须接住，否则参数机制形同虚设）
            v = PD.require(key, "cloth", why, unit, hint)
        return float(v)

    area = _get("area_m2", "布料迎风面积，决定气动阻力/升力大小", "m²",
                "参考：僧衣下摆约 0.25~0.40 m²；幡 2.5m×1.2m ≈ 3.0 m²")
    mass = _get("mass_kg", "布料质量，决定重力与是否离体", "kg",
                "参考：薄僧衣 ~0.3kg；厚袍 ~1.2kg；唐绢 62 g/m²")
    return area, mass


def _blowoff_ratio():
    """吹飞阈值（阻力/重力 比值），属 AI 声明，代码不内置（铁律32/99）。"""
    return PD.require(
        "cloth_blowoff_ratio", "cloth",
        "判定布料是否被吹飞：阻力/重力 超过该比值即视为离体", "-",
        "参考：摆角=arctan(F/W)；比值3对应摆角71.6°，比值5对应78.7°")


def garment_state(area_m2, mass_kg, v_wind, nx=1.0, ny=0.0):
    """布料在风中的受力状态与摆角。全部由 cloth_aero 运算，本层不重算物理。

    ★ 判据修正（本轮实证）：
      原用「升力 > 重力」判吹飞 —— 错。正迎风时 v̂×n̂=0，升力恒为 0，
      导致任何风速下都判"不飞"。
      物理上衣服被掀起是【阻力绕铰接点的力矩】与重力矩平衡：
            tan(摆角) = F_drag / (m·g)
      这与既有 flag_lift_deg（旗帜扬起角）是同一关系，口径统一。
    """
    r = CA.will_blow_off(area_m2, v_wind, mass_kg, nx=nx, ny=ny)
    weight = mass_kg * CA.G   # 重力常数复用，本模块不重复定义
    drag = r["detail"]["drag_N"]
    swing = math.degrees(math.atan2(drag, weight)) if weight > 0 else 90.0
    ratio = (drag / weight) if weight > 0 else float("inf")
    thr = _blowoff_ratio()
    return {
        "lift_N": r["lift_N"],
        "weight_N": weight,
        "drag_N": drag,
        "swing_deg": swing,
        "ratio": ratio,
        "blow_off": ratio >= float(thr),
        "blowoff_threshold": float(thr),
        "dynamic_pressure_Pa": r["detail"]["dynamic_pressure_Pa"],
    }


def garment_amp_m(spec_obj, v_wind, family="garment", L_char_m=0.35,
                  nx=1.0, ny=0.0):
    """衣摆最终幅值（米）：气动比值驱动，不是魔法数（铁律102）。

    v_wind : 标量风速 [m/s] 或矢量 (vx, vy)
        cloth_aero 需要矢量（算迎风角 cosθ），wind_response 需要标量（算 St 频率）。
        本层负责换算，调用方不必关心两侧接口差异。

    amp = A_max · ratio/(ratio+1) · (L/L_ref)
      · ratio/(ratio+1)  饱和曲线：ratio=1 → 0.5，ratio=3 → 0.75，永不超 A_max
      · A_max 由 wind_response 数值层给出（族 + 特征长度 + 风速），本层不内置
    """
    if isinstance(v_wind, (tuple, list)):
        vec = (float(v_wind[0]), float(v_wind[1]))
        speed = math.hypot(*vec)
    else:
        speed = float(v_wind)
        vec = (speed, 0.0)

    area, mass = garment_geom(spec_obj)
    st = garment_state(area, mass, vec, nx=nx, ny=ny)
    wr = WR.wind_response(family, L_char_m, speed)
    a_max = float(wr["amp_m"])
    ratio = st["ratio"]
    if not math.isfinite(ratio):
        ratio = 0.0
    swing_deg = st["swing_deg"]
    sat = ratio / (ratio + 1.0)                    # 饱和因子 [0,1)
    amp = a_max * sat * (float(L_char_m) / 0.35)   # 以 0.35m 衣摆为参考长
    return {
        "amp_m": amp,
        "amp_max_m": a_max,
        "freq_hz": float(wr["freq_hz"]),
        "freq_hz_raw": float(wr.get("freq_hz_raw", wr["freq_hz"])),
        "ratio": ratio,
        "swing_deg": swing_deg,
        "blow_off": st["blow_off"],
        "lift_N": st["lift_N"],
        "weight_N": st["weight_N"],
        "drag_N": st["drag_N"],
        "saturation": sat,
    }


def self_check():
    """自检：含证伪 —— 必须能抓到「没接 cloth_aero」的假实现。"""
    ok = []

    def ck(n, c, d=""):
        ok.append((n, bool(c), d))

    # 1 几何反问：缺 area_m2 必须抛 AskAI，不得静默给默认
    try:
        garment_geom({"mass_kg": 0.3})
        ck("缺面积应反问", False, "未抛异常 = 静默兜底")
    except Exception as e:
        ck("缺面积应反问", type(e).__name__ == "AskAI", f"{type(e).__name__}")

    # 2 比值单调：风越大幅值越大且饱和
    obj = {"area_m2": 0.30, "mass_kg": 0.3}
    seq = [garment_amp_m(obj, (float(u), 0.0))["amp_m"] for u in (1, 5, 10, 20, 40)]
    ck("幅值单调递增", all(b >= a - 1e-9 for a, b in zip(seq, seq[1:])),
       f"{[round(x,4) for x in seq]}")
    ck("幅值饱和不超上限",
       all(seq[i] <= garment_amp_m(obj, (40.0, 0.0))["amp_max_m"] * 1.001
           for i in range(len(seq))),
       f"max={seq[-1]:.4f}")

    # 3 吹飞判定：轻薄大面积 vs 厚重小面积，同样风速结论必须不同
    thin = garment_state(0.35, 0.15, (12.0, 0.0))
    heavy = garment_state(0.20, 1.20, (12.0, 0.0))
    ck("薄衣摆角大于厚袍", thin["swing_deg"] > heavy["swing_deg"],
       f"薄 {thin['swing_deg']:.1f}° 厚 {heavy['swing_deg']:.1f}°")
    ck("薄衣先飞厚袍不飞", thin["blow_off"] and not heavy["blow_off"],
       f"薄 ratio={thin['ratio']:.2f} 厚 ratio={heavy['ratio']:.2f} 阈值={thin['blowoff_threshold']}")

    # 4 无风不动
    calm = garment_amp_m(obj, (0.0, 0.0))
    ck("无风幅值为零", abs(calm["amp_m"]) < 1e-12, f"{calm['amp_m']}")

    # 5 本模块不得内置物性常数（rho/Cd/Cl 全在 param_decl）
    import ast, io
    src = open(__file__, encoding="utf-8").read()
    tree = ast.parse(src)
    magic = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Assign):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id.isupper():
                    v = getattr(n.value, "value", None)
                    if isinstance(v, (int, float)) and v > 0:
                        magic.append((t.id, v))
    ck("无内置物性常数", not magic, f"{magic}")

    # 6 证伪：把"幅值写死"的假实现代入真实判据，判据必须拒绝它
    fake_src = """
def garment_amp_m(spec_obj, v_wind, **kw):
    return {"amp_m": 0.06, "freq_hz": 1.0, "ratio": 0.0, "blow_off": False,
            "amp_max_m": 0.06, "freq_hz_raw": 1.0, "lift_N": 0, "weight_N": 0,
            "drag_N": 0, "saturation": 0.0}
"""
    ns = {}
    exec(compile(fake_src, "<fake>", "exec"), ns)
    fake = ns["garment_amp_m"]
    f_seq = [fake(obj, (float(u), 0.0))["amp_m"] for u in (1, 5, 10, 20, 40)]
    # 判据A：随风速变化（写死则不变化）
    varies = any(abs(x - f_seq[0]) > 1e-9 for x in f_seq)
    # 判据B：无风幅值为零（写死 0.06 则不为零）
    calm_zero = abs(fake(obj, (0.0, 0.0))["amp_m"]) < 1e-12
    caught = (not varies) or (not calm_zero)   # 被判据抓住 = 证伪有效
    ck("证伪：写死幅值必被判据拒绝", caught,
       f"变化={varies} 无风归零={calm_zero} 序列={[round(x,4) for x in f_seq]}")

    bad = [n for n, c, d in ok if not c]
    for n, c, d in ok:
        print(f"  {'PASS' if c else 'FAIL'}  {n}  {d}")
    print(f"cloth_wire self_check: {len(ok)-len(bad)}/{len(ok)} PASS")
    return len(bad) == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
