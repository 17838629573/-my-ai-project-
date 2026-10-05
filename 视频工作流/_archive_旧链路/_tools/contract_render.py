#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""contract_render —— 契约层/事实层渲染（contract_gen.py 拆出，过体积门禁）"""

from fact_extract import rules_of
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工作流根（本工具在 _tools/）


def render_S(mod, f, dep, rdep, depth, loc_map):
    L, M = loc_map.get(mod, ("?", "?"))
    tier = "TOP" if M == "_top" else "S"
    out = [f"[{tier}] {mod} @{L}/{M}  d{depth}  in={len(rdep)}  gen:contract_gen"]
    if f.get("error"):
        out.append("error: " + f["error"])
        return "\n".join(out)

    # 一句话：模块 docstring 首行；没有则用公开函数名概括
    brief = f["doc"].split("\n")[0][:60] if f["doc"] else ""
    if not brief:
        pub = [x["name"] for x in f["fns"] if x["public"]]
        brief = "提供 " + ", ".join(pub[:6]) if pub else "（无公开接口，内部模块）"
    out.append("does: " + brief)

    warn = []
    if f["main_at"] and f["sc_at"] and f["main_at"] < f["sc_at"]:
        warn.append(f"__main__@L{f['main_at']} 早于 self_check@L{f['sc_at']}"
                    f" → 入口 NameError，自检从未跑通")
    if warn:
        out.append("WARN: " + "; ".join(warn))

    pub = [x for x in f["fns"] if x["public"]]
    if pub:
        names = [x["name"] for x in pub[:12]]
        out.append("api: " + ", ".join(names) + (f" (+{len(pub)-12})" if len(pub) > 12 else ""))
    if f["const_names"]:
        out.append("const: " + ", ".join(f["const_names"][:8])
                   + (f" (+{len(f['const_names'])-8})" if len(f["const_names"]) > 8 else ""))
    # impl: 粗略内部实现——只说主线怎么走，禁止全量 AST 转储（行号/全调用链）。
    #   读契约的人只需判断"是不是我要找的模块"，细节读源码。
    impl = _rough_impl(f)
    if impl:
        out.append("impl: " + impl)

    if dep:
        out.append("up: " + ",".join(sorted(dep)))
    if rdep:
        out.append("down: " + ",".join(sorted(rdep)[:6])
                   + (f" (+{len(rdep)-6})" if len(rdep) > 6 else ""))
    # edit: 改本模块必须回头看的文件（上游+下游全集，不截断）。
    #   用途：改 X 时照此清单读，禁止一次性读全量。
    touch = sorted(set(dep) | set(rdep))
    if touch:
        out.append("edit: " + ",".join(touch)
                   + f"   # 改{mod}须同步核对这些文件")
    r = rules_of(mod)
    if r.strip():
        out.append("rule: " + r)
    out.append(f"why : IMPROVE_{mod}.md" if os.path.exists(os.path.join(BASE, f"IMPROVE_{mod}.md"))
               else "why : （缺，待补）")
    return "\n".join(out)
def render_D(mod, f, dep, rdep):
    out = [f"[FACT] {mod}   {f['lines']}行   机器生成，勿手改"]
    if f.get("error"):
        out.append("error: " + f["error"])
        return "\n".join(out)
    if f["doc"]:
        out.append("doc: " + f["doc"].split("\n")[0][:100])
    pub = [x for x in f["fns"] if x["public"]]
    if pub:
        out.append("api:")
        for x in pub:
            d = f"  # {x['doc']}" if x["doc"] else ""
            out.append(f"  L{x['line']} {x['sig']}{d}")
    priv = [x for x in f["fns"] if not x["public"]]
    if priv:
        out.append("internal:")
        for x in priv:
            out.append(f"  L{x['line']} {x['sig']}")
    rel = [f"{x['name']}→{c}" for x in f["fns"] for c in x["calls_local"]]
    if rel:
        out.append("calls_in: " + ", ".join(rel))
    exts = sorted({e for x in f["fns"] for e in x["calls_ext"]})
    if exts:
        out.append("calls_out: " + ",".join(exts))
    er = [f"{k}@L{v}" for x in f["fns"] for k, v in x["early"]]
    if er:
        out.append("guard: " + ", ".join(er))
    if f["const"]:
        out.append("const: " + ", ".join(f["const"]))
    if f["main_at"]:
        out.append(f"main: __main__@L{f['main_at']}"
                   + (f"  self_check@L{f['sc_at']}" if f["sc_at"] else ""))
    out.append("up: " + ",".join(sorted(dep)) if dep else "up: -")
    out.append("down: " + ",".join(sorted(rdep)) if rdep else "down: -")
    return "\n".join(out)


def _rough_impl(f):
    """粗略内部实现：一句话主线 + 边界。不做全量 AST 转储。

    取 main/self_check 的主干调用链（最多3跳），加 guard 行号。
    """
    parts = []
    fns = {x["name"]: x for x in f["fns"]}
    entry = None
    for cand in ("main", "self_check", "run", "__main__"):
        if cand in fns:
            entry = cand
            break
    if entry is None and f["fns"]:
        entry = f["fns"][0]["name"]
    if entry:
        chain = [c for c in fns[entry].get("calls_local", [])][:3]
        if chain:
            parts.append("%s → %s" % (entry, " → ".join(chain)))
        else:
            parts.append("入口 %s" % entry)
    n_priv = len([x for x in f["fns"] if not x["public"]])
    if n_priv:
        parts.append("内部helper %d个" % n_priv)
    if f.get("guard_at"):
        parts.append("边界 raise@L%d" % f["guard_at"])
    return "；".join(parts)
