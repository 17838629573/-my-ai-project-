# 契约: proc/(root)/prompt2spec
#   一句话: 提示词 → 规格对照：逐字段判能做/降级/不能，STUB 带搜索提示
#   完整契约见 (root)/__init__.py
"""提示词 → 工作流 spec：逐字段能力对照。

做法：把视频提示词的六个模块拆成可数的字段，逐项问引擎"你能不能做"。
不能做的走 formula.require() 抛 STUB 并给出 search_hint —— 不静默降级、不内部编造。

业界字段口径：Veo 3 / Sora 2 JSON schema
  subject / action / camera / lens / lighting / style / context / mood / audio
业界动作能力：ADAPT（Rutgers）
  ReachFor(target) GazeAt(target) GoTo(target) Gesture(name) SitDown() StandUp()
业界道具交接：PropHandoff（pickup → held → release → recovery，ownership 切换）
"""
import json
import formula

# ============================================================ 提示词原文（咖啡馆阅读）
PROMPT = {
    "subject": {
        "age": 25, "ethnicity": "东亚", "skin": "白皙偏暖",
        "face_shape": "鹅蛋脸", "cheekbone": "轮廓柔和",
        "hair": "黑色低马尾，额前碎发",
        "eyes": "深棕色瞳孔，睫毛自然稀疏，眼周浅纹",
        "cloth_outer": "米白粗针织开衫", "cloth_inner": "浅灰圆领棉T恤",
        "cloth_lower": "深蓝直筒牛仔裤",
        "body_type": "偏瘦", "posture": "坐姿前倾", "temperament": "安静内敛",
    },
    "action_beats": [
        {"t": [0, 3], "desc": "坐高脚椅，双腿交叠，左手托下巴，右手食指敲桌面，视线在书页"},
        {"t": [3, 6], "desc": "抬头，视线移向窗外，停敲，翻一页书，嘴角上扬微笑"},
        {"t": [6, 9], "desc": "合书放桌面左侧，起身（重心右倾后站直），端起陶瓷杯，向画面左侧走"},
        {"t": [9, 12], "desc": "沙发区坐下，放杯，翻开杂志，靠背，视线落杂志，表情平静"},
    ],
    "environment": {
        "place": "室内咖啡馆", "time": "午后", "weather": None,
        "space": "狭长型，左落地窗，右书架墙",
        "props": ["高脚椅", "沙发", "矮桌", "书架", "陶瓷杯", "书", "杂志", "三幅黑白摄影"],
        "floor": "浅灰水磨石", "outside": "街道树影与缓慢走过的行人",
        "tone": "暖色调、中等饱和度、中等对比度",
        "light": "窗边高脚椅区明亮，沙发区偏暗",
    },
    "dynamics": [
        {"what": "窗外行人", "how": "正常步速从左向右，每人2-3秒经过"},
        {"what": "窗外树影", "how": "微风中轻微晃动，幅度小频率慢"},
        {"what": "咖啡杯热气", "how": "白色水汽缓慢向上飘散"},
        {"what": "书页", "how": "翻动时纸张轻微翘起后缓慢落下"},
        {"what": "书架前人影", "how": "模糊经过，不聚焦"},
        {"what": "窗光光斑", "how": "随树影轻微晃动"},
        {"what": "微表情", "how": "嘴角上扬→眼神移向窗外→恢复平静"},
    ],
    "camera": {
        "shot": "中景 MS", "angle": "平视", "position": "人物正面偏右30度",
        "motion": [{"t": [0, 6], "m": "固定"},
                   {"t": [6, 9], "m": "缓慢左摇跟拍"},
                   {"t": [9, 12], "m": "轻微推近至中近景"}],
        "speed": "轻微到中等",
    },
    "audio": {
        "ambient": ["咖啡馆低频人声", "杯碟碰撞", "咖啡机蒸汽"],
        "action": ["翻书纸张声", "杯子放下轻响"],
        "music": "轻柔钢琴独奏，音量低",
    },
}

