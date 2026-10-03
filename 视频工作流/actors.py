"""
actors.py —— 可动者登记 + 动作能力白名单 + 硬报错

【铁律·资产分类唯一判据】
  分类按"能不能动"，不按"是不是人"。
    能动：人 / 动物 / 植物 / 门 / 旗 / 水 / 火  → actor，必须能被代码驱动
    动不了：城池 / 房屋 / 地形 / 远山          → 背景，静态整图
  驱动不了 → 硬报错并停机。禁止降级、禁止色块占位。

【背景图铁律】
  背景图里只允许烘焙"动不了"的东西。
  树、旗、门、水这类可动件必须单独成层，否则代码无法驱动它。

【三态刚体】（Unity 官方，非简单两分）
  static    不受力，无限质量，不动        → 城池/地形/房屋
  kinematic 不受力，但由代码显式驱动      → 走路的主角、推开的门
  dynamic   受质量/重力/力，物理求解      → 旗、叶、衣摆、可推倒物
物性只填 M / rho / kind / Cd / B_vogel / body_type；
迎风面积由 physics.area() 算，禁止手填（铁律11：逻辑唯一）。
"""
import os

BASE = os.path.dirname(os.path.abspath(__file__))
CHAR_DIR = os.path.join(BASE, "assets_tang", "char")
BG_DIR = os.path.join(BASE, "assets_tang", "bg")

__all__ = ["ACTORS", "CAPABILITY", "BG_STATIC", "check_shot",
           "missing_actor_assets", "require"]

# ------------------------------------------------------------------ 可动者
# kind: human / animal / plant / object / cloth / fluid
# role: protagonist 主角 / supporting 配角 / movable 可动件
ACTORS = {
    "xz":          dict(cn="玄奘",     kind="human",  role="protagonist",
                        file="xz_stand.jpg", body_type="kinematic",
                        mass=62.0, cd=1.0),
    "li_daliang":  dict(cn="李大亮",   kind="human",  role="supporting",
                        file="li_daliang.png", body_type="kinematic",
                        mass=72.0, cd=1.0),
    "li_chang":    dict(cn="李昌",     kind="human",  role="supporting",
                        file="li_chang.png", body_type="kinematic",
                        mass=65.0, cd=1.0),
    "shi_pantuo":  dict(cn="石槃陀",   kind="human",  role="supporting",
                        file="shi_pantuo.png", body_type="kinematic",
                        mass=78.0, cd=1.0),
    "old_man":     dict(cn="老翁",     kind="human",  role="supporting",
                        file="old_man.png", body_type="kinematic",
                        mass=55.0, cd=1.0),
    "horse":       dict(cn="瘦老赤马", kind="animal", role="supporting",
                        file="prop_horse.png", body_type="kinematic",
                        mass=320.0, cd=1.0),
    # 可动件（非生命，但会动 → 一律 actor，不进背景图）
    # 【修正】mass 曾手填 1.0kg，实测应为 0.0257kg（面密度95g/m² × 0.9×0.3m）
    # 差 39 倍 —— 手填数值的典型翻车，改由物性表推导
    "banner":      dict(cn="幡旗",     kind="cloth",  role="movable",
                        file="banner.png", body_type="dynamic",
                        mass=0.0257, cd=1.2, b_vogel=-0.5,
                        length=0.90, height=0.30, areal_density=0.095,
                        bending_stiffness=0.30, loop_period=0.366),
    "tree":        dict(cn="树",       kind="tree",   role="movable",
                        file=None, body_type="dynamic",
                        mass=200.0, cd=0.8, b_vogel=-0.71),
    "door":        dict(cn="城门",     kind="object", role="movable",
                        file=None, body_type="kinematic",
                        mass=800.0, cd=1.05),
    "water":       dict(cn="水面",     kind="fluid",  role="movable",
                        file=None, body_type="dynamic",
                        mass=1000.0, cd=1.0),
}

# ------------------------------------------------------- 动作能力白名单
# impl=None 表示代码当前驱动不了 → 硬性停机，不降级
CAPABILITY = {
    "stand": dict(cn="静立", impl="静态贴图", kinds=["human", "animal"]),
    "walk":  dict(cn="行走", impl="骨骼8帧+锁相",
                  kinds=["human", "animal"]),
    "kneel": dict(cn="跪",   impl="静态贴图", kinds=["human"]),
    "idle":  dict(cn="待机微动", impl="相位错开+idle break",
                  kinds=["human", "animal"]),
    # 【新增】flutter: 序列帧循环播放。周期由 St=f·L/U 推出，非手填。
    # 依铁律16：dynamic actor 必须有 <name>_fNN.png 循环序列
    "flutter": dict(cn="飘动", impl="序列帧循环(周期由St推出)",
                    kinds=["cloth", "plant", "fluid"]),
    "sway":  dict(cn="摆动", impl="Verlet+空气动力",
                  kinds=["plant", "cloth"]),
    "open":  dict(cn="推开", impl=None, kinds=["object"]),
    "flow":  dict(cn="流动", impl=None, kinds=["fluid"]),
    "tear":  dict(cn="撕纸", impl=None, kinds=["human"]),
    "grow":  dict(cn="生长", impl=None, kinds=["plant"]),
}

