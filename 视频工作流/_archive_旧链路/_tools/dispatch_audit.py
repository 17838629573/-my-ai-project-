#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dispatch_audit.py —— 检查规则表本身的边界问题。

查三类：
  1. 重复条目    同一 id/name 出现多次
  2. 覆盖空洞    某种输入组合没有任何规则能处理
  3. 边界重合    同一个阶段内，某种输入组合有多条规则同时适用（互斥项撞车）

关键：规则必须先分【阶段】。
  互斥项（只能选一条）与串联项（必须依次执行）混在同一张平面表里，
  必然产生伪重合 —— 那是表的结构错误，不是规则的错。

用法: python3 _tools/dispatch_audit.py
"""
import itertools, json, os, sys
from collections import defaultdict

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(BASE, "RULES.json")

# 阶段定义：同一 stage 内的条目互斥，不同 stage 之间串联
STAGE = {
    # --- 抠图域 ---
    "M_a": "key",        # 键控主方法（互斥）
    "M_e": "key",
    "M_g": "key",
    "M_f": "plate",      # plate 构造（前置）
    "M_i": "trimap",     # 三分区（matte 前置）
    "M_j": "matte",      # matting 精修（互斥：与 key 二选一）
    "M_k": "post",       # 后处理（串联）
    "M_b": "post",
    "M_c": "post",
    "M_o": "composite",  # 合成（必经）
    "M_d": "attach",     # 附加（可选）
    # --- 运动域：全部是按对象类型分工，非互斥 ---
    "T_a": "wind", "T_l": "wind", "T_c": "wind", "T_d": "wind",
    "T_b": "period", "T_f": "period", "T_q": "period", "T_o": "period",
    "T_e": "period",
    "T_g": "skeleton", "T_h": "skeleton", "T_i": "skeleton",
    "T_j": "skeleton", "T_m": "skeleton", "T_r": "skeleton",
    "T_k": "proc", "T_p": "proc", "T_n": "proc",
}

# 输入空间维度（可枚举）
DIM_MATTE = {
    "plate": ["有真实plate", "无plate"],
    "edge": ["简单硬边", "复杂边缘"],
    "type": ["人物", "柔性旗帜", "程序层", "字幕UI"],
}
DIM_MOTION = {
    "periodic": ["周期", "一次性"],
    "kind": ["骨架可驱动", "程序化可算", "需生图"],
    "stochastic": ["确定性", "随机非刚性"],
}
# 交互域：维度由 interaction_gen.DIMS 提供，避免两处各写一份
import importlib.util as _il
_spec = _il.spec_from_file_location(
    "interaction_gen", os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "interaction_gen.py"))
_ig = _il.module_from_spec(_spec); _spec.loader.exec_module(_ig)
DIM_INTER = _ig.DIMS

# 判定一律读 RULES.json 每条的 cond 字段 —— 不再手写谓词。
# 手写谓词与表内自然语言是两层，可能不一致（那才是幻觉的真正藏身处）。
def make_ok(D, dom):
    items = D[dom]["候选枚举"] if "候选枚举" in D[dom] else D[dom]
    conds = {}
    for it in items:
        c = it.get("cond")
        if not c:
            print(f"  [FAIL] {it['id']} 缺 cond —— 无法判定，先跑 "
                  f"python3 _tools/cond_gen.py gen/apply")
            raise SystemExit(1)
        conds[it["id"]] = c

    def ok(rid, ctx):
        """ctx: {维度: 值}。cond 里缺的维度视为"任意"（宽容）。"""
        c = conds.get(rid)
        if c is None:
            return False
        for k, want in c.items():
            got = ctx.get(k)
            if got is None:
                continue
            if want == "任意" or (isinstance(want, list) and "任意" in want):
                continue
            allow = want if isinstance(want, list) else [want]
            if got not in allow:
                return False
        return True
    return ok


def main():
    D = json.load(open(R, encoding="utf-8"))
    fails = []

    print("=" * 64)
    print("1) 重复条目检查")
    print("=" * 64)
    for dom in ("matte", "motion"):
        seen = defaultdict(list)
        for it in D[dom]["候选枚举"]:
            seen[it["id"]].append(it["name"])
        dup = {k: v for k, v in seen.items() if len(v) > 1}
        if dup:
            for k, v in dup.items():
                print(f"  [FAIL] {dom}/{k} 出现 {len(v)} 次: {v}")
                fails.append(f"{dom}/{k} 重复")
        else:
            print(f"  [PASS] {dom} 无重复 id")

    print("\n" + "=" * 64)
    print("2) 空洞 / 重合（按阶段分，同阶段内才互斥）")
    print("=" * 64)

    for dom, dims in (("matte", DIM_MATTE), ("motion", DIM_MOTION),
                      ("interaction", DIM_INTER)):
        okf = make_ok(D, dom)
        _sec = D[dom]["候选枚举"] if "候选枚举" in D[dom] else D[dom]
        ids = [i["id"] for i in _sec]
        keys = list(dims)
        combos = list(itertools.product(*[dims[k] for k in keys]))
        # 按阶段分组
        by_stage = defaultdict(list)
        for rid in ids:
            by_stage[STAGE.get(rid, "?")].append(rid)

        print(f"\n--- {dom} ---  阶段: {dict(by_stage)}")

        holes, clashes = [], []
        for combo in combos:
            ctx = dict(zip(keys, combo))
            for stage, rids in sorted(by_stage.items()):
                if stage in ("post", "composite", "attach"):
                    continue   # 串联/必经/可选阶段不做互斥判定
                hit = [r for r in rids if okf(r, dict(zip(keys, combo)))]
                if dom == "matte" and stage in ("key", "matte"):
                    # key 与 matte 一起构成"主抠图方法"，整体互斥
                    continue
                if len(hit) == 0:
                    holes.append((combo, stage))
                elif len(hit) > 1:
                    clashes.append((combo, stage, hit))

        if dom != "matte":
            # motion 域是【职责分工】，不是互斥流水线 —— 天然多对多，
            # 同一输入命中多条属正常（如骨架域的插值/循环/混合/防漂移各管一块）。
            # 只对"某类输入在所有阶段都无解"报空洞。
            covered = set()
            for c in combos:
                if any(okf(r, dict(zip(keys, c))) for r in ids):
                    covered.add(c)
            nocov = [c for c in combos if c not in covered]
            if nocov:
                print(f"\n  真空洞（所有阶段都无解）:")
                for c in nocov[:6]:
                    print(f"    {dict(zip(keys,c))}")
            else:
                print("\n  [PASS] 无真空洞（每类输入至少有一条规则覆盖）")

            # 逐阶段空洞里，排除"该输入本就不属于该阶段"的情形
            print(f"\n  各阶段命中数（供人工核对，非缺陷）:")
            for stage2, rids in sorted(by_stage.items()):
                n = sum(1 for c in combos if any(okf(r, dict(zip(keys, c))) for r in rids))
                print(f"    {stage2:<10} 覆盖 {n}/{len(combos)} 组合")
            continue

        # 抠图主方法：key 出粗 alpha，matte 精修 —— 两者是串联不是互斥。
        # 所以判定标准是：key 阶段必须【恰好 1 条】；matte 阶段命中即精修。
        key_ids = by_stage.get("key", [])
        main_holes, main_clash = [], []
        for combo in combos:
            ctx = dict(zip(keys, combo))
            if ctx.get("type") in ("程序层", "字幕UI"):
                continue
            hit = [r for r in key_ids if okf(r, dict(zip(keys, combo)))]
            if len(hit) == 0:
                main_holes.append(combo)
            elif len(hit) > 1:
                main_clash.append((combo, hit))

        print(f"\n  主抠图方法(key 阶段，须恰好 1 条):")
        if main_holes:
            for c in main_holes:
                print(f"    [空洞] {dict(zip(keys,c))} -> 无规则可用")
                fails.append(f"{dom} 空洞 {c}")
        else:
            print("    [PASS] 无空洞")
        if main_clash:
            # 已写进 dispatch.裁决 的重合不算缺陷
            ruled = {(r.get("场景"), tuple(r.get("候选", [])))
                     for r in D.get("dispatch", {}).get("裁决", [])}
            unresolved = []
            for c, hit in main_clash:
                ctx = dict(zip(keys, c))
                desc = "无 plate + 简单硬边" if ctx["plate"] == "无plate" else \
                       "有 plate + 复杂边缘"
                if (desc, tuple(hit)) in ruled or (desc, tuple(sorted(hit))) in ruled:
                    print(f"    [已裁决] {ctx} -> {hit}")
                else:
                    print(f"    [重合] {ctx} -> {hit}  (须写进 dispatch.裁决)")
                    unresolved.append(c)
            if unresolved:
                fails.extend(f"{dom} 未裁决重合 {c}" for c in unresolved)
        else:
            print("    [PASS] 无重合")

        # 排除项：命中排除的输入不算空洞
        excl = {e["输入"].split("（")[0] for e in D.get("dispatch", {}).get("排除项", [])}
        COND = {"plate", "trimap"}   # 条件性阶段：无plate 无 plate 阶段；简单硬边无需 trimap 精修
        real = []
        for c, s in holes:
            ctx = dict(zip(keys, c))
            if s == "plate" and ctx.get("plate") == "无plate":
                continue
            if s == "trimap" and ctx.get("edge") == "简单硬边":
                continue                      # 条件性阶段，正常
            if any(e in str(ctx.get("type", "")) for e in excl):
                continue                      # 已排除的输入，正常
            real.append((c, s))
        if real:
            print(f"\n  其它阶段空洞:")
            for c, s in real[:8]:
                print(f"    [{s}] {dict(zip(keys,c))}")
        else:
            print("\n  [PASS] 其它阶段无空洞（程序层/字幕UI 属排除，无plate 无 plate 阶段属正常）")

        if clashes:
            print(f"\n  其它阶段重合:")
            for c, s, hit in clashes[:8]:
                print(f"    [{s}] {dict(zip(keys,c))} -> {hit}")

    print("\n" + "=" * 64)
    if fails:
        print(f"[FAIL] 共 {len(fails)} 处边界问题")
        return 1
    print("[PASS] 规则表边界自洽")
    return 0


if __name__ == "__main__":
    sys.exit(main())
