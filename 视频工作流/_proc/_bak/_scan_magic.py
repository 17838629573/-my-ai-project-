# -*- coding: utf-8 -*-
"""扫出手填系数：凡 0.01~100 的浮点字面量，且不在注释行，都算嫌疑。"""
import re, os, json, collections

FILES = [f for f in os.listdir(".") if f.endswith(".py") and not f.startswith("_scan")]
PAT = re.compile(r"(?<![\w.])([0-9]*\.?[0-9]+)(?![\w.])")
hits = collections.defaultdict(list)
for fn in sorted(FILES):
    for ln, line in enumerate(open(fn, encoding="utf-8"), 1):
        s = line.strip()
        if s.startswith("#") or s.startswith('"""') or "=" not in line:
            continue
        if re.search(r"#\s*(文献|公式|原文|ref|D&C|Winter|0\.414)", line):
            continue
        for m in PAT.finditer(line.split("#")[0]):
            v = float(m.group(1))
            if 0.01 <= v <= 100 and v not in (0.5, 1.0, 2.0, 30.0, 60.0, 90.0, 100.0):
                hits[fn].append((ln, v, s[:78]))
out = []
for fn in sorted(hits):
    for ln, v, s in hits[fn]:
        out.append(dict(file=fn, line=ln, val=v, code=s))
json.dump(out, open("_magic.json", "w"), ensure_ascii=False, indent=1)
print("嫌疑硬编码 %d 处，涉及 %d 个文件" % (len(out), len(hits)))
for fn in sorted(hits):
    print("  %-14s %d" % (fn, len(hits[fn])))
