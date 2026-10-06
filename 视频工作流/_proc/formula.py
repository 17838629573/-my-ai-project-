# 契约: proc/(root)/formula
#   一句话: 公式注册表与 STUB 门禁：缺公式抛错并给搜索关键词，禁止凭记忆写近似值
#   完整契约见 (root)/__init__.py
# -*- coding: utf-8 -*-
"""formula —— 公式登记表的状态面板与 STUB 门禁

三件事：
  1. panel()      打印状态面板（哪些有、哪些缺、该搜什么）
  2. require(id)  取公式；缺则抛 MissingFormula，绝不静默返回近似值
  3. check(list)  写动画脚本前先声明要用的公式，一次性报出缺口

STUB 原则（用户定）：缺公式不能靠内部知识凑一个近似，必须标记出来去搜。
"""
import json, os

REG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FORMULA_REGISTRY.json")


class MissingFormula(Exception):
    pass


def load():
    with open(REG, encoding="utf-8") as f:
        return json.load(f)


def index(reg=None):
    reg = reg or load()
    idx = {}
    for g in reg["groups"]:
        for it in g["items"]:
            idx[it["id"]] = dict(it, group=g["name"])
    return idx


def require(fid, reg=None):
    """取公式描述。IMPL/MIGRATE 返回；其余一律抛错。"""
    idx = index(reg)
    if fid not in idx:
        raise MissingFormula("未登记公式 %r（先加进 FORMULA_REGISTRY.json）" % fid)
    it = idx[fid]
    if it["status"] in ("IMPL", "MIGRATE"):
        return it
    raise MissingFormula(
        "公式缺失 [%s] %s\n"
        "  状态: %s\n"
        "  搜索关键词: %s\n"
        "  → 搜到后填入 _proc，把 status 改成 IMPL"
        % (fid, it["name"], it["status"], it["search_hint"] or "(未填)"))


def check(ids):
    """批量声明。返回 (可用, 缺口清单)"""
    idx = index()
    ok, miss = [], []
    for fid in ids:
        try:
            require(fid, None); ok.append(fid)
        except MissingFormula as e:
            miss.append((fid, str(e).split("\n")[0], idx.get(fid, {}).get("search_hint", "")))
    return ok, miss


def panel():
    reg = load()
    icon = {"IMPL": "[x]", "MIGRATE": "[~]", "STUB": "[ ]", "ARCH": "[ ]"}
    cnt = {"IMPL": 0, "MIGRATE": 0, "STUB": 0, "ARCH": 0}
    print("=" * 62)
    print("  公式状态面板   [x]=新引擎已有  [~]=待迁入  [ ]=缺")
    print("=" * 62)
    todo = []
    for g in reg["groups"]:
        print("\n  %s" % g["name"])
        for it in g["items"]:
            s = it["status"]; cnt[s] += 1
            print("   %s %-22s %s" % (icon[s], it["name"], s))
            if s in ("STUB", "ARCH"):
                todo.append(it)
    print("\n" + "-" * 62)
    print("  合计  已实现%d  待迁入%d  缺%d" % (cnt["IMPL"], cnt["MIGRATE"],
                                          cnt["STUB"] + cnt["ARCH"]))
    print("\n  缺口清单（下一步该搜的）：")
    for i, it in enumerate(todo, 1):
        print("   %2d. %-22s %s" % (i, it["name"], it["search_hint"] or "(待补关键词)"))
    return todo


if __name__ == "__main__":
    panel()


# ---------------------------------------------------------------- 工具优先门禁
class UnsourcedFormula(Exception):
    pass


def audit_source(reg=None):
    """工具优先（用户定）：标 IMPL 的公式必须带 source（文献/出处/URL）。

    没有出处 = 是我自己拍脑袋想出来的 → 一律打回，去搜。
    返回 [(id, name)] 违规清单。
    """
    idx = index(reg)
    bad = []
    for fid, it in idx.items():
        if it["status"] == "IMPL" and not (it.get("source") or "").strip():
            bad.append((fid, it["name"]))
    return bad


def claim(fid, source, reg=None):
    """把搜到的出处写回登记表，并把状态置为 IMPL。"""
    reg = reg or load()
    for g in reg["groups"]:
        for it in g["items"]:
            if it["id"] == fid:
                it["status"] = "IMPL"
                it["source"] = source
                json.dump(reg, open(REG, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
                return it
    raise MissingFormula("未登记 %r" % fid)
