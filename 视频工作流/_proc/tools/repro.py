#   依据: gosec 要求 rule-scoped #nosec + justification；
#         Microsoft C++ 支持 gsl::suppress(rule-id, justification)；
#         semgrep 要求 // nosemgrep + justification；
#         import-linter 用 unmatched_ignore_imports_alerting="error" 防过期豁免；
#         LDRA 建议「简化复现」提取最小测试文件验证误报。
#         本工具比业界更强：只写理由文字不算数，必须给**可执行**的最小复现，
#         跑得通才算豁免成立，跑不通一律按真问题处理。
# -*- coding: utf-8 -*-
"""R17 豁免验证 —— 「假阳性」必须附最小复现，做不到按真问题处理。

铁律原文：
    任何被判定为"假阳性"的报错，必须附一个最小复现——
    能证明这条报错在正确配置下不会触发。
    做不到复现的，一律按真问题处理。

用法：
    python3 tools/repro.py            # 全量验证豁免登记册
    python3 tools/repro.py --add ID   # 交互式登记一条（含复现脚本）

登记册格式 suppress.json：
    [{
      "id":     "S1",
      "rule":   "R1 逆向依赖",
      "target": "tools -> motion",
      "reason": "tools 层已登记进 ALLOW，属合法跨层调用",
      "repro":  "python 代码字符串：制造报错 -> 修复 -> 报错消失",
      "expect": "absent"      # 正确配置下该报错 absent / present
    }]

判定：
    PASS  repro 跑通，且实测与 expect 一致 → 豁免成立
    FAIL  repro 跑不通，或实测与 expect 不符 → 按真问题处理
"""

import json
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROC = os.path.dirname(_HERE)
_SUPPRESS = os.path.join(_HERE, "suppress.json")


def _load():
    if not os.path.exists(_SUPPRESS):
        return []
    with open(_SUPPRESS, encoding="utf-8") as f:
        return json.load(f)


def _save(items):
    with open(_SUPPRESS, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)


def verify(item, timeout=120):
    """跑一条豁免的复现脚本。

    repro 脚本约定：
      向 stdout 打印一行结果，形如 "OBSERVED=absent" 或 "OBSERVED=present"。
    返回 (ok, detail)。
    """
    code = item.get("repro", "")
    if not code.strip():
        return False, "无复现脚本 —— 按铁律判定为真问题"
    env = dict(os.environ)
    env["PYTHONPATH"] = _PROC + os.pathsep + env.get("PYTHONPATH", "")
    try:
        r = subprocess.run([sys.executable, "-c", code],
                           capture_output=True, text=True,
                           timeout=timeout, cwd=_PROC, env=env)
    except subprocess.TimeoutExpired:
        return False, f"复现超时 {timeout}s"
    if r.returncode != 0:
        tail = (r.stderr or "").strip().splitlines()[-1:] or [""]
        return False, "复现脚本崩溃: " + tail[0]
    out = r.stdout or ""
    obs = None
    for line in out.splitlines():
        if line.startswith("OBSERVED="):
            obs = line.split("=", 1)[1].strip()
    if obs is None:
        return False, "复现未输出 OBSERVED=absent|present"
    exp = item.get("expect", "absent")
    if obs != exp:
        return False, f"实测 {obs} != 声明 {exp} —— 豁免不成立"
    return True, f"实测 {obs} == 声明 {exp}"


def self_check():
    """自检：内置三个探针，正反两面都要对。"""
    ok = 0
    tot = 0

    # 探针1：有 repro 且 expect 一致 → PASS
    tot += 1
    r = verify({"repro": "print('OBSERVED=absent')", "expect": "absent"})
    ok += r[0]
    print(f"  探针1 复现跑通且一致          {'PASS' if r[0] else 'FAIL'}  {r[1]}")

    # 探针2：无 repro → 必须 FAIL（不能豁免）
    tot += 1
    r = verify({"repro": "   ", "expect": "absent"})
    ok += (not r[0])
    print(f"  探针2 无复现必须判 FAIL       {'PASS' if not r[0] else 'FAIL'}  {r[1]}")

    # 探针3：实测与声明不符 → 必须 FAIL
    tot += 1
    r = verify({"repro": "print('OBSERVED=present')", "expect": "absent"})
    ok += (not r[0])
    print(f"  探针3 实测≠声明必须判 FAIL    {'PASS' if not r[0] else 'FAIL'}  {r[1]}")

    # 探针4：脚本崩溃 → 必须 FAIL
    tot += 1
    r = verify({"repro": "raise RuntimeError('boom')", "expect": "absent"})
    ok += (not r[0])
    print(f"  探针4 复现崩溃必须判 FAIL     {'PASS' if not r[0] else 'FAIL'}")

    print(f"\n  self_check: {ok}/{tot}")
    return ok == tot


def main():
    items = _load()
    if "--self-check" in sys.argv:
        return 0 if self_check() else 1
    if not items:
        print("豁免登记册为空 —— 没有待验证的「假阳性」")
        return 0
    print(f"豁免登记册 {len(items)} 条\n")
    bad = 0
    for it in items:
        ok, detail = verify(it)
        flag = "PASS" if ok else "FAIL"
        print(f"  [{flag}] {it.get('id','?')}  {it.get('rule','')}  "
              f"{it.get('target','')}")
        print(f"         {detail}")
        if not ok:
            bad += 1
            print(f"         理由: {it.get('reason','')}")
            print("         → 按铁律判定为真问题，不得豁免")
    print(f"\n成立 {len(items)-bad}  按真问题处理 {bad}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