# ============================================================ 能力对照表
# status: OK=能做 / DEGRADE=能做但降级 / STUB=不能做（走 require 抛错）
CAP = {
    # ---- 主体描述
    "subject.age":              ("DEGRADE", "只影响身高，不影响面部年龄特征", ""),
    "subject.skin":             ("OK",      "Fitzpatrick 六型", ""),
    "subject.face_shape":       ("STUB",    "头是椭圆，无脸型参数", "face shape parametric ellipse jaw cheekbone 2D"),
    "subject.cheekbone":        ("STUB",    "无颧骨几何", ""),
    "subject.hair":             ("OK",      "发纹 2 道（寥寥几笔）", ""),
    "subject.hair_strands":     ("STUB",    "低马尾/碎发需独立发束", "hair strand verlet chain low ponytail procedural"),
    "subject.eyes":             ("OK",      "眼锚点 35%/65%，可画瞳孔", ""),
    "subject.eyelash":          ("STUB",    "睫毛细节", ""),
    "subject.cloth_outer":      ("DEGRADE", "region=robe 单色，无针织纹理/开衫轮廓", "knit texture procedural 2D cardigan silhouette"),
    "subject.cloth_inner":      ("STUB",    "无内外层叠（衬衫领/下摆）", "clothing layering inner outer collar hem 2D"),
    "subject.cloth_lower":      ("STUB",    "裤腿未与腿分离", ""),
    "subject.body_type":        ("DEGRADE", "只有胶囊半径，无胖瘦档", ""),
    "subject.posture":          ("STUB",    "坐姿/前倾需 sit 动作", "ADAPT sitting choreographer state machine sit down"),
    "subject.temperament":      ("STUB",    "气质靠微表情/节奏体现", ""),
    # ---- 动作时序
    "action.walk":              ("OK",      "四相位 gait + IK，已修好", ""),
    "action.sit":               ("STUB",    "只有走路，无坐", "ADAPT SitDown StandUp choreographer procedural"),
    "action.stand_up":          ("STUB",    "无起身（重心转移）", ""),
    "action.gaze_shift":        ("STUB",    "无视线转移", "ADAPT GazeAt gaze tracking IK upper body"),
    "action.reach_grab":        ("STUB",    "无伸手取物（CCD/IK）", "ADAPT ReachFor cyclic coordinate descent damped"),
    "action.carry_prop":        ("STUB",    "无持物（杯/书）", "PropHandoff parent prop to bone ownership switch"),
    "action.prop_release":      ("STUB",    "无放下", ""),
    "action.page_flip":         ("STUB",    "无翻页（纸张形变）", ""),
    "action.legs_cross":        ("STUB",    "无交叠腿", ""),
    "action.finger_tap":        ("STUB",    "手 LOD0 是一团，无手指", ""),
    "action.expression":        ("STUB",    "无微笑/平静表情", "viseme mouth corner procedural smile"),
    "action.beat_timeline":     ("STUB",    "无多段动作时间线（0-3/3-6/6-9/9-12）", "animation state machine beat timeline DSL"),
    # ---- 背景环境
    "env.outdoor_pack":         ("OK",      "山野/城墙/城郭/沙漠/河谷", ""),
    "env.indoor_pack":          ("STUB",    "无室内包（咖啡馆/书架/窗/家具）", "procedural interior room bookshelf window furniture 2D"),
    "env.props":                ("STUB",    "无陈设元件（椅/桌/杯/书）", ""),
    "env.floor_material":       ("STUB",    "无水磨石/材质区分", ""),
    "env.time_of_day":          ("OK",      "Perez 天空，theta_s 可调", ""),
    "env.light_zones":          ("STUB",    "无分区明暗（窗边亮/沙发暗）", ""),
    "env.tone_grade":           ("DEGRADE", "有 ramp 无统一调色", ""),
    # ---- 动态元素
    "dyn.wind_plant":           ("DEGRADE", "wind.py 已实现，未接进 kit", ""),
    "dyn.steam":                ("STUB",    "无粒子（热气/水汽）", "particle system velocity acceleration drag max age procedural"),
    "dyn.pedestrian_bg":        ("DEGRADE", "有 draw_crowd 占位，未驱动", ""),
    "dyn.light_spot":           ("STUB",    "无光斑晃动", ""),
    "dyn.paper_bend":           ("STUB",    "无纸张形变", ""),
    "dyn.micro_expression":     ("STUB",    "无微表情", ""),
    # ---- 镜头运动
    "cam.static":               ("OK",      "固定相机", ""),
    "cam.pan":                  ("STUB",    "无横摇", "2D camera pan tilt dolly zoom transform formula"),
    "cam.dolly_in":             ("STUB",    "无推近", ""),
    "cam.tracking":             ("STUB",    "无跟拍", ""),
    "cam.shot_size":            ("STUB",    "无景别（中景/中近景/特写）", ""),
    "cam.angle_yaw":            ("DEGRADE", "人物 yaw 有，相机朝向无", ""),
    # ---- 声音
    "audio.ambient":            ("STUB",    "无音频", ""),
    "audio.foley":              ("STUB",    "无动作音", ""),
    "audio.music":              ("STUB",    "无配乐", ""),
}


