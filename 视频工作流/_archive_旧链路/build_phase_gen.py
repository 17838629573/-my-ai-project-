#!/usr/bin/env python3
"""出片前置：生图任务包 + 生图顺序队列。
依赖: shot_plan genqueue prompt_tpl wind_response pose _common build_util
被依赖: build_video
改前必读: IMPROVE_build_video.md
铁律: T81 一次只生成一种物体的一类图，禁提示词混用
      T97 生图时代码告诉 AI 路面几何 / 结构性量禁"正在迈步"等模糊词
"""
import math
import shot_plan as SP
import genqueue as GQ
import prompt_tpl as PT
from wind_response import wind_response as _wr
from build_util import _joint_seq, _need


def plan_shots(spec, W, H, baseline_y):
    """生图任务包：代码告诉 AI 路画在哪（铁律97）。"""
    scene_plan = {"canvas": {"w_px": W, "h_px": H},
                  "reference": spec["scale"]["reference"],
                  "baseline_y": baseline_y,
                  "objects": spec["scale"]["objects"],
                  "path": spec["path"]}
    objs_plan = [{"name": o["name"], "kind": o.get("kind", "ground_contact"),
                  "real_m": float(o["real_m"]), "on_path": o.get("on_path", True),
                  "s": float(o.get("s", 0.0)), "offset": float(o.get("offset", 0.0)),
                  "anchor_xy": o.get("anchor_xy")}
                 for o in spec["scale"]["objects"]]
    plan = SP.plan_shot((H, W), scene_plan, objs_plan)
    print(f"[4] 生图任务包: {plan['prompts']['background']}")
    return plan


def _solve_structural(fam, spec, o, U):
    """结构性量一律由代码算出后随任务包下发（铁律：禁凭印象描述姿态）。"""
    _solved = {}
    if fam == "biped":
        import pose as _P
        import _common as _C
        _rig = spec["biped_rig"]
        _g = dict(_rig["gait"])
        _sp = float(_g["speed_m_s"])
        _st = float(_g.get("stride_m", o["real_m"] * 0.88))
        _g["cycle_s"] = _C.gait_cycle_from_speed(_sp, _st)
        _g["stride_m"] = _st
        # 【已修】帧数 = round(物理周期 × 素材采样帧率)，禁硬编码 30（铁律29）
        _F = float(spec.get("素材采样帧率", 32))
        _n = max(8, int(round(float(_g["cycle_s"]) * _F)))
        _solved["帧数"] = _n
        _solved["关节坐标"] = _joint_seq(spec, o["real_m"], n_key=_n)
    elif fam == "cloth":
        _w = _wr("flag", o["real_m"], U)
        _solved["周期s"] = round(_w["period_s"], 3)
        _solved["末端幅度m"] = round(_w["amp_m"], 3)
    elif fam == "vegetation":
        _w = _wr("trunk", o["real_m"], U)
        _solved["周期s"] = round(_w["period_s"], 3)
    return _solved


def _cloth_phys_points(solved, real_m, n=35):
    """旗帜逐帧物理点：周期与幅度来自 wind_response 数值层，禁硬编码。"""
    _T = float(solved["周期s"])
    _A = float(solved["末端幅度m"])
    _Lm = float(real_m or 2.5)
    _pts = []
    for _i in range(n):
        _t = _T * _i / n
        _ph = 2 * math.pi * _i / n
        # 末端走闭合正弦：s=(1-cos φ)/2 ∈[0,1]，i=0 与 i=n 同值 → 可循环。
        # 禁线性爬升（旧实现 y 是相位的一次函数，首尾不闭合、第1帧还额外跳 0.5A）。
        _s = (1.0 - math.cos(_ph)) / 2.0
        _pts.append("帧%d t=%.2fs: 末端(%.3f,%.3f) 杆侧(0.000,0.000)"
                    % (_i + 1, _t,
                       _Lm * (0.50 + 0.12 * _s),   # 扬起时旗面展开、水平伸出更多
                       _A * _s))                    # 竖直正弦振荡，峰峰=A
    return (("周期%.3fs 末端峰峰%.3fm（数值来自 wind_response）；" % (_T, _A))
            + "；".join(_pts)), _pts, n


def emit_gen_queue(spec, U):
    """生图顺序：一次只生成一种物体的一类图（铁律81），禁混用提示词。"""
    fams = spec.get("families")
    if not fams:
        raise SystemExit("[4b] 缺 families 映射（物体名->族），禁猜（铁律31）")
    _qobjs = []
    for o in spec["scale"]["objects"]:
        nm = o["name"]
        if nm not in fams:
            raise SystemExit(f"[4b] 物体 {nm} 未声明族，禁静默降级")
        fam = fams[nm]
        spec_d = {"风格": spec.get("style", "唐代写实"), "背板色": "#FF00FF"}
        if fam == "biped":
            spec_d.update({"构图占比": "70%"})
        elif fam == "vegetation":
            spec_d.update({"构图占比": "70%"})
        for slot in PT.scale_slots(fam):
            # 【已修】冠幅/肩高等次尺寸原一律取 real_m，导致冠幅=树高。
            # 优先读 spec 显式声明的槽位，无声明才回退 real_m。
            spec_d[slot] = o.get(slot, o["real_m"])
        _solved = _solve_structural(fam, spec, o, U)
        if fam == "rigid":
            _anc = o.get("anchor") or {}
            spec_d["注册点"] = _anc.get("type", "wheel_contact")
            _solved["注册点"] = spec_d["注册点"]
        if _solved.get("帧数"):
            # 网格容量必须 >= 帧数：ceil(sqrt(n)) 方阵，禁写死 5x6/6x6
            _c = math.ceil(math.sqrt(int(_solved["帧数"])))
            spec_d["帧数"] = int(_solved["帧数"])
            spec_d["网格"] = "%dx%d" % (_c, _c)
        if fam == "biped" and _solved.get("关节坐标"):
            spec_d["关节坐标"] = _solved["关节坐标"]
        if fam == "cloth":
            _F = float(spec.get("素材采样帧率", 32))
            spec_d["帧数"] = max(8, int(round(float(_solved["周期s"]) * _F)))
            spec_d["固定边"] = "杆侧（贴旗杆一边逐帧不动）"
            _ptxt, _pts, _n = _cloth_phys_points(
                _solved, o.get("real_m"), n=spec_d["帧数"])
            spec_d["物理点"] = _ptxt
            _solved["物理点"] = _pts
            _solved["points"] = _pts
        if spec_d.get("帧数"):
            # 网格容量 >= 帧数：ceil(sqrt(n)) 方阵，禁写死 5x6/6x6
            _c = math.ceil(math.sqrt(int(spec_d["帧数"])))
            spec_d["网格"] = "%dx%d" % (_c, _c)
        _qobjs.append({"物体": nm, "族": fam, "spec": spec_d, "solved": _solved})
    _q = GQ.plan(_qobjs)
    print(f"[4b] 生图顺序 共{_q['n']}批 —— 一次只生成一种物体的一类图，禁混用提示词")
    _done = set()
    while True:
        tk = GQ.next_task(_q, _done)
        if not tk:
            break
        print(f"   [{len(_done)+1}/{_q['n']}] {tk['id']}\n{GQ.build_prompt(tk)}\n")
        _done.add(tk["id"])
    return _q
