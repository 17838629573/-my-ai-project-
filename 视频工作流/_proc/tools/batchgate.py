# -*- coding: utf-8 -*-
"""契约: tools/batchgate.py
职责: 分批门检执行器。
输入: --ids 用例ID逗号串 / --all 全部 / --resume 续跑（跳过已完成）
输出: 逐条状态与耗时，写入 JSON 结果文件；单条超时记 TIMEOUT
边界: 不修改 CASES/EXEC；不判定阈值；只负责"能否跑完+耗时"
依据: 全量门检单批超环境时限(600s)无法完成，需可分段执行；
      pytest-timeout 的做法——单条超时必须显式记状态而非静默跳过
判定: TIMEOUT 用例即"跑不动"，须评估删除或优化，不得静默降级为 PASS
"""
import argparse
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROC = os.path.dirname(_HERE)
_ROOT = os.path.dirname(_PROC)
for _p in (_PROC, _ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DEFAULT_OUT = os.path.join(_ROOT, ".batchgate.json")


def _load():
    """导入 run_all 拿到 CASES 与 EXEC。"""
    import importlib
    sys.path.insert(0, _PROC)
    if "tests" not in sys.modules:
        import tests  # noqa: F401
    m = importlib.import_module("tests.run_all")
    return m.CASES, m.EXEC


def _one(cid, grp, name, need, cap, exec_map, H, B, timeout):
    """单条执行，带超时标记。返回 (状态, 实测文本, 耗时秒)。"""
    t0 = time.time()
    miss = [c for c in need if c not in cap]
    if miss:
        return ("STUB", "缺能力: " + ",".join(miss), time.time() - t0)
    if cid not in exec_map:
        return ("READY", "能力齐备，待写执行代码", time.time() - t0)
    try:
        import signal

        def _alarm(signum, frame):
            raise TimeoutError("case timeout %ss" % timeout)

        old = signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(int(timeout))
        try:
            checks, _extra = exec_map[cid]()
            txt, ok = H.report(checks)
            st = "PASS" if ok else "FAIL"
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
        return (st, txt, time.time() - t0)
    except TimeoutError as e:
        return ("TIMEOUT", str(e)[:70], time.time() - t0)
    except Exception as e:
        return ("ERROR", type(e).__name__ + ": " + str(e)[:70],
                time.time() - t0)


def run(ids=None, out=DEFAULT_OUT, timeout=120, resume=True, fresh=False):
    """执行一批用例，结果写 out。返回统计 dict。"""
    CASES, EXEC = _load()
    from tests import harness as H
    from motion import beat as B
    cap = set(getattr(B, "CAP_ALL", B.CAP).keys())

    done = {}
    if resume and not fresh and os.path.exists(out):
        try:
            done = json.load(open(out))
        except Exception:
            done = {}
    want = set(ids) if ids else {c[0] for c in CASES}
    todo = [c for c in CASES if c[0] in want
            and (not resume or c[0] not in done)]

    for cid, grp, name, need, crits, seed in todo:
        st, txt, dt = _one(cid, grp, name, need, cap, EXEC, H, B, timeout)
        done[cid] = {"id": cid, "grp": grp, "name": name, "status": st,
                     "detail": txt, "sec": round(dt, 2)}
        print("%-4s %-6s %6.1fs %s" % (cid, st, dt, txt[:60]))
        sys.stdout.flush()
        json.dump(done, open(out, "w"), ensure_ascii=False, indent=1)

    n = {}
    for v in done.values():
        n[v["status"]] = n.get(v["status"], 0) + 1
    slow = sorted((v for v in done.values()),
                  key=lambda v: -v["sec"])[:5]
    return {"total": len(done), "stat": n, "slowest": slow}


def self_check():
    C = []
    C.append(("模块可导入", True, ""))
    ids = run(ids=["A1"], out=os.path.join(_ROOT, ".bg_self.json"),
              timeout=60, resume=False, fresh=True)
    C.append(("单条可跑", ids["total"] == 1, str(ids["stat"])))
    r = run(ids=["__NOPE__"], out=os.path.join(_ROOT, ".bg_self.json"),
            timeout=5, resume=False, fresh=True)
    C.append(("未知ID不崩且不计入", r["total"] == 0, str(r["stat"])))
    return C


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", default="")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--self-check", action="store_true")
    a = ap.parse_args()
    if a.self_check:
        for nm, ok, ex in self_check():
            print("%-24s %s %s" % (nm, "OK" if ok else "FAIL", ex))
        sys.exit(0)
    ids = [s.strip() for s in a.ids.split(",") if s.strip()] or None
    r = run(ids=ids, out=a.out, timeout=a.timeout, fresh=a.fresh)
    print("\n" + json.dumps(r["stat"], ensure_ascii=False))
    print("最慢: " + ", ".join("%s %.1fs" % (v["id"], v["sec"])
                               for v in r["slowest"]))
    sys.exit(1 if (r["stat"].get("FAIL") or r["stat"].get("ERROR")
                   or r["stat"].get("TIMEOUT")) else 0)
