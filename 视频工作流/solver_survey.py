# -*- coding: utf-8 -*-
"""solver_survey —— 从 solver.py 切出（业界：文件 150-500 行最优）。

依赖: solver（懒加载，破环）
被依赖: solver
改前必读: IMPROVE_solver_survey.md
"""

# ------------------------------------------------------------ 动静问卷（铁律36）
# 【关键】代码不知道本片有什么物体——那是 AI 的活。
# 代码只做两件事：
#   ① 让 AI 盘点本片有几个动物/静物
#   ② 每建一个美术资源回来，就反问：这物件上哪些相对动、哪些相对静
# 禁在代码里硬编码任何具体物体名（幡旗/垂带/胡杨…）——铁律36

KINDS = ("人物", "动物", "静物", "植物", "流体", "其他")

# 相对动 / 相对静 的三类角色（语义判断，一律 AI 填）
PART_ROLES = {
    "anchor":  "绝对不动：固定端/基座，位移恒 0（如幡杆、树干基部）",
    "driven":  "主动运动：受外部驱动源直接作用（风/步频/冲击）",
    "passive": "被动响应：挂在上游部件上被带动（受迫阻尼，如衣摆/发丝/枝条）",
}

# 驱动源（AI 判）
DRIVE_SOURCES = {
    "wind":    "风：稳态持续负载 → 用无量纲数 regime",
    "gait":    "自身运动（走/跑）：驱动频率=步频，躯干起伏频率=2×步频",
    "impulse": "冲击/爆炸：瞬态，过后回到原扰动量（铁律35）",
    "none":    "无驱动：纯静态，不进动力学",
}

# 各 family 的物性槽位（通用，不含任何具体物体名）
SLOT_TEMPLATE = {
    "cantilever": {"geometry": ["L", "W", "t"], "material": ["sigma", "E", "nu"],
                   "fluid": ["U"], "criteria": ["regime_by"]},
    "chain":      {"drive": ["f_hz", "amp_m"], "links": ["L", "m", "EI", "zeta"]},
    "hinge":      {"geometry": ["L", "W"], "material": ["sigma"], "fluid": ["U"]},
    "free_surface": {"geometry": ["L"], "fluid": ["U"]},
}

# ============================================================ BEGIN EXAMPLES
# 【铁律36 例外区】此处允许硬编码具体物体名——用途是给 AI 建立心智模型，
# 不是参与逻辑。提问(survey/inventory)一律不含这些名字。
EXAMPLES = {
    # --- 大类：每个 kind 一个示例，含动静划分 ---
    "kind": {
        "人物": {"例": "玄奘（唐，身高1.70m）",
                 "动静": [("躯干", "driven"), ("发丝", "passive"),
                          ("衣摆", "passive"), ("足", "anchor")],
                 "驱动": "gait（步频2.0Hz，躯干起伏2×步频）"},
        "动物": {"例": "马（肩高1.60m）",
                 "动静": [("躯干", "driven"), ("鬃毛", "passive"),
                          ("尾巴", "passive"), ("蹄", "anchor")],
                 "驱动": "gait（四足步频）"},
        "静物": {"例": "幡旗（幡身0.90×0.30m）",
                 "动静": [("幡杆", "anchor"), ("幡身", "driven"),
                          ("垂带", "passive")],
                 "驱动": "wind（6级=12.3m/s）"},
        "植物": {"例": "胡杨（成熟木10m）",
                 "动静": [("树干基部", "anchor"), ("主干", "driven"),
                          ("枝条", "passive"), ("叶", "passive")],
                 "驱动": "wind（f₀≈0.26Hz，带叶ζ≈8.6%）"},
        "流体": {"例": "水面（河/海）",
                 "动静": [("水体", "driven"), ("浪花", "passive")],
                 "驱动": "wind（自由液面，用 Fr/Re）"},
        "其他": {"例": "爆炸冲击波（瞬态）",
                 "动静": [("空气", "driven"), ("衣物", "passive")],
                 "驱动": "impulse（过后回到原扰动量，非0）"},
    },
    # --- 角色：每个 role 三个跨类示例（说明它跨物体通用）---
    "role": {
        "anchor":  ["幡杆（静物）", "树干基部（植物）", "足/蹄（人物·动物·着地瞬间）"],
        "driven":  ["幡身（被风直接吹）", "躯干（被步频驱动）",
                    "主干（被风直接吹）"],
        "passive": ["垂带（挂幡身末端）", "发丝（挂头皮）",
                    "衣摆（挂肩腰）", "枝条（挂主干）"],
    },
    # --- 驱动源：每个一个示例 ---
    "source": {
        "wind":    "幡旗6级风：稳态持续，用 μ/Fr 判 regime → flapping",
        "gait":    "人走路：躯干起伏频率=2×步频，发丝 f₀≈0.9Hz 与摇摆1Hz 近共振",
        "impulse": "爆炸：A_env(t)=A_steady+(A_peak-A_steady)·e^(-ζω_n t)，回到稳态",
        "none":    "静止石碑：不进动力学，不生成序列帧",
    },
    # --- family：每个族一个示例 ---
    "family": {
        "cantilever": "只有1个 driven（无 passive）→ 悬臂梁，如单块幡身",
        "chain":      "有 passive 挂在 driven 后 → 受迫阻尼链，如幡身→垂带、躯干→发丝",
        "hinge":      "绕轴转动 → 门/窗开合",
        "free_surface": "自由液面 → 水波/涟漪",
    },
}

