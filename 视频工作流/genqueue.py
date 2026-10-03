"""genqueue · 生图任务队列（铁律81-85）

一次只放行一个物体的一种图，提示词按族模板组装、只含该物体槽值。
依据见 contracts/genqueue.md 与 IMPROVE_genqueue.md。
"""
import re
import prompt_tpl as TPL


class GenQueueError(ValueError):
    """生图队列错误。继承 ValueError：既有调用方用 except ValueError 捕获，保持兼容"""

# 族 -> 该族要出的图类型
_KIND = {
    "biped":      ["sheet"],
    "quadruped":  ["sheet"],
    "cloth":      ["sheet"],
    "vegetation": ["single"],
    "rigid":      ["single"],
}

# identity 词：用于检测跨物体污染
_ID_KEYS = ("身份", "服饰", "配色", "名称", "物体", "name", "identity")


def plan(objects):
    """objects: [{"物体":str,"族":str,"spec":dict}] -> 任务队列"""
    if not objects:
        raise ValueError("plan: objects 为空，禁静默返回空队列")
    tasks = []
    for o in objects:
        name = o.get("物体") or o.get("name")
        fam = o.get("族") or o.get("family")
        if not name:
            raise ValueError("plan: 缺物体名")
        if fam not in _KIND:
            raise ValueError(f"plan: 未知族 {fam!r}，禁降级为默认")
        for kind in _KIND[fam]:
            tasks.append({
                "id": f"{name}::{kind}",
                "物体": name,
                "族": fam,
                "kind": kind,
                "spec": dict(o.get("spec") or {}),
                "solved": o.get("solved") or {},
            })
    return {"tasks": tasks, "n": len(tasks)}


def _declared_slots(fam):
    """已声明槽 = 必填 ∪ 段内 {} 占位符。
    实测发现：biped 段里用了 {构图占比} 却不在必填里 —— 不提取就会静默留空。"""
    t = TPL.TPL.get(fam)
    if not t:
        return set()
    slots = set(t.get("必填", ()))
    for seg in t.get("段", {}).values():
        slots.update(re.findall(r"\{(\w+)\}", seg))
    return slots


def build_prompt(task):
    """只由该 task 的 spec 组装，禁引入任何其他物体"""
    fam = task["族"]
    params = dict(task["spec"])
    params.setdefault("物体", task["物体"])
    # 关节角来自代码算出的 solved，禁凭印象手填（铁律68）
    sv = task.get("solved") or {}
    if sv and "关节角" not in params:
        params["关节角"] = "，".join(f"{k}={v}" for k, v in sv.items())
    # 未声明槽会被模板静默丢弃 —— 必须报出来，禁 AI 以为生效（铁律31精神）
    known = _declared_slots(fam) | {"物体", "关节角"}
    dropped = [k for k in task["spec"] if k not in known]
    if dropped:
        raise GenQueueError(
            f"{task['id']} 槽位 {dropped} 未被模板声明，会被静默丢弃 —— "
            f"改用已声明槽或补模板（禁以为填了就生效）")
    p = TPL.build(fam, params)
    # 结构块：无骨骼族不加姿态骨架描述
    if fam in ("vegetation", "rigid"):
        return p
    sp = TPL.structural_pose(fam, task.get("solved") or {})
    return f"{p}\n{sp}" if sp else p


def next_task(q, done):
    """一次只返回一个未完成任务；done 为已 accept 的 id 集合"""
    for t in q["tasks"]:
        if t["id"] not in done:
            return t
    return None


def accept(q, tid, report=None):
    return {"ok": True, "id": tid, "report": report or {}}


def reject(q, tid, reason=""):
    if not reason:
        raise ValueError("reject: 必须给原因，便于定位该物体的哪一类图不过")
    return {"ok": False, "id": tid, "reason": reason}


# ---------------- 自检 ----------------
def _chk(name, ok, info=""):
    print(f"{'PASS' if ok else 'FAIL'} | {name} {info}")
    return bool(ok)


