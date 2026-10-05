# 契约: proc/tools/layers.py
#   一句话: 分层契约门禁——包装 import-linter，替代自造的 R1(逆向依赖)/R4(上帝包)
#   完整契约见 _proc/tools/__init__.py
#   依据: (1) import-linter 是业界成熟的架构约束工具，声明式 layers/forbidden/independence
#            contracts + ignore_imports 债务台账（Kraken monolith 实践 40+ contracts）
#            https://import-linter.readthedocs.io/
#         (2) 自造规则的问题：R1 靠 ALLOW 表逐条比对，漏定义层就产生假阳性；
#            R4 用"包内条目数>20"判上帝包，与依赖方向无关，是拍脑袋指标。
#            改为声明式 contract 后，配置即文档，未登记层会被工具直接报出。
# -*- coding: utf-8 -*-
"""分层契约门禁（R21）。

配置在项目根 .importlinter（层序与 check.py ALLOW 表一致）：
    tools > tests > showreel > motion > scene > color > shape > base

用法:
    python3 _proc/tools/layers.py            # 人读
    python3 _proc/tools/layers.py --json     # 机读
    （等价 CLI: cd 项目根 && lint-imports）
"""
import json
import os
import re
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROC = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_PROC)

CONFIG = os.path.join(_ROOT, ".importlinter")
KEPT_RE = re.compile(r"Contracts:\s*(\d+)\s+kept,\s*(\d+)\s+broken\.", re.I)
CONTRACT_RE = re.compile(r"^(\S.*?)\s+(KEPT|BROKEN)\s*$", re.M)


def run():
    """跑 lint-imports，返回 {"ok":bool,"kept":n,"broken":m,"contracts":[...],"error":str|None}"""
    if not os.path.exists(CONFIG):
        return {"ok": False, "kept": 0, "broken": 0, "contracts": [],
                "error": "配置文件缺失: %s" % CONFIG}
    try:
        # PYTHONPATH 必须含 _proc: 项目存在 _proc.motion 与 motion 两套包名(双包名),
        # 缺 _proc 时 grimp 找不到扁平包, 直接报
        #   "Could not find package 'tools' in your Python path."
        # —— 这不是契约通过, 是工具压根没跑起来, 必须避免被当成"绿"。
        _env = dict(os.environ)
        _pp = _env.get("PYTHONPATH", "")
        _env["PYTHONPATH"] = (_PROC + os.pathsep + _ROOT + os.pathsep + _pp).strip(os.pathsep)
        p = subprocess.run(
            ["lint-imports"], cwd=_ROOT, timeout=600, env=_env,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        out = p.stdout.decode("utf-8", "replace")
    except FileNotFoundError:
        return {"ok": False, "kept": 0, "broken": 0, "contracts": [],
                "error": "lint-imports 未安装 (pip install import-linter)"}
    except subprocess.TimeoutExpired:
        return {"ok": False, "kept": 0, "broken": 0, "contracts": [], "error": "超时"}

    contracts = [{"name": m.group(1).strip(), "state": m.group(2)}
                 for m in CONTRACT_RE.finditer(out)]
    mk = KEPT_RE.search(out)
    kept = int(mk.group(1)) if mk else sum(1 for c in contracts if c["state"] == "KEPT")
    broken = int(mk.group(2)) if mk else sum(1 for c in contracts if c["state"] == "BROKEN")
    if kept + broken == 0:
        # 一个契约都没解析到 = 工具没真正执行(未安装/路径错/配置空), 不能当成"零违规"。
        return {"ok": False, "kept": 0, "broken": 0, "contracts": [],
                "error": "未解析到任何契约, 工具可能未真正执行: " + out.strip()[-300:],
                "raw_tail": out[-800:]}
    return {"ok": broken == 0, "kept": kept, "broken": broken,
            "contracts": contracts, "error": None, "raw_tail": out[-800:]}


def self_check():
    """自检 3 项：配置在、CLI 能跑、解析出契约结果。"""
    ok = True

    def _chk(name, cond):
        nonlocal ok
        print(("PASS " if cond else "FAIL ") + name)
        ok = ok and bool(cond)

    _chk("配置文件存在 (.importlinter)", os.path.exists(CONFIG))
    r = run()
    _chk("lint-imports 可执行且无致命错误", not r.get("error"))
    _chk("解析出契约结果 (kept>0 且 broken=0)", r["kept"] > 0 and r["broken"] == 0)
    return ok


def main():
    if "--self-check" in sys.argv:
        return 0 if self_check() else 1
    r = run()
    if "--json" in sys.argv:
        print(json.dumps(r, ensure_ascii=False, indent=2))
        return 0 if r["ok"] else 1
    print("分层契约门禁 (import-linter)  配置: .importlinter")
    if r.get("error"):
        print("  ERROR: %s" % r["error"])
        return 1
    print("  Contracts: %d kept, %d broken." % (r["kept"], r["broken"]))
    for c in r["contracts"]:
        print("    [%-6s] %s" % (c["state"], c["name"]))
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
