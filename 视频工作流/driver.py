#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""driver —— 先判族，再选驱动器（铁律77-80）

程序负责: 族校验 / 驱动器分派 / 注册点与路径参数计算 / 输出 AI 必做清单
AI 负责: 判族 / 搜物性 / 确认生图工具能力 / 按清单生图

依赖: 无（纯分派，不 import 业务模块，避免成环）
被依赖: solver_survey, build_video
改前必读: IMPROVE_driver.md
"""
from __future__ import annotations
import ast

# 族 -> 驱动器规格（禁在此处出现具体物体名，铁律36/37：示例在 EXAMPLES 区）
FAMILIES = {
    "biped": {
        "skeleton": True,
        "driver": "pose.solve",
        "sheet": True,
        "anchor": "foot_contact",
        "must": [
            "生图用结构性文本姿态（铁律73：骨架图永不进画面）",
            "每帧姿态量必须来自 pose.solve 输出，禁凭印象写模糊词",
            "走循环须 in-place + 脚接触线在格底 + 相机固定",
        ],
    },
    "quadruped": {
        "skeleton": True,
        "driver": "pose.solve(quadruped)",
        "sheet": True,
        "anchor": "hoof_contact",
        "must": [
            "四腿相位交错，禁按两条腿生成后再镜像",
            "脊柱参与起伏，禁把躯当刚体",
        ],
    },
    "vegetation": {
        "skeleton": False,
        "driver": "wind_sway.wind_sway",
        "sheet": False,
        "anchor": "trunk_base",
        "must": [
            "只生一张图，禁生成序列帧（铁律77：无骨骼物体禁骨架）",
            "摆动由代码顶点位移完成：树根不动、树梢摆幅最大",
            "生图时树干必须与地面垂直，倾斜留给代码算",
        ],
    },
    "rigid": {
        "skeleton": False,
        "driver": "rigid_body",
        "sheet": False,
        "anchor": "wheel_contact",
        "must": [
            "只生一张图，车轮自转与位移由代码算，禁序列帧",
            "注册点须声明为轮胎接地面中点（铁律：定位靠注册点不靠肉眼）",
            "若带拉车动物，动物与车靠挂接点连接，分别独立驱动",
        ],
    },
    "cloth": {
        "skeleton": False,
        "driver": "chain",
        "sheet": True,
        "anchor": "固定端",
        "must": [
            "帧数由 solver 从周期算出，禁手填（铁律29）",
            "骨架仅作 control map；无该接口时改文本描述，禁当参考图临摹",
        ],
    },
    "fluid": {
        "skeleton": False,
        "driver": "water.drop_terminal_velocity / rain_inclination / streak_length",
        "sheet": False,
        "anchor": "无（粒子层，不占骨架）",
        "must": [
            "雨强 I(mm/h) 是唯一输入量纲，禁凭印象写密度或速度（铁律96）",
            "倾斜角 = arctan(v_wind/U)，1mm 滴在 4m/s 风中恰 45°，禁手填角度",
            "粒子拖尾长 = V*t + 2R，V 由终速公式算，禁写死像素长度",
            "溅射与否用 K=We·Oh^-0.4 与 Kc 比较，禁凭印象决定画不画水花",
        ],
    },
    "water_body": {
        "skeleton": False,
        "driver": "water.wave_speed / wave_omega / ripple_from_rain",
        "sheet": False,
        "anchor": "水面线（由 groundline 探测）",
        "must": [
            "涟漪波长与相速由色散关系 ω²=(gk+σk³/ρ)tanh(kh) 算出（铁律95）",
            "λ<1.7cm 为毛细波、反之为重力波，禁混为一谈",
            "人物入水后受力与失稳由 wading_state 的 d·v / d·v² 双判据给出",
        ],
    },
}

# 示例区（铁律37：示例必须硬编码，供其他 AI 建立心智模型）
# BEGIN EXAMPLES
EXAMPLES = [
    ("biped", "人物", "躯干/四肢 humanoid，足端轨迹由 pose 算"),
    ("quadruped", "马、骆驼、犬", "四足，四腿相位交错，非两条腿镜像"),
    ("vegetation", "旱柳、胡杨", "无骨骼，单图 + 顶点风摆，树梢摆幅最大"),
    ("rigid", "马车", "刚体，车轮自转，注册点在轮胎接地面中点"),
    ("cloth", "幡旗", "受迫链，帧数=周期×FPS"),
    ("fluid", "雨、雪、雾", "粒子层，由雨强 I 驱动，倾斜角=arctan(v_wind/U)"),
    ("water_body", "溪流、水面", "波场，由色散关系算，入水失稳用 d·v 判据"),
]
# END EXAMPLES

HARDCODE_BAN = ["玄奘", "幡旗", "胡杨", "旱柳", "马车", "城墙"]


class DriverError(ValueError):
    pass


def classify(obj):
    """校验物体的族声明。族由 AI 判（铁律79），代码只校验。"""
    if not isinstance(obj, dict):
        raise DriverError("物体必须是 dict")
    name = obj.get("名称") or obj.get("name")
    fam = obj.get("族") or obj.get("family")
    if not name:
        raise DriverError("缺槽位 物体.名称")
    if not fam:
        raise DriverError(f"缺槽位 {name}.族 —— 族由 AI 判定，禁默认 biped")
    if fam not in FAMILIES:
        raise DriverError(f"{name} 的族 '{fam}' 未登记，可选: {sorted(FAMILIES)}")
    return fam


def plan(objects):
    """分派驱动器，并输出 AI 必做清单（铁律80：不许静默降级）。"""
    if isinstance(objects, dict):
        objects = [objects]
    out = []
    for o in objects:
        fam = classify(o)
        # 纵深防御①：族字段必须真实存在，禁"缺失即补默认"
        if not (o.get("族") or o.get("family")):
            raise DriverError("族字段缺失，禁补默认值（plan 纵深防御①）")
        # 纵深防御②：族必须已登记，不依赖 classify 单点抛错
        if fam not in FAMILIES:
            raise DriverError(
                f"族 '{fam}' 未在 FAMILIES 登记（plan 二次校验拦截）")
        spec = FAMILIES[fam]
        item = {
            "名称": o.get("名称") or o.get("name"),
            "族": fam,
            "有骨骼": spec["skeleton"],
            "驱动器": spec["driver"],
            "需序列帧": spec["sheet"],
            "注册点类型": spec["anchor"],
            "AI必做": list(spec["must"]),
            "提示词模板": f"tpl-{fam}",
        }
        # 程序做不到的：提示词必须按族取模板，禁 AI 自写 / 禁按具体物体写死
        item["AI必做"].append(
            f"生图提示词走 prompt_tpl.build('{fam}', params)，"
            f"禁自写、禁按具体物体名写死（铁律81）"
        )
        if spec["skeleton"]:
            item["AI必做"].append(
                "姿态描述须用代码算出的结构性量（关节角/足端坐标），"
                "禁'迈步中'等模糊词（铁律83）"
            )
        else:
            item["AI必做"].append("无骨骼族：只生单张图，禁序列帧（铁律77）")
        # 程序能算的，在这里算掉；算不出的列进 AI 必做
        if not o.get("注册点"):
            item["AI必做"].append(
                f"补声明注册点（类型 {spec['anchor']}）——定位靠注册点，禁凭肉眼摆"
            )
        if spec["sheet"] and not o.get("周期s"):
            item["AI必做"].append(
                "周期未定：帧数=周期×FPS，须由 solver 算出，禁手填"
            )
        if not spec["sheet"] and o.get("序列帧数"):
            item["违规"] = f"{fam} 无骨骼，禁生成序列帧（铁律77）"
        out.append(item)
    return out


def briefing(objects, tool_caps=None):
    """代码 -> AI 的任务包。程序做不到的逐条提醒。"""
    items = plan(objects)
    lines = ["【代码任务包 · 本片 AI 必须完成以下事项】", ""]
    for it in items:
        lines.append(f"· {it['名称']}（族 {it['族']}）")
        lines.append(f"    驱动器 {it['驱动器']}  骨骼={it['有骨骼']}  序列帧={it['需序列帧']}")
        for m in it["AI必做"]:
            lines.append(f"    [必做] {m}")
        if "违规" in it:
            lines.append(f"    [违规] {it['违规']}")
        lines.append("")
    # 程序无法自行确认的能力，必须问 AI
    lines.append("【代码无法自证，须 AI 确认】")
    lines.append("  当前生图工具是否支持传 control map（如 OpenPose）？")
    if tool_caps is None:
        lines.append("    → 未声明。未确认前一律按不支持处理：")
        lines.append("      禁止把骨架图当参考图喂入（会被画进画面，铁律78）")
        lines.append("      姿态改走结构性文本描述")
    else:
        lines.append(f"    → 已声明 {tool_caps}")
    lines.append("")
    lines.append("【示例（照此分辨族）】")
    for fam, who, why in EXAMPLES:
        lines.append(f"  {fam:11s} {who}：{why}")
    lines.append("")
    lines += _genqueue_brief(objects)
    return "\n".join(lines)


def _genqueue_brief(objects):
    """生图纪律：一次只放行一个物体的一类图，防提示词混用（铁律81-85）"""
    try:
        import genqueue as GQ
    except Exception as e:                      # 不成环：genqueue 不依赖 driver
        return [f"[降级] genqueue 未接入（{e}）：须人工保证一次一物体"]
    try:
        q = GQ.plan([{"物体": o.get("物体") or o.get("名称"),
                      "族": o.get("族"), "spec": o.get("spec", {}),
                      "solved": o.get("solved", {})} for o in objects])
    except Exception as e:
        return [f"[必做] 生图队列未建立：{e}", "  先补全族的必填槽，再逐物体生成"]
    out = ["【生图顺序 · 一次只生成一种物体的一类图】",
           f"  共 {q['n']} 个任务，逐个放行；前一个未验收，不放行下一个",
           "  每次只把下面『当前任务』的提示词喂给生图工具，",
           "  禁止一次铺开多物体的提示词（会概念泄漏/混用）"]
    t = GQ.next_task(q, set())
    if t is not None:
        out.append(f"  当前任务 {t['id']}")
        try:
            out.append("  " + GQ.build_prompt(t).replace("\n", "\n  "))
        except Exception as e:
            out.append(f"  [待补] 该物体槽位不全：{e}")
    return out


# ---------------- 自检 ----------------
def _chk(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ((" " + info) if info else ""))
    return bool(ok)


def _scan_targets():
    """取真实逻辑区源码（模块级 FAMILIES + 函数/类体）。

    原实现只取 split(BEGIN)[0]（示例区之前的 docstring+import），
    真正的逻辑一行没扫 —— 是空转的假 PASS。改用 AST，并跳过
    EXAMPLES 常量与 HARDCODE_BAN 词表本身（否则自指误报）。
    """
    src = open(__file__, encoding="utf-8").read()
    tree = ast.parse(src)
    parts = []
    for n in tree.body:
        if isinstance(n, ast.Assign):
            nm = [t.id for t in n.targets if isinstance(t, ast.Name)]
            if any(k in nm for k in ("EXAMPLES", "HARDCODE_BAN")):
                continue
            parts.append(ast.get_source_segment(src, n) or "")
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef)):
            if n.name in ("_scan_hardcode", "_scan_targets", "self_check"):
                continue
            parts.append(ast.get_source_segment(src, n) or "")
    return "\n".join(parts)


def _scan_hardcode(src=None):
    """逻辑区禁具体物体名（铁律82）；EXAMPLES 常量豁免（铁律37）。"""
    text = _scan_targets() if src is None else src
    return [w for w in HARDCODE_BAN if w in text]


def self_check():
    ok = []
    # 1 族缺失必须报错，且不得默认 biped
    try:
        plan([{"名称": "X"}])
        ok.append(_chk("族缺失即报错", False, "未报错=会静默默认"))
    except DriverError as e:
        ok.append(_chk("族缺失即报错", "族" in str(e), str(e)[:40]))

    # 2 未登记族必须报错
    try:
        plan([{"名称": "X", "族": "bird"}])
        ok.append(_chk("未登记族报错", False))
    except DriverError:
        ok.append(_chk("未登记族报错", True))

    # 3 无骨骼族声明序列帧 -> 必须标记违规（不能静默放过）
    r = plan([{"名称": "T", "族": "vegetation", "序列帧数": 35}])
    ok.append(_chk("无骨骼禁序列帧", r[0].get("违规", "").find("铁律77") >= 0,
                   r[0].get("违规", "")))

    # 4 有骨骼族不得被判为无骨骼
    r = plan([{"名称": "P", "族": "biped", "周期s": 1.0}])
    ok.append(_chk("biped 需序列帧", r[0]["需序列帧"] is True))

    # 5 必做清单非空（铁律80：不许空包）
    ok.append(_chk("必做清单非空", all(len(i["AI必做"]) > 0 for i in r)))

    # 6 注册点未声明 -> 必须进提醒
    ok.append(_chk("缺注册点必提醒",
                   any("注册点" in m for m in r[0]["AI必做"])))

    # 7 声明了注册点则不重复提醒
    r2 = plan([{"名称": "P", "族": "biped", "周期s": 1.0,
                "注册点": [10, 20]}])
    ok.append(_chk("有注册点则不提",
                   not any("补声明注册点" in m for m in r2[0]["AI必做"])))

    # 8 工具能力未声明 -> 必须输出降级禁令
    b = briefing([{"名称": "P", "族": "biped", "周期s": 1.0,
                   "注册点": [10, 20]}])
    ok.append(_chk("未声明能力须禁参考图", "禁止把骨架图当参考图" in b))

    # 9 证伪：注入"默认 biped"的假实现必须被抓
    orig = dict(FAMILIES)
    try:
        def _bad(o):
            return "biped"
        _save = globals()["classify"]
        globals()["classify"] = lambda o: o.get("族", "biped")
        try:
            plan([{"名称": "X"}])
            ok.append(_chk("证伪:禁止默认biped", False, "缺族竟通过"))
        except Exception:
            ok.append(_chk("证伪:禁止默认biped", True))
        globals()["classify"] = _save
    finally:
        globals()["FAMILIES"] = orig

    # 10 逻辑区无硬编码物体名（示例区豁免）
    src = open(__file__, encoding="utf-8").read()
    hits = _scan_hardcode()   # 用 AST 目标区，禁传整文件（会把示例区算进来）
    ok.append(_chk("逻辑区无物体名", not hits, str(hits)))

    # 证伪：扫描器本身必须有效，且目标区必须真覆盖逻辑，否则上一项是空转的假PASS
    probe = _scan_hardcode("玄奘立于城墙持幡旗")
    ok.append(_chk("证伪:扫描器有效", len(probe) >= 3, str(probe)))
    tgt = _scan_targets()
    ok.append(_chk("证伪:目标区覆盖FAMILIES",
                   "FAMILIES" in tgt and len(tgt) > 3000, f"len={len(tgt)}"))

    # 13 briefing 必须带生图顺序纪律，否则 genqueue 接了等于没接
    b = briefing([{"名称": "玄奘", "族": "biped"},
                  {"名称": "旱柳", "族": "vegetation"}])
    ok.append(_chk("briefing含生图顺序", "一次只生成" in b and "当前任务" in b))
    # 14 证伪：物体缺族时队列建立失败，必须明说而非静默跳过
    try:
        briefing([{"名称": "未知物", "族": None}])
        ok.append(_chk("证伪:缺族不静默", False, "未报错=静默降级"))
    except DriverError:
        ok.append(_chk("证伪:缺族不静默", True, "缺族即抛错"))

    print(f"\n自检 {sum(ok)}/{len(ok)} 项 PASS")
    return all(ok)


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