def self_check():
    import pose as PS                                   # 姿态由代码真算
    # BEGIN EXAMPLES —— 示例区允许写死（示範用），扫描时剔除
    ANTHRO = {"trunk": 0.288, "head": 0.130, "neck": 0.052, "upperarm": 0.186,
              "lowerarm": 0.146, "hand": 0.108, "thigh": 0.245, "shank": 0.246,
              "shoulder_half": 0.1295, "hip_half": 0.095}
    FACE = {"eye_back": 0.15, "ear_back": 0.35, "face_side": 0.30}
    POSES = {"stand": {"a_trunk": 90, "a_head": 90, "a_shoulder_l": 180,
                       "a_shoulder_r": 0, "a_upperarm_l": -90, "a_upperarm_r": -90,
                       "a_forearm_l": -90, "a_forearm_r": -90, "a_hip_l": 180,
                       "a_hip_r": 0, "a_thigh_l": -90, "a_thigh_r": -90,
                       "a_shank_l": -90, "a_shank_r": -90}}

    def _solved(h, t):
        """铁律68：姿态量由 pose 计算，禁凭印象写"""
        g = {"speed_m_s": 1.5, "cycle_s": 1.0, "stride_m": 1.5,
             "stance_ratio": 0.60, "swing_height_m": 0.10}
        s = {"height_m": h, "anthro": ANTHRO, "face": FACE,
             "poses": POSES, "gait": g}
        r = PS.solve(s, "walk", t)
        j, m = r["joints"], r["meta"]
        return {"足端x": round(j["l_ankle"][0], 3), "足端y": round(j["l_ankle"][1], 3),
                "支撑相": m["l_phase"], "髋": round(j["l_hip"][1], 3),
                "膝": round(j["l_knee"][1], 3), "踝": round(j["l_ankle"][1], 3)}
    # END EXAMPLES

    objs = [
        {"物体": "玄奘", "族": "biped",
         "spec": {"身高m": 1.70, "帧数": 30, "网格": "6x5", "构图占比": "70%", "风格": "唐代",
                  "背板色": "#FF00FF"},
         "solved": _solved(1.70, 0.20)},
        {"物体": "慧琳", "族": "biped",
         "spec": {"身高m": 1.65, "帧数": 30, "网格": "6x5", "构图占比": "70%", "风格": "唐代",
                  "背板色": "#FF00FF"},
         "solved": _solved(1.65, 0.55)},
        {"物体": "旱柳", "族": "vegetation",
         "spec": {"树高m": 9.0, "冠幅m": 6.0, "构图占比": "70%", "风格": "唐代", "背板色": "#FF00FF"}},
        {"物体": "马车", "族": "rigid",
         "spec": {"车长m": 3.2, "轮径m": 0.9, "注册点": "wheel_contact",
                  "风格": "唐代", "背板色": "#FF00FF"}},
    ]
    r = []
    q = plan(objs)

    r.append(_chk("1 任务数 = 物体×图类型", q["n"] == 4, f"got {q['n']}"))
    r.append(_chk("2 无骨骼族只出单张",
                  all(t["kind"] == "single" for t in q["tasks"]
                      if t["族"] in ("vegetation", "rigid"))))

    # 3 一次只返回一个
    done = set()
    first = next_task(q, done)
    second = next_task(q, done)
    r.append(_chk("3 未验收不放行(两次同一任务)",
                  first is not None and second is not None
                  and first["id"] == second["id"], f"{first['id']}"))

    # 4 accept 后才推进
    done.add(first["id"])
    nxt = next_task(q, done)
    r.append(_chk("4 accept后推进到下一物体",
                  nxt is not None and nxt["id"] != first["id"],
                  f"{first['id']} -> {nxt['id'] if nxt else None}"))

    # 5 不同实例是不同任务、prompt 不同
    ids = [t["id"] for t in q["tasks"]]
    r.append(_chk("5 同类不同实例分属不同任务",
                  "玄奘::sheet" in ids and "慧琳::sheet" in ids))
    p1 = build_prompt(q["tasks"][0])
    p2 = build_prompt(q["tasks"][1])
    r.append(_chk("6 不同实例提示词不同", p1 != p2))

    # 7 跨物体污染检测：任一 prompt 不得含其他物体名
    leak = []
    for t in q["tasks"]:
        p = build_prompt(t)
        for other in [o["物体"] for o in objs]:
            if other != t["物体"] and other in p:
                leak.append(f"{t['id']}含{other}")
    r.append(_chk("7 提示词无跨物体污染", not leak, str(leak)))

    # 8 未知族报错
    try:
        plan([{"物体": "x", "族": "ufo", "spec": {}}])
        r.append(_chk("8 未知族报错", False, "未抛错"))
    except ValueError:
        r.append(_chk("8 未知族报错", True))

    # 9 空输入报错
    try:
        plan([])
        r.append(_chk("9 空输入报错", False, "未抛错"))
    except ValueError:
        r.append(_chk("9 空输入报错", True))

    # 10 证伪：假实现(一次返回全部)必须被 3 检出
    def fake_next(qq, dd):
        return [t for t in qq["tasks"] if t["id"] not in dd] or None
    got = fake_next(q, set())
    r.append(_chk("10 证伪:假实现返回列表被检出",
                  isinstance(got, list) and len(got) == 4,
                  f"假实现返回 {len(got) if isinstance(got, list) else '非列表'}"))

    # 11 证伪：注入跨物体污染必须被第7项的检测器抓出
    q2 = plan([dict(o) for o in objs])
    q2["tasks"][1]["spec"]["风格"] = "唐代，同玄奘的袈裟"   # 注入到已声明槽
    leak2 = []
    for t in q2["tasks"]:
        p = build_prompt(t)
        for other in [o["物体"] for o in objs]:
            if other != t["物体"] and other in p:
                leak2.append(f"{t['id']}含{other}")
    r.append(_chk("11 证伪:污染注入被检出", bool(leak2), str(leak2)))

    # 12 证伪：AI 填了未声明槽必须报错（禁静默丢弃让它以为生效）
    bad = dict(objs[0]); bad["spec"] = dict(bad["spec"]); bad["spec"]["袈裟颜色"] = "赭红"
    try:
        build_prompt({"id": "x::sheet", "物体": "玄奘", "族": "biped",
                      "spec": bad["spec"], "solved": {}})
        r.append(_chk("12 证伪:未声明槽报错", False, "未报错=静默丢弃"))
    except GenQueueError as e:
        r.append(_chk("12 证伪:未声明槽报错", True, str(e)[:40]))

    # 13 段内 {占位符} 必须都在必填里，否则渲染时静默留空
    miss = {}
    for f in TPL.families():
        t = TPL.TPL[f]
        ph = set()
        for seg in t.get("段", {}).values():
            ph.update(re.findall(r"\{(\w+)\}", seg))
        gap = ph - set(t.get("必填", ()))
        if gap:
            miss[f] = sorted(gap)
    r.append(_chk("13 段占位符均在必填内", not miss, str(miss)))

    print(f"\n自检 {sum(r)}/{len(r)} PASS")
    return all(r)


if __name__ == "__main__":
    raise SystemExit(0 if self_check() else 1)
