"""一次性迁移脚本：把扁平模块整理成大/中/小三层。"""
import os, re, shutil, sys

ROOT = os.path.dirname(os.path.abspath(__file__))

# 中模块 -> 小模块
LAYOUT = {
    "shape":  ["line.py", "character.py"],          # 画线：形体与骨架
    "color":  ["paint.py"],                          # 填色
    "scene":  ["kit.py", "detail.py", "bgpack.py"],  # 背景
    "motion": ["camera.py", "run.py", "stage.py", "beat.py", "wind.py"],  # 跑起来
}
ROOT_KEEP = ["formula.py", "prompt2spec.py"]         # 门禁层与提示词对照，留在根

BAK = os.path.join(ROOT, "_bak")
os.makedirs(BAK, exist_ok=True)

# 1) 归档临时诊断脚本
for f in os.listdir(ROOT):
    if f.startswith("_") and f.endswith(".py") and f != "__init__.py":
        shutil.move(os.path.join(ROOT, f), os.path.join(BAK, f))
        print("归档", f)

# 2) 建目录并移动小模块
for mid, files in LAYOUT.items():
    d = os.path.join(ROOT, mid)
    os.makedirs(d, exist_ok=True)
    for fn in files:
        src = os.path.join(ROOT, fn)
        if os.path.exists(src):
            shutil.move(src, os.path.join(d, fn))
            print("移动", fn, "->", mid + "/")

# 3) 改写内部 import 为跨包绝对导入
MOD2PKG = {}
for mid, files in LAYOUT.items():
    for fn in files:
        MOD2PKG[fn[:-3]] = mid

IMPORT_RE = re.compile(
    r"^(\s*)(import\s+([A-Za-z_][\w]*)\s+as\s+(\w+)|import\s+([A-Za-z_][\w]*)|"
    r"from\s+([A-Za-z_][\w]*)\s+import\s+(.+))$")

def fix(path, pkg):
    out, changed = [], 0
    with open(path, encoding="utf-8") as fh:
        for ln in fh:
            m = IMPORT_RE.match(ln.rstrip("\n"))
            if not m:
                out.append(ln); continue
            ind = m.group(1)
            alias, plain, frm, names = m.group(4), m.group(5), m.group(6), m.group(7)
            if alias and m.group(3) in MOD2PKG:
                t = MOD2PKG[m.group(3)]
                if t != pkg:
                    out.append(f"{ind}from {t} import {m.group(3)} as {alias}\n"); changed += 1; continue
            elif plain and plain in MOD2PKG:
                t = MOD2PKG[plain]
                if t != pkg:
                    out.append(f"{ind}from {t} import {plain}\n"); changed += 1; continue
            elif frm and frm in MOD2PKG:
                t = MOD2PKG[frm]
                if t != pkg:
                    out.append(f"{ind}from {t}.{frm} import {names}\n"); changed += 1; continue
            out.append(ln)
    if changed:
        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(out)
    return changed

total = 0
for mid, files in LAYOUT.items():
    for fn in files:
        p = os.path.join(ROOT, mid, fn)
        if os.path.exists(p):
            n = fix(p, mid)
            if n:
                print("修导入", mid + "/" + fn, n)
            total += n
print("导入改写总数", total)
