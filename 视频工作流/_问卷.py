# -*- coding: utf-8 -*-
"""AI 填问卷：只做动静划分 + 驱动源判断。物性槽位留空，由代码告诉我要搜什么。"""
import json, solver

# --- AI 盘点：本片有哪些物体 ---
ACTORS = [
    {"name": "城头旗", "kind": "静物"},
    {"name": "行人A", "kind": "人物"},
    {"name": "行人B", "kind": "人物"},
    {"name": "行人C", "kind": "人物"},
    {"name": "行人D", "kind": "人物"},
    {"name": "城墙",  "kind": "静物"},
]

# --- AI 答问卷：每个物体上哪些部件动、哪些静 ---
# 只回答结构与驱动源，物性(geometry/material/fluid/criteria)一律留空
ANSWER = {"问卷": [
    {"物体": "城头旗", "source": "wind",
     "parts": [{"part": "旗杆", "role": "anchor"},
               {"part": "旗面", "role": "driven"},
               {"part": "旗缘垂带", "role": "passive"}]},

    {"物体": "行人A", "source": "gait",
     "parts": [{"part": "足", "role": "anchor"},
               {"part": "躯干", "role": "driven"},
               {"part": "发髻发丝", "role": "passive"},
               {"part": "衣摆袍角", "role": "passive"}]},

    {"物体": "行人B", "source": "gait",
     "parts": [{"part": "足", "role": "anchor"},
               {"part": "躯干", "role": "driven"},
               {"part": "发髻发丝", "role": "passive"},
               {"part": "衣摆袍角", "role": "passive"}]},

    {"物体": "行人C", "source": "gait",
     "parts": [{"part": "足", "role": "anchor"},
               {"part": "躯干", "role": "driven"},
               {"part": "发髻发丝", "role": "passive"},
               {"part": "衣摆袍角", "role": "passive"}]},

    {"物体": "行人D", "source": "gait",
     "parts": [{"part": "足", "role": "anchor"},
               {"part": "躯干", "role": "driven"},
               {"part": "发髻发丝", "role": "passive"},
               {"part": "衣摆袍角", "role": "passive"}]},

    {"物体": "城墙", "source": "none",
     "parts": [{"part": "墙体", "role": "anchor"}]},
]}

inv = solver.inventory(ACTORS)
r = solver.assemble(ANSWER)
print("=== 代码组装结果 ===")
for s in r["组装"]:
    print("  %-8s family=%-11s 锚点=%s 链=%s"
          % (s["物体"], s["family"], s["锚点(恒不动)"],
             [(c["part"], c["role"]) for c in s["链"]]))
print()
print("=== 代码告诉我：要去搜哪些物性 ===")
for m in r["待搜物性"]:
    print("  [%s] %s -> %s   (%s)" % (m["物体"], m["部件组"], m["缺"], m["提示"]))
json.dump({"问卷": ANSWER["问卷"], "待搜物性": r["待搜物性"]},
          open("_问卷结果.json", "w"), ensure_ascii=False, indent=1)
