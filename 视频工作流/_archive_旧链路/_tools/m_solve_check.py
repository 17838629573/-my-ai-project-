#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SOLVE/check —— 中模块 facade（组合层）

小模块: _chk_base, _chk_physics, _chk_chain, _chk_assemble, _chk_survey, _chk_motion, _chk_multi, _chk_sheet, _chk_reuse, _chk_pack, solver_check

作用：
  ① 一键跑组内全部自检（subprocess 逐个执行，**不 import** —— 组内含
     top-level 副作用的脚本，import 会炸）
  ② 契约导航：改代码只读 contracts/SOLVE.check.md，不读组内全部源码

契约: contracts/SOLVE.check.md
"""
import os
import subprocess
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 工作流根（本工具在 _tools/）
MODULES = ("_chk_base", "_chk_physics", "_chk_chain", "_chk_assemble", "_chk_survey", "_chk_motion", "_chk_multi", "_chk_sheet", "_chk_reuse", "_chk_pack", "solver_check")


def self_check(timeout=300):
    """聚合跑组内每个小模块的自检。返回 bool。"""
    ok = True
    for m in MODULES:
        p = os.path.join(BASE, m + ".py")
        if not os.path.exists(p):
            print(f"  FAIL {m}  文件缺失")
            ok = False
            continue
        try:
            r = subprocess.run([sys.executable, p], cwd=BASE,
                               capture_output=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            print(f"  FAIL {m}  超时 {timeout}s")
            ok = False
            continue
        out = (r.stdout + r.stderr).decode("utf-8", "replace").strip().splitlines()
        tail = out[-1][:70] if out else "(无输出)"
        print(f"  {'PASS' if r.returncode == 0 else 'FAIL'} {m}  {tail}")
        ok = ok and (r.returncode == 0)
    print(f"  -> {len(MODULES)} 项 {'PASS' if ok else 'FAIL'}  [SOLVE/check]")
    return ok


if __name__ == "__main__":
    sys.exit(0 if self_check() else 1)