# AI 填完后：写到哪、填什么、跑什么（代码明示，AI 不靠猜）
HOWTO = {
    "填到哪个文件": "scene_spec.json（本目录）",
    "填什么": "assemble() 输出的『组装』+ 补齐『待搜物性』里的每个槽位",
    "跑什么命令": "python3 solver.py --run scene_spec.json",
    "跑完得到": "每个物体的 regime/频率/周期/帧数 + 35相位骨架图集 _骨架/<name>N.png",
    "然后AI做什么": "拿骨架图集去图生图 → 序列帧 <name>_fNN.png → 交回代码播放",
    "交回格式": "帧数须等于 solver.frames，±15% 内钳制，超出报错（铁律30）",
}
# ============================================================ END EXAMPLES


def survey():
    """第①步：代码向 AI 提问——本片有哪些物体？（代码不知道，AI 盘）"""
    return {
        "问": "本片有哪些物体？逐个列出并分类",
        "填": [{"name": None, "kind": list(KINDS)}],
        "注意": "连看似纯静态的物件也要列（它可能含相对动的部分）",
        "示例": {k: v["例"] for k, v in EXAMPLES["kind"].items()},
    }


def inventory(actors):
    """第②步：AI 给物体清单 -> 代码为每个物体反问『哪些相对动、哪些相对静』"""
    if not actors:
        raise ValueError("inventory: actors 为空（须先盘点本片物体，铁律36）")
    qs = []
    for a in actors:
        nm = a.get("name")
        kind = a.get("kind")
        if not nm:
            raise ValueError("inventory: 每项须含 name，缺: %r" % a)
        if kind not in KINDS:
            raise ValueError("inventory: %r 的 kind=%r 非法（应为 %s）"
                             % (nm, kind, list(KINDS)))
        qs.append({
            "物体": nm, "大类": kind,
            "问": "该物件上哪些部件相对动、哪些相对静？",
            "填": {"parts": [{"part": None, "role": list(PART_ROLES)}]},
            "驱动源": list(DRIVE_SOURCES),
            "提示": "anchor 恒不动；driven 是被直接驱动的主体；"
                    "passive 挂在上游被带动，摆幅通常大于驱动点",
            "示例": {
                "同大类可参考": EXAMPLES["kind"].get(kind, {}),
                "角色怎么分": EXAMPLES["role"],
                "驱动源怎么选": EXAMPLES["source"],
            },
        })
    return {"问卷": qs, "_roles": PART_ROLES, "_sources": DRIVE_SOURCES,
            "示例": EXAMPLES, "填到哪": HOWTO}


