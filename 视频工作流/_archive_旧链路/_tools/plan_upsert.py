#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""plan_upsert —— 修复表/计划表的幂等写入器

【由来】VIDEO_FIX_PLAN.json 出现 V7/V8 各两份、V6 丢失：
  原因是 list.append 非幂等，沙盒崩溃重跑就追加一份。
  ADR 业界规范：决策记录 append-only，同 id 不得原地重复追加。

用法:
    python3 plan_upsert.py VIDEO_FIX_PLAN.json <id> '<json片段>'
    python3 plan_upsert.py VIDEO_FIX_PLAN.json --dedupe      # 只去重
    python3 plan_upsert.py --check VIDEO_FIX_PLAN.json       # 查重复/缺失

同 id 已存在 → 合并更新（新字段覆盖旧字段），不新增条目。
"""
import json
import io
import os
import sys


def load(p):
    return json.load(io.open(p, encoding="utf-8"))


def save(p, d):
    json.dump(d, io.open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def steps_of(d):
    """兼容 步骤/steps 两种键名。"""
    for k in ("步骤", "steps"):
        if k in d and isinstance(d[k], list):
            return k
    return None


def dedupe(d):
    k = steps_of(d)
    if not k:
        return d, 0
    seen, order, n = {}, [], 0
    for s in d[k]:
        i = s.get("id")
        if i is None:
            order.append(("__noname%d" % n, s))
            n += 1
            continue
        if i not in seen:
            order.append((i, s))
        seen[i] = s
    out = []
    for i, s in order:
        out.append(s)
    removed = len(d[k]) - len(out)
    d[k] = out
    return d, removed


def check(p):
    d = load(p)
    k = steps_of(d)
    if not k:
        print("无步骤列表"); return 1
    ids = [s.get("id") for s in d[k]]
    dup = [x for x, c in __import__("collections").Counter(ids).items() if c > 1]
    print("%s: %d 步  id=%s" % (os.path.basename(p), len(ids), ids))
    if dup:
        print("  [FAIL] 重复 id: %s" % dup); return 1
    print("  [PASS] 无重复")
    return 0


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    flags = [x for x in sys.argv[1:] if x.startswith("--")]
    if not a:
        print(__doc__); return 2
    p = a[0]
    if "--check" in flags:
        return check(p)
    d = load(p)
    if "--dedupe" in flags or len(a) == 1:
        d, rm = dedupe(d)
        save(p, d)
        print("去重完成，移除 %d 条重复" % rm)
        return 0
    sid, frag = a[1], a[2]
    k = steps_of(d)
    patch = json.loads(frag)
    hit = [s for s in d[k] if s.get("id") == sid]
    if hit:
        hit[0].update(patch)
        print("更新已存在条目 %s" % sid)
    else:
        patch.setdefault("id", sid)
        d[k].append(patch)
        print("新增条目 %s" % sid)
    d, rm = dedupe(d)
    save(p, d)
    return 0


if __name__ == "__main__":
    sys.exit(main())