# ------------------------------------------------------------ 静态背景
# 只允许"动不了"的东西。可动件禁止烘焙进背景图。
BG_STATIC = {
    "gate":   "城门洞·城墙",
    "hall":   "讲经堂 interior",
    "office": "都督府 interior",
    "yamen":  "州衙 interior",
    "river":  "河道地形",
    "desert": "沙漠地形·沙丘",
    "oasis":  "绿洲地形",
    "yiwu":   "边境地形",
}


def require(action, actor):
    """单个 (actor, action) 能否被供给。返回 None 或错误串。"""
    a = ACTORS.get(actor)
    if a is None:
        return "未登记 actor「%s」（先写进 ACTORS）" % actor
    c = CAPABILITY.get(action)
    if c is None:
        return "未登记动作「%s」（先写进 CAPABILITY）" % action
    if a["kind"] not in c["kinds"]:
        return "%s(%s) 不能做 %s（该动作只支持 %s）" % (
            a["cn"], a["kind"], c["cn"], "/".join(c["kinds"]))
    if c["impl"] is None:
        return ("HALT: %s 需要 %s 做「%s」，代码当前无此能力\n"
                "        → ① 补该动作实现 ② 改叙事。禁止降级/占位"
                % (a["cn"], a["cn"], c["cn"]))
    return None


def check_shot(name, decl):
    """
    decl: [(actor, action), ...]
    分镜声明了就必须要能驱动，驱动不了就硬报错。
    """
    errs = []
    for actor, action in decl:
        e = require(action, actor)
        if e:
            errs.append("[%s] %s" % (name, e))
        f = ACTORS[actor].get("file")
        if f and not os.path.exists(os.path.join(CHAR_DIR, f)):
            errs.append("[%s] %s 资产文件缺失: %s" % (name, actor, f))
    return errs


BODY_TYPES = ("static", "kinematic", "dynamic")


def check_body_type():
    """每个 actor 必须声明合法 body_type"""
    errs = []
    for k, v in ACTORS.items():
        bt = v.get("body_type")
        if bt not in BODY_TYPES:
            errs.append("%s(%s) body_type=%r 非法，须为 %s"
                        % (v["cn"], k, bt, "/".join(BODY_TYPES)))
        elif bt == "dynamic" and not v.get("mass"):
            errs.append("%s 是 dynamic 但缺 mass，无法算 a=F/m" % v["cn"])
    return errs


def wind_response(name, v):
    """该 actor 在风速 v 下的响应（面积/受力/加速度/风级）"""
    import physics as pr            # 铁律11：物理原子层唯一实现
    a = ACTORS[name]
    if a["body_type"] == "static":
        return "%s 是 static，不受风" % a["cn"]
    A = pr.area(a["mass"], a["kind"])
    F = pr.force(v, A, a.get("cd", 1.0), b=a.get("b_vogel", 0.0))
    acc = pr.accel(F, a["mass"])
    bft, desc = pr.beaufort_level(v)
    return (f"{a['cn']:<6} A={A:<7.3f} F={F:<8.2f}N "
            f"a={acc:<7.3f}m/s² {bft}级 {desc[:10]}")


def missing_actor_assets():
    """actor 资产缺口（可动件 file=None 视为待生成）"""
    out = []
    for k, v in ACTORS.items():
        f = v.get("file")
        if not f:
            out.append((k, v["cn"], "待生成"))
        elif not os.path.exists(os.path.join(CHAR_DIR, f)):
            out.append((k, v["cn"], f))
    return out


if __name__ == "__main__":
    print("=== actors 自检 ===")
    print("1 辩经场景（听众 idle）")
    e = check_shot("02_hall", [("li_daliang", "idle"), ("xz", "stand")])
    print("   ", e or "PASS")
    print("2 撕文牒（tear 无实现）")
    e = check_shot("04_yamen", [("li_chang", "tear")])
    print("   ", e[0] if e else "!! 应报错却通过了")
    print("3 树摆动（sway 有实现）")
    e = require("sway", "banner")
    print("   ", e or "PASS")
    print("4 未登记 actor")
    print("   ", require("walk", "nobody"))
    print("5 资产缺口:", len(missing_actor_assets()), "项")
    print("6 三态合法性:", check_body_type() or "PASS")
    print("7 风响应(10m/s):")
    for n in ("xz", "horse", "banner", "tree"):
        print("     ", wind_response(n, 10.0))
