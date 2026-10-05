#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""prompt_tpl —— 按族抽象的生图提示词模板（铁律81-85）

程序负责: 族白名单校验 / 模板渲染 / 必填槽校验 / 输出避免项与验收标准
AI 负责:   判族 / 填物性与构图参数 / 按渲染出的提示词生图

业界依据: 类别对应 tpl-{name} 结构化约束块（awesome-gpt-image-2）；
          提示词以资产角色开头、固定顺序收尾于避免项与验收（Orias taxonomy）；
          资产白名单防 LLM 幻觉（UE5 PCG）。

依赖: 无（纯模板，禁 import 业务模块以免成环）
被依赖: driver, build_video
改前必读: IMPROVE_prompt_tpl.md
"""
from __future__ import annotations

import ast

# ---- 示例区（铁律37/82：示例必须硬编码，供其他 AI 建立心智模型）----
# BEGIN EXAMPLES
EXAMPLES = [
    ("biped",      "人物：躯干+四肢，足端轨迹由 pose 算，走循环 in-place"),
    ("quadruped",  "马、骆驼、犬：四足，四腿相位交错，非两条腿镜像"),
    ("vegetation", "旱柳、胡杨：无骨骼，单图 + 顶点风摆，树梢摆幅最大"),
    ("rigid",      "马车：刚体，车轮自转，注册点在轮胎接地面中点"),
    ("cloth",      "幡旗：受迫链，帧数 = 周期 × FPS"),
]
# END EXAMPLES

# ---- 模板区（铁律82：禁出现任何具体物体名）----
# 段序遵循业界 prompt order：角色 → 用途 → 构图 → 姿态 → 风格 → 格式 → 避免 → 验收
TPL = {
    "biped": {
        "必填": ["身高m", "帧数", "网格", "构图占比", "关节坐标", "风格", "背板色"],
        "段": {
            "角色": "侧面行走循环序列帧素材（in-place，原地走，不做位移）",
            "用途": "序列帧动画源，供代码按帧切分后循环播放",
            "构图": "相机固定不变；单物体居中，占格高 {构图占比}；"
                    "脚接触线贴格底；主体完整不出格",
            "姿态": "严格按下述关节坐标摆放（原点=双脚地面中点，单位米，逐帧不同）：{关节坐标}",
            "风格": "{风格}",
            "格式": "{帧数} 帧排成 {网格} 网格；每格等大；纯色背板 {背板色}；"
                    "格间留净边距，禁画格线",
            "避免": "禁出现骨架线、火柴人、标注文字、箭头、坐标数字；"
                    "禁渐变或实景背景；禁跨帧改变服饰配色与体型",
            "验收": "跨格形态差异低于阈值；脚接触线位置逐格一致；"
                    "身高换算 {身高m}m 与整体比例自洽",
        },
    },
    "quadruped": {
        "必填": ["体长m", "肩高m", "帧数", "网格", "构图占比", "腿相位", "风格", "背板色"],
        "段": {
            "角色": "侧面四足行进循环序列帧素材（in-place）",
            "用途": "序列帧动画源，供代码切分循环",
            "构图": "相机固定；单物体居中，占格宽 {构图占比}；"
                    "蹄接触线贴格底；主体完整不出格",
            "姿态": "四条腿按下述相位交错（非两条腿镜像）：{腿相位}；"
                    "脊柱随步态起伏，躯干非刚体",
            "风格": "{风格}",
            "格式": "{帧数} 帧排成 {网格} 网格；每格等大；纯色背板 {背板色}；禁画格线",
            "避免": "禁把四条腿画成左右对称；禁骨架线；禁跨帧改变毛色与体型",
            "验收": "四条腿相位互不相同；体长 {体长m}m 与肩高 {肩高m}m 比例自洽",
        },
    },
    "vegetation": {
        "必填": ["树高m", "冠幅m", "构图占比", "风格", "背板色"],
        "段": {
            "角色": "单张静态植株素材（无骨骼，不生成序列帧）",
            "用途": "供代码做顶点位移风摆：树根锁定不动，树梢摆幅最大",
            "构图": "单株完整居中；树干与地面垂直（倾斜留给代码算）；"
                    "树冠占画面 {构图占比}",
            "姿态": "静止直立姿态，不带任何摆动倾向",
            "风格": "{风格}",
            "格式": "单张图；纯色背板 {背板色}；无格线",
            "避免": "禁生成序列帧（无骨骼物体禁骨架）；"
                    "禁预先画出弯曲或倾斜（由代码算）；禁骨架线",
            "验收": "树干垂直；树高 {树高m}m、冠幅 {冠幅m}m 比例自洽；只交付一张图",
        },
    },
    "rigid": {
        # 抽象为"通用刚体"：车辆、杆件、器物皆属此族，不再硬编码成"车"
        "必填": ["长m", "注册点", "风格", "背板色"],
        "可选": ["轮径m"],  # 仅带轮载具填，杆件/器物不填
        "段": {
            "角色": "单张静态刚体素材（无骨骼，不生成序列帧）",
            "用途": "位移与自转由代码算，图只提供静止外观",
            "构图": "单物体居中；注册点 {注册点} 明确可定位；主体按注册点摆放",
            "姿态": "静止姿态，不预画运动模糊或旋转模糊",
            "风格": "{风格}",
            "格式": "单张图；纯色背板 {背板色}；无格线",
            "避免": "禁生成序列帧；禁画运动模糊或速度线；禁骨架线",
            "验收": "注册点落在声明位置；长度 {长m}m 比例自洽",
        },
    },
    "cloth": {
        "必填": ["长m", "宽m", "帧数", "网格", "固定边", "物理点", "风格", "背板色"],
        "段": {
            "角色": "受迫摆动循环序列帧素材",
            "用途": "序列帧动画源，帧数由物理周期算出",
            "构图": "相机固定；固定边 {固定边} 位置逐帧不动；主体完整不出格",
            "姿态": "逐帧形态由代码给出的物理点决定，按下述序列摆放：{物理点}",
            "风格": "{风格}",
            "格式": "{帧数} 帧排成 {网格} 网格；每格等大；纯色背板 {背板色}；禁画格线",
            "避免": "禁骨架线；禁跨帧改变材质纹理与配色；"
                    "禁自行改变帧数（帧数由周期算出）",
            "验收": "固定边逐帧不动；摆幅随相位单调变化，无忽大忽小；"
                    "{长m}m × {宽m}m 比例自洽",
        },
    },
}

# 通用后缀：生图纪律（由代码强制附加，AI 不可删）
DISCIPLINE = (
    "【生图纪律·代码强制】\n"
    "1. 一次只生成【一个物体】的【一类图】，禁把多个物体的描述混在同一批。\n"
    "2. 本批未通过验收前，禁止开始下一批。\n"
    "3. 骨架图/控制图【永不进画面】——它只是计算中间量。"
)

# 扫描用词表（与 driver.HARDCODE_BAN 保持一致）
HARDCODE_BAN = ["玄奘", "石槃陀", "慧琳", "幡旗", "城头旗", "胡杨",
                "旱柳", "马车", "城墙", "骆驼"]


class PromptTplError(ValueError):
    pass


# 族 -> 主尺度槽名（AI 只给 real_m，代码按族落到对应槽）
# 禁在调用方写死 "real_m"，各族槽名不同，写死会静默丢弃（genqueue 已能拦）
SCALE_SLOT = {
    "biped":      ["身高m"],
    "quadruped":  ["体长m", "肩高m"],
    "vegetation": ["树高m", "冠幅m"],
    "rigid":      ["长m"],
    "cloth":      ["长m", "宽m"],
}


def scale_slots(family: str):
    """族的主尺度槽名。未知族报错（禁静默降级，铁律31）。"""
    if family not in SCALE_SLOT:
        raise PromptTplError(
            "未知族 %r，禁猜。已登记：%s" % (family, list(SCALE_SLOT)))
    return list(SCALE_SLOT[family])


def families():
    return sorted(TPL)


def _require(family, params):
    need = TPL[family]["必填"]
    miss = [k for k in need if k not in params or params[k] in (None, "")]
    if miss:
        raise PromptTplError(f"族 {family} 缺必填参数 {miss} —— 禁静默留空（铁律31）")


def build(family, params):
    """按族渲染提示词。未知族报错（铁律84），缺槽报错（铁律31）。"""
    if family not in TPL:
        raise PromptTplError(
            f"族 '{family}' 未登记，可选: {families()} —— 禁静默套用相近族（铁律84）")
    p = dict(params)
    # 【已修】setdefault 原在 _require 之后 —— 默认永远救不了缺槽，形同虚设。
    # 默认必须在校验之前生效。
    p.setdefault("构图占比", "70%")
    _require(family, p)
    seg = TPL[family]["段"]
    order = ["角色", "用途", "构图", "姿态", "风格", "格式", "避免", "验收"]
    lines = [f"[资产角色] {seg['角色']}"]
    for k in order[1:]:
        if k in seg:
            try:
                lines.append(f"[{k}] {seg[k].format(**p)}")
            except KeyError as e:
                raise PromptTplError(f"模板占位符 {e} 无对应参数") from e
    text = "\n".join(lines) + "\n\n" + DISCIPLINE
    return {
        "族": family,
        "提示词": text,
        "验收": seg["验收"].format(**p),
        "避免": seg["避免"],
        "未填": [],
    }


def structural_pose(family, solved):
    """把代码算出的量转成结构性姿态文本（铁律83：禁模糊词）。"""
    if family not in TPL:
        raise PromptTplError(f"未登记族 '{family}'")
    if not isinstance(solved, dict) or not solved:
        raise PromptTplError("缺 solved 量：姿态必须来自代码计算，禁凭印象描述")
    if family == "biped":
        # 【铁律113】优先用 _joint_seq 的逐帧序列：已减身体位移（局部坐标，
        # 首尾闭合可循环）且逐帧给出足端支撑/摆动语义。
        # 旧路径只给 t=0 单帧世界坐标 → 循环时足端从 1.5m 硬跳回 0，
        # 观感即"只走出半步/动作断裂"。旧路径仅作无序列时的报错兜底。
        seq = solved.get("关节坐标")
        if seq:
            return ("逐帧关节坐标(米；原点=人体中心，已减身体位移，"
                    "首尾闭合可循环)：\n" + str(seq))
        raise PromptTplError(
            "biped 缺逐帧关节坐标序列：单帧世界坐标会导致循环跳变，"
            "必须传 _joint_seq(...) 的输出")
    if family == "quadruped":
        legs = solved.get("腿相位") or solved.get("legs")
        if not legs:
            raise PromptTplError("quadruped 缺四腿相位")
        return "四腿相位：" + str(legs)
    if family == "cloth":
        pts = solved.get("物理点") or solved.get("points")
        if not pts:
            raise PromptTplError("cloth 缺物理点序列")
        return "物理点序列：" + str(pts)
    # 无骨骼族不需要姿态量
    return f"{family} 无骨骼，不需要序列姿态（禁生成序列帧）"


# ---------------- 自检 ----------------
def _chk(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ((" " + info) if info else ""))
    return bool(ok)


def _scan(text):
    """硬编码扫描核心。单独抽出来，便于证伪其有效性。"""
    return [w for w in HARDCODE_BAN if w in text]


def _scan_targets():
    """AST 取「模板区 + 逻辑区」真实源码。

    不能用 split 标记法：扫描函数自己的代码里含标记字面量，会被误当第二个
    标记，导致只扫到空壳（实测只扫到 497 字符，模板区完全漏掉）。
    """
    src = open(__file__, encoding="utf-8").read()
    tree = ast.parse(src)
    parts = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if "TPL" in names:
                parts.append(ast.get_source_segment(src, node) or "")
        elif isinstance(node, ast.FunctionDef):
            if node.name in ("_logic_src", "self_check", "_scan_targets",
                             "_scan"):
                continue
            parts.append(ast.get_source_segment(src, node) or "")
    return "\n".join(parts)


def self_check():
    ok = []
    # 1 五族模板齐全
    ok.append(_chk("五族模板齐全", len(families()) == 5, str(families())))

    # 2 逻辑区零具体物体名（示例区豁免）
    hits = _scan(_scan_targets())
    ok.append(_chk("逻辑区无物体名(真实扫描)", not hits, str(hits)))

    # 2b 扫描目标必须真的覆盖模板区，否则第2项是空转的假PASS
    tgt = _scan_targets()
    ok.append(_chk("扫描目标覆盖模板区",
                   "vegetation" in tgt and len(tgt) > 3000, f"len={len(tgt)}"))

    # 3 未知族报错（防 PCG 式幻觉）
    try:
        build("bird", {"身高m": 1})
        ok.append(_chk("未知族报错", False, "竟通过=会静默套用"))
    except PromptTplError as e:
        ok.append(_chk("未知族报错", "未登记" in str(e)))

    # 4 缺必填槽报错
    try:
        build("biped", {"身高m": 1.7})
        ok.append(_chk("缺槽报错", False))
    except PromptTplError as e:
        ok.append(_chk("缺槽报错", "缺必填" in str(e)))

    # 5 biped 模板含结构性姿态占位符，而非模糊词
    seg = TPL["biped"]["段"]
    ok.append(_chk("biped姿态为结构量",
                   "{关节坐标}" in seg["姿态"] and "迈步" not in seg["姿态"]))

    # 6 每族必含避免项与验收（铁律85）
    ok.append(_chk("每族含避免+验收",
                   all("避免" in TPL[f]["段"] and "验收" in TPL[f]["段"]
                       for f in families())))

    # 7 示例区豁免生效（示例里含物体名不算违规）
    ex = open(__file__, encoding="utf-8").read().split("# BEGIN EXAMPLES")[1]
    ok.append(_chk("示例区豁免生效",
                   any(w in ex for w in HARDCODE_BAN)))

    # 8 渲染成功且无残留占位符
    r = build("biped", {"身高m": 1.70, "帧数": 30, "网格": "6×5",
                        "构图占比": "70%", "关节坐标": "踝(-0.15,0.07),膝(0.07,0.42)", "风格": "唐代写实",
                        "背板色": "#FF00FF"})
    ok.append(_chk("渲染无残留占位", "{" not in r["提示词"], r["提示词"][:40]))

    # 9 生图纪律被强制附加（防提示词混用）
    ok.append(_chk("含生图纪律", "一次只生成" in r["提示词"]))

    # 10 证伪：扫描器本身必须有效，否则上面全是空转
    h = _scan("玄奘持幡旗立于城墙")
    ok.append(_chk("证伪:扫描器有效", len(h) >= 3, str(h)))
    ok.append(_chk("证伪:真目标区仍干净", not _scan(_scan_targets())))

    # 11 structural_pose 拒绝空量（防退回模糊词）
    try:
        structural_pose("biped", {})
        ok.append(_chk("缺算量即报错", False))
    except PromptTplError:
        ok.append(_chk("缺算量即报错", True))

    print(f"\n自检 {sum(ok)}/{len(ok)} 项 PASS")
    return all(ok)


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