def scale_question(objects):
    """第②·五步：比例尺问卷（铁律63）

    代码不知道任何物体的真实尺寸——只反问。
    AI 须：搜证米制 → 指定一个命名参照物 → 其余全部由它推像素。
    业界依据：图集交付必含 pixels per unit；尺度用 named reference
    object 锁定而非肉眼；AI 无内在尺度感须显式注入米制。
    """
    return {
        "问AI(比例尺)": [
            "本片画布像素尺寸？(canvas.w_px / canvas.h_px)",
            "命名参照物是谁？真实几米？它在画面里占多少像素？"
            "（唯一，其余物体全部对它取尺度，禁止各自估）",
            "地平线 baseline_y 在第几像素？（所有站立物脚底共用，禁各画各的）",
            "每个部件的真实尺寸 real_m？是否落地 on_ground？"
            "悬挂物给 anchor_y_px 顶边；pivot 默认 bottom_center",
        ],
        "物体清单": [{"物体": o, "需填": ["real_m", "real_w_m(可选)",
                                          "on_ground", "pivot", "anchor_y_px(悬挂物)"]}
                     for o in objects],
        # === BEGIN EXAMPLES（铁律36 例外区：仅示例，不参与逻辑）===
        "示例(硬编码·供其他AI理解)": {
            "命名参照物": {"玄奘": "1.70 m（唐制约5尺）",
                           "城门洞": "8.0 m（唐含光门夯土 8.2 m，门道宽 5.35 m）"},
            "落地物": "玄奘/马/胡杨 → on_ground=true，脚底贴 baseline_y",
            "悬挂物": "城头旗 → on_ground=false，anchor_y_px=旗杆顶",
            "比例实例": {"玄奘:马": "1.06 : 1", "玄奘:城门": "1 : 4.71",
                         "玄奘:胡杨": "1 : 5.88"},
        },
        # === END EXAMPLES ===
        "校验": "合成前必跑 scale_map.verify()，偏差超 15% 不许落位（铁律64）",
        "填到哪": "scene_spec.json 的 scale 段，再跑 python3 scale_map.py",
    }
# ============================================================ END EXAMPLES


def _qname(q):
    """问卷项物体名归一化：inventory 用 name，assemble 用 物体，两阶段键名
    曾不一致（真 bug）——此处统一接受两者，缺则报错（铁律31）。"""
    nm = q.get("物体") or q.get("name")
    if not nm:
        raise ValueError("问卷项缺物体名（须含 物体 或 name）：%r" % (q,))
    return nm

def assemble(ans):
    """第③步：AI 填完问卷 -> 代码组装成 solver spec + 缺槽清单（AI 去搜）"""
    if not ans or not ans.get("问卷"):
        raise ValueError("assemble: 问卷为空（AI 须先答动静划分，铁律36）")
    specs, missing = [], []
    for q in ans["问卷"]:
        nm = _qname(q)
        src = q.get("source")
        if src not in DRIVE_SOURCES:
            raise ValueError("assemble: %r 的 source=%r 非法（应为 %s）"
                             % (nm, src, list(DRIVE_SOURCES)))
        parts = q.get("parts") or []
        if not parts:
            raise ValueError("assemble: %r 未划分部件动静（铁律36）" % nm)
        anchors, drivens, passives = [], [], []
        for p in parts:
            role = p.get("role")
            if role not in PART_ROLES:
                raise ValueError("assemble: %r 的部件 %r role=%r 非法"
                                 % (nm, p.get("part"), role))
            {"anchor": anchors, "driven": drivens,
             "passive": passives}[role].append(p)
        # 组装：driven 是链首，passive 依次挂后；anchor 不进动力学
        chain = drivens + passives
        fam = "chain" if len(chain) > 1 else "cantilever"
        specs.append({
            "物体": nm, "family": fam, "source": src,
            "锚点(恒不动)": [p.get("part") for p in anchors],
            "链": [{"part": p.get("part"), "role": p["role"]} for p in chain],
        })
        slots = SLOT_TEMPLATE[fam]
        for grp, fs in slots.items():
            for f in fs:
                if grp not in q or f not in (q.get(grp) or {}):
                    missing.append({"物体": nm, "部件组": grp, "缺": f,
                                    "提示": "搜索该物真实物性后填入"})
    # 形态族分派（driver.py）：与上面 chain/cantilever 动力学族不同维度
    # 形态族=这东西是什么（biped/vegetation/rigid…）；动力学族=怎么动
    try:
        import driver as _drv
        objs = [{"名称": _qname(q),
                 "族": q.get("形态族") or q.get("form_family"),
                 "周期s": q.get("周期s"),
                 "序列帧数": q.get("序列帧数"),
                 "注册点": q.get("注册点")} for q in ans["问卷"]]
        _plan = _drv.plan(objs)
        for it in _plan:
            if "违规" in it:
                missing.append({"物体": it["名称"], "部件组": "形态族",
                                "缺": "合规", "提示": it["违规"]})
    except Exception as e:  # 形态族未填时 driver 报错，转成待办而非崩
        _plan = None
        missing.append({"物体": "全部", "部件组": "形态族",
                        "缺": "形态族",
                        "提示": "须逐物体判形态族 "
                                "(biped/quadruped/vegetation/rigid/cloth)："
                                + str(e)[:80]})
    return {"组装": specs, "待搜物性": missing,
            "驱动分派": _plan,
            "填到哪": HOWTO,
            "示例": {"family怎么选": EXAMPLES["family"],
                     "角色怎么分": EXAMPLES["role"]},
            "比例尺": scale_question(list({_qname(q) for q in ans["问卷"]})),
            "生图规格": {"帧数": "由 solver 输出 frames=round(T·FPS)，禁手填（铁律29）",
                         "相位": "由 solver 输出 phase_geometry，先画骨架再图生图",
                         "参考图": "近景需含比例尺参照物；远景标 LOD 等级"},
            "交付回代码": {"格式": "序列帧 <name>_fNN.png，帧数须等于 solver.frames",
                           "校验": "帧数不符 ±15% 内钳制，超出报错（铁律30）"}}


