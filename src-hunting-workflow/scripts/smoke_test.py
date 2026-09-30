#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
smoke_test.py —— 全命令冒烟测试（上传前必跑）

动机：连续三轮升级都引入新 bug，每次都是外部 Agent 实跑才抓到。
根因：新增脚本只跑了单一命令，没跑全部子命令。

纪律：任何新增/修改脚本逻辑，必须 `python3 smoke_test.py` 全绿再上传。
"""

import os
import subprocess
import sys
import tempfile
import json

HERE = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable

# 每个脚本要跑的子命令（尽力覆盖所有入口）
CASES = [
    ("src_gate.py", [
        ["rules"],
        ["rate", "--platform", "atmail", "--rps", "20"],
        ["rate", "--platform", "atmail"],
        ["rate", "--platform", "openbugbounty"],
        ["quota"],
        ["quota", "--add", "1"],
        ["preflight"],
        ["preflight", "--scope", "--rate", "--cred", "--interactive"],
        # ★ check 是历史上出 bug 最多的命令（缺 --add / dest 别名 / 静默吞异常）
        ["check"],
        ["check", "--platform", "atmail", "--rps", "3"],
        ["check", "--add", "1", "--scope"],
        ["intel"],
        ["intel", "--epss", "0.93723", "--kev", "--cve", "CVE-2026-21643"],
        ["intel", "--epss", "0.1"],
        ["evidence"],
        ["merge"],
    ]),
    ("src_calibrate.py", [
        ["steps"],
        ["demo"],
        # ★ 混合样本回归：知名 + 非知名 + 零命中场景
        ["load", "--file", "@MIX@"],
        ["load", "--file", "@MIX@", "--require-nonfamous"],
    ]),
    ("src_stack.py", [
        ["upgrade"],
        ["upgrade", "--lang", "python"],
        ["upgrade", "--lang", "java"],
        ["upgrade", "--lang", "go"],
        ["upgrade", "--lang", "js"],
        ["arch"],
        ["arch", "--cat", "AI/自动化"],
        ["arch", "--cat", "建站/CMS"],
        ["frame"],
        ["proto"],
        ["lang", "--lang", "python"],
        ["map", "--family", "declared_boundary"],
        ["families"],
    ]),
    ("src_variant.py", [
        ["dims"],
        ["demo", "--top", "6"],
    ]),
    ("src_intel.py", [
        ["demo", "--top", "5"],
    ]),
    ("src_rules.py", [
        ["stats"],
    ]),
    ("src_scout.py", [
        ["help"],
    ]),
    ("src_patchdiff.py", [
        ["help"],
    ]),
    ("src_gitpatch.py", [
        ["help"],
    ]),
    ("run.py", [
        ["help"],
    ]),
]

# 混合样本（1 知名 + 4 非知名 + 覆盖不同步骤）
MIX = [
    {"title": "微软 ALPC 提权", "vendor": "microsoft",
     "vuln_class": "权限提升", "root_cause": "缺失校验"},
    {"title": "某 K8s 组件未授权 API", "vendor": "社区自研",
     "vuln_class": "未授权", "root_cause": "缺失鉴权", "source": "GitHub Advisory"},
    {"title": "小众模型服务 SSRF", "vendor": "小众",
     "vuln_class": "SSRF", "root_cause": "出站未校验"},
    {"title": "闭源工控硬编码凭证", "vendor": "闭源",
     "vuln_class": "默认口令", "root_cause": "配置不当", "source": "闭源公告"},
    {"title": "DeepSeek MCP 未授权", "vendor": "DeepSeek",
     "vuln_class": "未授权访问", "root_cause": "默认无鉴权"},
    {"title": "n8n MCP 端点未授权", "vendor": "n8n",
     "vuln_class": "未授权", "root_cause": "默认配置"},
    {"title": "并发领券超领", "vendor": "某电商",
     "vuln_class": "逻辑漏洞", "root_cause": "并发竞态"},
]


def run(script, args, timeout=90):
    cmd = [PY, os.path.join(HERE, script)] + args
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                           cwd=HERE)
        return r.returncode, r.stdout.decode("utf8", "replace"), \
            r.stderr.decode("utf8", "replace")
    except subprocess.TimeoutExpired:
        return -1, "", "TIMEOUT"
    except Exception as e:
        return -2, "", str(e)


def main():
    tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False,
                                      encoding="utf-8")
    json.dump(MIX, tmp, ensure_ascii=False)
    tmp.close()

    total = ok = fail = 0
    fails = []
    print("=" * 74)
    print(" 全命令冒烟测试（上传前必跑）")
    print("=" * 74)
    for script, cases in CASES:
        if not os.path.exists(os.path.join(HERE, script)):
            print(f"\n[skip] {script} 不存在")
            continue
        print(f"\n── {script} ──")
        for args in cases:
            real = [tmp.name if a == "@MIX@" else a for a in args]
            total += 1
            rc, out, err = run(script, real)
            label = " ".join(args) or "(default)"
            # 判定：非 0 退出码、有 Traceback、或 stderr 未捕获异常
            bad = (rc not in (0, 1, 2)) or ("Traceback" in err) or \
                  ("Traceback" in out)
            if bad:
                fail += 1
                fails.append((script, label, rc, err[:200] or out[:200]))
                print(f"   [!!] {label}  rc={rc}")
                if err.strip():
                    print(f"        {err.strip()[:300]}")
            else:
                ok += 1
                print(f"   [OK] {label}")
    os.unlink(tmp.name)

    print("\n" + "=" * 74)
    print(f" 结果: {ok}/{total} 通过" + ("" if not fail else f"，{fail} 失败"))
    print("=" * 74)
    if fails:
        print("\n失败明细:")
        for s, l, rc, e in fails:
            print(f"\n  {s} :: {l}")
            print(f"    rc={rc}")
            print(f"    {e}")
        print("\n[x] 不许上传，先修")
        return 1
    print("\n[OK] 全绿，可以上传")
    return 0


if __name__ == "__main__":
    sys.exit(main())
