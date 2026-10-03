#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_family_map —— 五类 → 物理形态 唯一映射（铁律88）

对外（AI 声明）只用五类：biped/quadruped/vegetation/rigid/cloth
内部物理求解仍用物理形态，由本模块查表转换，AI 不接触物理形态名。

契约:   contracts/family_map.md
依赖:   无（纯数据 + 校验，避免成环）
被依赖: _solver_base, _solver_chain, driver, solver_survey
改前必读: IMPROVE_family_map.md
"""
from __future__ import annotations

__all__ = ["FIVE", "PHYSICS", "FAMILY_TO_PHYSICS", "to_physics",
           "is_five", "need_physics", "self_check"]

# 对外五类（AI 唯一可见）
FIVE = ("biped", "quadruped", "vegetation", "rigid", "cloth")

# 内部物理形态（AI 不可见，仅代码使用）
PHYSICS = ("chain", "cantilever", "pendulum2", "hinge", "free_surface", "static")

# 五类 -> 默认物理形态（唯一真源）
# 动态规则：spec 含 links（链级结构）时一律走 chain，见 to_physics_dyn
FAMILY_TO_PHYSICS = {
    "biped": "chain",       # 躯干驱动，四肢/衣摆被动
    "quadruped": "chain",   # 脊柱驱动，四腿相位交错
    "vegetation": "chain",  # 树干驱动，枝条受迫
    "rigid": "static",      # 刚体：无振动求解，仅位移+轮转
    "cloth": "cantilever",  # 旗帜本体=悬臂；带垂带(links)时转 chain
}


def to_physics_dyn(fam, spec=None):
    """五类 -> 物理形态（含动态规则）。spec 有 links 则走受迫链。"""
    phys = to_physics(fam)
    if phys != "static" and spec and spec.get("links"):
        return "chain"      # 有链级结构 -> 受迫阻尼链
    return phys


class FamilyError(ValueError):
    pass


def is_five(fam):
    """是否对外五类之一。"""
    return fam in FIVE


def to_physics(fam):
    """五类 -> 物理形态。非五类直接报错（铁律88：禁静默降级）。"""
    if not is_five(fam):
        raise FamilyError(
            "族=%r 非五类之一（应为 %s）。物理形态名(cantilever/pendulum2/chain)"
            " 由代码转换，AI 禁止直接填写" % (fam, "/".join(FIVE)))
    return FAMILY_TO_PHYSICS[fam]


def need_physics(fam):
    """该族是否需要物理振动求解。rigid 不需要。"""
    return to_physics(fam) != "static"


# ------------------------------------------------------------------ 自检
def _chk(name, ok, info=""):
    return {"name": name, "ok": bool(ok), "info": info}


def self_check():
    ok = []
    # 1 映射完整性：五类全覆盖
    ok.append(_chk("五类全覆盖",
                   all(f in FAMILY_TO_PHYSICS for f in FIVE)))
    # 2 映射值合法：都是已知物理形态
    ok.append(_chk("映射值合法",
                   all(v in PHYSICS for v in FAMILY_TO_PHYSICS.values())))
    # 3 转换正确性
    ok.append(_chk("rigid->static", to_physics("rigid") == "static"))
    ok.append(_chk("cloth 默认->cantilever", to_physics("cloth") == "cantilever"))
    ok.append(_chk("cloth 有links->chain",
                   to_physics_dyn("cloth", {"links": [{"L": 0.5}]}) == "chain"))
    ok.append(_chk("biped->chain", to_physics("biped") == "chain"))
    # 4 非五类必须报错（含物理形态名）
    for bad in ("cantilever", "pendulum2", "chain", "", None):
        try:
            to_physics(bad)
            ok.append(_chk("证伪:禁物理形态名 %r" % bad, False, "竟通过"))
        except FamilyError:
            ok.append(_chk("证伪:禁物理形态名 %r" % bad, True))
    # 5 need_physics
    ok.append(_chk("rigid 不求振动", need_physics("rigid") is False))
    ok.append(_chk("cloth 需求振动", need_physics("cloth") is True))
    return ok


if __name__ == "__main__":
    rs = self_check()
    bad = [r for r in rs if not r["ok"]]
    for r in rs:
        print("%s %s %s" % ("PASS" if r["ok"] else "FAIL", r["name"], r["info"]))
    print("---- %d/%d PASS" % (len(rs) - len(bad), len(rs)))
    raise SystemExit(1 if bad else 0)