def briefing_text(b, with_examples=True):
    """可读任务包。代码输出后 AI 照做即可，不靠记忆（铁律33）。

    with_examples=True 时附带硬编码示例——给**其他 AI**建立简陋心智模型，
    使其能分辨"动/静""哪类族"。本 AI 已理解时可传 False 省字数。
    """
    L = ["=" * 62, "【代码任务包 · 本片 AI 必须完成以下事项】", ""]

    if with_examples and "示例" in b:
        ex = b["示例"]
        L.append("【先建立心智模型·示例（照此分辨动/静）】")
        for k, v in EXAMPLES["kind"].items():
            dm = "  ".join("%s=%s" % (p, r) for p, r in v["动静"])
            L.append("  %s  例:%s" % (k, v["例"]))
            L.append("      动静:%s" % dm)
            L.append("      驱动:%s" % v["驱动"])
        L.append("")
        L.append("  anchor(绝对不动) 例: " + "、".join(EXAMPLES["role"]["anchor"]))
        L.append("  driven(主动运动) 例: " + "、".join(EXAMPLES["role"]["driven"]))
        L.append("  passive(被动响应)例: " + "、".join(EXAMPLES["role"]["passive"]))
        L.append("")
        for k, v in EXAMPLES["family"].items():
            L.append("  族 %-13s %s" % (k, v))
        L.append("")

    for q in b.get("问卷", []):
        L.append("· 物体 %s（%s）" % (q["物体"], q["大类"]))
        L.append("    " + q["问"])
        L.append("    角色取值: " + " / ".join(
            "%s=%s" % (k, v.split("：")[0]) for k, v in PART_ROLES.items()))
        L.append("    驱动源: " + ", ".join(DRIVE_SOURCES))
        ref = q.get("示例", {}).get("同大类可参考")
        if isinstance(ref, dict) and ref:
            L.append("    同类参考: %s  动静=%s"
                     % (ref.get("例"), "  ".join(
                         "%s:%s" % (p, r) for p, r in ref.get("动静", []))))
    if "待搜物性" in b:
        L.append("")
        L.append("  【待搜物性】搜索真实物性后填入：")
        for m in b["待搜物性"][:40]:
            L.append("    %s / %s : %s" % (m["物体"], m["部件组"], m["缺"]))
    if "生图规格" in b:
        L.append("")
        L.append("· 生图规格: " + str(b["生图规格"]))
    if "填到哪" in b:
        L.append("")
        L.append("【填到哪 / 跑什么】")
        for k, v in b["填到哪"].items():
            L.append("  %-8s %s" % (k, v))
    L.append("=" * 62)
    return "\n".join(L)


