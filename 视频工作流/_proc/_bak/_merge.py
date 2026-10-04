"""按来源规则 R2（模块 50~500 行）合并过短模块到兄弟模块。

出处: mrognlie "Below 50: the module barely earns its own file; consider merging with sibling"
备份在 _bak/pre_merge/，出问题可整体回滚。
"""
import os
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
BAK = os.path.join(ROOT, "_bak", "pre_merge")
os.makedirs(BAK, exist_ok=True)


def body_of(path):
    """抽取功能体：从首个 def/常量开始，去掉契约注释、import、__all__、分隔注释。"""
    lines = open(path, encoding="utf-8").read().splitlines()
    start = None
    for i, ln in enumerate(lines):
        if ln.startswith("def ") or ln.startswith("class ") or (
                ln[:1].isupper() and "=" in ln.split("#")[0]):
            start = i
            break
    if start is None:
        return []
    out = []
    for ln in lines[start:]:
        s = ln.strip()
        if s.startswith("__all__") or s.startswith("# ---") or s.startswith("import ") \
           or s.startswith("from "):
            continue
        out.append(ln)
    return out


def exported(path):
    import re
    return set(re.findall(r"^def\s+(\w+)|^([A-Z][A-Z_0-9]*)\s*=",
                          open(path, encoding="utf-8").read(), re.M)) \
        if False else set(
            m for m in re.findall(r"^(?:def\s+(\w+)|([A-Z][A-Z_0-9]*)\s*=)",
                                  open(path, encoding="utf-8").read(), re.M)
            for m in m if m)


def merge(src, tgt, insert_before=None):
    sp = os.path.join(ROOT, src)
    tp = os.path.join(ROOT, tgt)
    if not os.path.exists(sp):
        print("跳过（不存在）", src)
        return False
    shutil.copy(sp, os.path.join(BAK, os.path.basename(src)))
    body = body_of(sp)
    if not body:
        print("跳过（无功能体）", src)
        return False
    tlines = open(tp, encoding="utf-8").read().splitlines()
    clash = exported(sp) & set(
        __import__("re").findall(r"^(?:def\s+(\w+)|([A-Z][A-Z_0-9]*)\s*=)",
                                 "\n".join(tlines), __import__("re").M)
        and [a or b for a, b in __import__("re").findall(
            r"^(?:def\s+(\w+)|([A-Z][A-Z_0-9]*)\s*=)", "\n".join(tlines), __import__("re").M)]
        or [])
    if clash:
        print("跳过（命名冲突）", src, clash)
        return False
    if insert_before:
        idx = next((i for i, ln in enumerate(tlines) if ln.startswith(insert_before)), None)
        if idx is None:
            print("跳过（找不到插入点）", src)
            return False
        new = tlines[:idx] + [""] + body + [""] + tlines[idx:]
    else:
        idx = None
        for i in range(len(tlines) - 1, -1, -1):
            if tlines[i].startswith("__all__"):
                idx = i
                break
        new = (tlines[:idx] + body + [""] + tlines[idx:]) if idx is not None \
            else tlines + [""] + body
    open(tp, "w", encoding="utf-8").writelines(ln + "\n" for ln in new)
    os.remove(sp)
    print(f"合并 {src} -> {tgt}（{len(body)} 行）")
    return True


def drop_line(path, needles):
    p = os.path.join(ROOT, path)
    if not os.path.exists(p):
        return
    lines = open(p, encoding="utf-8").read().splitlines()
    keep = [ln for ln in lines if not any(nd in ln for nd in needles)]
    open(p, "w", encoding="utf-8").writelines(ln + "\n" for ln in keep)


# 1) 三个过短模块合并到语义最近的兄弟
merge("scene/kit/cloud.py", "scene/kit/sky.py")           # 云并入天空
merge("scene/kit/biome.py", "scene/kit/terrain.py")       # 群区配色并入地形
merge("scene/kit/place.py", "scene/kit/compose.py",
      insert_before="ELEMENTS = {")                        # 草/花/行人并入注册表前

# 2) sdf.py 46 行：仅当只有 render 引用时才合并
ch_dir = os.path.join(ROOT, "motion", "character")
users = [f for f in os.listdir(ch_dir)
         if f.endswith(".py") and f != "sdf.py"
         and "sdf" in open(os.path.join(ch_dir, f), encoding="utf-8").read()]
if users == ["render.py"]:
    merge("motion/character/sdf.py", "motion/character/render.py")
else:
    print("sdf.py 保留（引用者不止 render）:", users)

# 3) 清理失效 import 与文档条目
drop_line("scene/kit/__init__.py",
          ["from .cloud import", "from .biome import", "from .place import",
           "cloud.py ", "biome.py ", "place.py "])
drop_line("scene/kit/compose.py", ["from .cloud import", "from .place import"])
drop_line("motion/character/__init__.py", ["from .sdf import"])

# 4) 拆分脚本已用完，归档
for f in ("_split_char.py", "_split_kit.py"):
    p = os.path.join(ROOT, f)
    if os.path.exists(p):
        shutil.move(p, os.path.join(BAK, f))
        print("归档", f)
print("完成")
