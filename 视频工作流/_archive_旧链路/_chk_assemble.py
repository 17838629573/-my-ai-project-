"""检查域3：inventory/assemble/动静划分/anchor/驱动源。

依赖: _chk_base
被依赖: solver_check
改进措施记录: IMPROVE_solver_check.md（改前必读）
"""
from _chk_base import *
from _chk_base import _r

from solver_survey import assemble
from solver_survey import inventory


def check(ctx=None):
    ok = True

    # 15) inventory: 空清单必须报错（禁静默空包）
    b1 = False
    try:
        inventory([])
    except ValueError:
        b1 = True
    ok &= _r("inventory 空清单报错", b1)

    # 16) inventory: 未知大类必须报错
    b1b = False
    try:
        inventory([{"name": "A", "kind": "外星生物"}])
    except ValueError:
        b1b = True
    ok &= _r("inventory 未知大类报错", b1b)

    # 17) assemble: 未划分动静必须报错（核心：代码要逼 AI 回答）
    b1c = False
    try:
        assemble({"问卷": [{"物体": "A", "source": "wind", "parts": []}]})
    except ValueError:
        b1c = True
    ok &= _r("assemble 未分动静报错", b1c)

    # 18) 动静划分真起作用（证伪：同一物体改 role，组装结果必须变）
    def _mk(role_passive):
        return {"问卷": [{"物体": "A", "source": "wind",
                          "parts": [{"part": "杆", "role": "anchor"},
                                    {"part": "主体", "role": "driven"},
                                    {"part": "末端", "role": role_passive}]}]}
    as_passive = assemble(_mk("passive"))
    as_anchor = assemble(_mk("anchor"))
    ok &= _r("动静划分驱动组装结果",
             as_passive["组装"][0]["family"] == "chain"
             and as_anchor["组装"][0]["family"] == "cantilever",
             "末端=passive→%s / 末端=anchor→%s"
             % (as_passive["组装"][0]["family"], as_anchor["组装"][0]["family"]))

    # 19) anchor 不进动力学链（恒不动）
    chain_names = [c["part"] for c in as_passive["组装"][0]["链"]]
    ok &= _r("anchor 不进链(恒不动)", "杆" not in chain_names,
             "链=%s  锚点=%s" % (chain_names, as_passive["组装"][0]["锚点(恒不动)"]))

    # 20) 驱动源非法必须报错
    b1d = False
    try:
        assemble({"问卷": [{"物体": "A", "source": "魔法",
                            "parts": [{"part": "p", "role": "driven"}]}]})
    except ValueError:
        b1d = True
    ok &= _r("assemble 非法驱动源报错", b1d)

    return ok
