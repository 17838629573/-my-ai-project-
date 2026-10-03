"""检查域4：源码禁硬编码物体名/survey 只问不猜/示例覆盖。

依赖: _chk_base
被依赖: solver_check
改进措施记录: IMPROVE_solver_check.md（改前必读）
"""
from _chk_base import *
from _chk_base import _r


def check(ctx=None):
    ok = True

    # 21)【铁律36】源码禁硬编码具体物体名——代码不该知道本片有什么
    # 只扫 self_check 之前的【逻辑区】，且剔除 BEGIN/END EXAMPLES 例外区
    # （自检自指误报，第 3 次遇到：framerate 正则/AST 扫描也栽过两次）
    # 扫 solver 系真实逻辑模块（子模块内 __file__ 自指会空转，第 4 次踩）
    logic = SOLVER_LOGIC
    code_lines = [l for l in logic.splitlines()
                  if not l.lstrip().startswith("#")]
    banned = ["幡旗", "垂带", "胡杨", "玄奘", "旗帜", "马匹"]
    hit = [w for w in banned if any(w in l for l in code_lines)]
    ok &= _r("源码禁硬编码物体名(铁律36)", not hit,
             "逻辑区%d行(已剔除示例区) 命中=%s" % (len(code_lines), hit))

    # 22) survey 提问不含任何物体名（代码只问，不猜）
    sv = survey()
    ok &= _r("survey 仅提问不猜物体",
             sv["填"] == [{"name": None, "kind": list(KINDS)}]
             and "本片有哪些物体" in sv["问"])

    # 23)【示例覆盖】每类必须有硬编码示例，否则别的 AI 看不懂
    miss_k = [k for k in KINDS if k not in EXAMPLES["kind"]]
    ok &= _r("示例覆盖全部大类", not miss_k,
             "%d 类，缺=%s" % (len(KINDS), miss_k))
    miss_r = [k for k in PART_ROLES if not EXAMPLES["role"].get(k)]
    ok &= _r("示例覆盖全部角色", not miss_r, "缺=%s" % miss_r)
    miss_s = [k for k in DRIVE_SOURCES if k not in EXAMPLES["source"]]
    ok &= _r("示例覆盖全部驱动源", not miss_s, "缺=%s" % miss_s)
    miss_f = [k for k in SLOT_TEMPLATE if k not in EXAMPLES["family"]]
    ok &= _r("示例覆盖全部族", not miss_f, "缺=%s" % miss_f)

    # 24) 每个大类示例必须给出动静划分 + 驱动源（心智模型才完整）
    bad = [k for k, v in EXAMPLES["kind"].items()
           if not v.get("动静") or not v.get("驱动")]
    ok &= _r("大类示例含动静+驱动", not bad, "不完整=%s" % bad)

    # 25)【填到哪】必须告诉 AI 文件/内容/命令
    need = ("填到哪个文件", "填什么", "跑什么命令", "跑完得到")
    miss_h = [k for k in need if not HOWTO.get(k)]
    ok &= _r("HOWTO 明示文件/内容/命令", not miss_h,
             "缺=%s | %s | %s"
             % (miss_h, HOWTO.get("填到哪个文件"), HOWTO.get("跑什么命令")))

    # 26) 任务包带示例时须含心智模型段，且明显长于不带示例版
    inv = inventory([{"name": "X", "kind": "静物"},
                     {"name": "Y", "kind": "人物"}])
    full = briefing_text(inv, True)
    slim = briefing_text(inv, False)
    ok &= _r("任务包含心智模型示例",
             "心智模型" in full and len(full) > len(slim) * 2,
             "带示例%d字 / 不带%d字" % (len(full), len(slim)))
    lack = [kw for kw in ("anchor", "driven", "passive",
                          "wind", "gait", "impulse") if kw not in full]
    ok &= _r("任务包含全部角色/驱动关键词", not lack, "缺=%s" % lack)

    return ok
