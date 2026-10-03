#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""_split_plan.py —— 超大模块拆分方案（数据驱动）"""

SOLVER = {
    "file": "solver.py", "lines": 1173, "defs": 29,
    "big_spans": [
        ("solve", 329, 501, 172),
        ("draw_sheet", 895, 967, 72),
        ("sheet_plan", 821, 891, 70),
        ("probe_check", 167, 232, 65),
        ("self_check", 1019, 1081, 62),
        ("chain_response_multi", 539, 595, 56),
    ],
    "target": {
        "_solver_core.py":      "solve + run_spec + 物性查表 (~330)",
        "_solver_sheet.py":     "sheet_plan + draw_sheet + 容纳性 (~260)",
        "_solver_probe.py":     "probe_check 墙顶/地平线探测 (~120)",
        "_solver_reuse.py":     "reuse_plan + _reuse_for (~130)",
        "_solver_selfcheck.py": "self_check (62行, 纯断言)",
        "solver.py":            "facade 重导出 (~60)",
    },
}

SYSTEMS = {
    "file": "systems.py", "lines": 670, "defs": 16,
    "big_spans": [("self_check", 553, 664, 111)],
    "target": {
        "_systems_core.py":        "更新循环",
        "_systems_io.py":          "字幕 RGBA / 图像 IO",
        "_systems_selfcheck.py":   "self_check 111行",
        "systems.py":              "facade",
    },
}

POSE = {
    "file": "pose.py", "lines": 420, "defs": 15,
    "big_spans": [("self_check", 288, 415, 127)],
    "target": {
        "pose.py":               "fk/ik/foot_target/solve",
        "_pose_selfcheck.py":    "self_check + _scan_hardcode",
    },
}

TODO = [
    "1. _solver_probe.py   (无依赖, 先拆)",
    "2. _solver_sheet.py   (依赖 _common, _px)",
    "3. _solver_reuse.py   (依赖 _audit_dup)",
    "4. _solver_core.py    (依赖上述)",
    "5. solver.py -> facade (保留 __all__)",
    "6. _systems_selfcheck.py",
    "7. _pose_selfcheck.py",
    "8. 门禁 validate + 五族回归",
]

if __name__ == "__main__":
    import json
    print(json.dumps({"SOLVER": SOLVER, "SYSTEMS": SYSTEMS, "POSE": POSE, "TODO": TODO}, ensure_ascii=False, indent=2))