def check(verbose=True):
    """逐字段问引擎。STUB 走 formula.require 抛错（不静默降级）。"""
    rows, stubs = [], []
    for k in sorted(CAP):
        st, note, hint = CAP[k]
        if st == "STUB":
            stubs.append((k, note, hint))
        rows.append((k, st, note))
    if verbose:
        print("=" * 74)
        print("  提示词字段 → 引擎能力对照")
        print("=" * 74)
        for k, st, note in rows:
            mark = {"OK": " ✓ ", "DEGRADE": " ~ ", "STUB": " ✗ "}[st]
            print("  %s %-26s %s" % (mark, k, note))
    return rows, stubs


def stats(rows):
    n = {"OK": 0, "DEGRADE": 0, "STUB": 0}
    for _, st, _ in rows:
        n[st] += 1
    tot = len(rows)
    print("  " + "-" * 70)
    print("  合计 %d 项：OK %d (%.0f%%)  DEGRADE %d (%.0f%%)  STUB %d (%.0f%%)"
          % (tot, n["OK"], 100.0 * n["OK"] / tot, n["DEGRADE"],
             100.0 * n["DEGRADE"] / tot, n["STUB"], 100.0 * n["STUB"] / tot))
    return n


def by_module(rows):
    print("  " + "-" * 70)
    mod = {}
    for k, st, _ in rows:
        m = k.split(".")[0]
        d = mod.setdefault(m, {"OK": 0, "DEGRADE": 0, "STUB": 0})
        d[st] += 1
    name = {"subject": "主体描述", "action": "动作时序", "env": "背景环境",
            "dyn": "动态元素", "cam": "镜头运动", "audio": "声音"}
    for m in ["subject", "action", "env", "dyn", "cam", "audio"]:
        d = mod.get(m, {"OK": 0, "DEGRADE": 0, "STUB": 0})
        t = sum(d.values())
        print("  %-8s %2d项   ✓%d  ~%d  ✗%d   (%s)"
              % (name[m], t, d["OK"], d["DEGRADE"], d["STUB"],
                 "完全能做" if d["STUB"] == 0 else
                 ("基本能做" if d["STUB"] <= 1 else "缺口大")))
    return mod


def register_stubs(stubs):
    """把缺的登记进 FORMULA_REGISTRY —— 后续按 search_hint 逐个搜，一次只搜一个。"""
    reg = json.load(open("FORMULA_REGISTRY.json"))
    g = None
    for x in reg["groups"]:
        if x["id"] == "prompt":
            g = x
    if g is None:
        g = {"id": "prompt", "name": "提示词字段→引擎能力", "items": []}
        reg["groups"].append(g)
    have = set(i["id"] for i in g["items"])
    added = 0
    for k, note, hint in stubs:
        fid = "prompt." + k.replace(".", "_")
        if fid in have:
            continue
        g["items"].append({
            "id": fid, "name": k + "：" + note, "status": "STUB", "src": "",
            "search_hint": hint, "note": "由 prompt2spec 对照视频提示词得出",
        })
        added += 1
    json.dump(reg, open("FORMULA_REGISTRY.json", "w"), ensure_ascii=False, indent=1)
    print("  登记缺公式 %d 项 → FORMULA_REGISTRY.json [group=prompt]" % added)


if __name__ == "__main__":
    rows, stubs = check()
    print()
    stats(rows)
    by_module(rows)
    print()
    print("  缺口清单（按此逐个搜，一次只搜一个）：")
    for k, note, hint in stubs:
        if hint:
            print("    %-24s %s" % (k, hint))
    print()
    register_stubs(stubs)
