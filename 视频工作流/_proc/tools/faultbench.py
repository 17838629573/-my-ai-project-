# 契约: proc/tools/faultbench
#   一句话: 缺陷注入基准：注入已知代码缺陷，实测工具矩阵能否检出，量化召回率并暴露盲区
#   完整契约见 tools/__init__.py
#   依据: Mutation Testing(PIT/mutmut) 的存活率口径——注入的缺陷若未被检出即 SURVIVED，
#         每一条 SURVIVED 都是工具矩阵的盲区；
#         NASA/JPL 的“测试应能证明缺陷存在”要求测试套件自身也要被验证；
#         业界 fault injection benchmark(LFI/Chaos Engineering) 用注入验证可观测性。
# -*- coding: utf-8 -*-
"""R18 缺陷注入基准 —— 「工具能不能抓到代码里的问题」的实测答案。

为什么需要它:
  前面所有工具都在检查「代码写没写、结构对不对」，
  但没人验证过「真有 bug 时，这套工具能不能抓到」。
  没有这个基准，「测试全绿」跟「代码没问题」之间没有因果关系。

做法:
  1. 往 canary 文件注入一批 AI 写代码最常犯的缺陷（每类一个）
  2. 跑工具矩阵（静态 check.py + 动态实跑）
  3. 抓到 = KILLED，抓不到 = SURVIVED
  4. 召回率 = KILLED / 总数；SURVIVED 就是工具盲区，必须补工具

用法:
    python3 tools/faultbench.py            # 人读
    python3 tools/faultbench.py --json     # 机读
"""
import atexit
import contextlib
import io
import json
import os
import signal
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROC = os.path.dirname(_HERE)
if _PROC not in sys.path:
    sys.path.insert(0, _PROC)

CANARY = os.path.join(_PROC, "_canary_faultbench.py")

# 最近一次失败的原始报错，供 main/self_check 打印（裸 False 无从诊断）
_LAST_ERR = {"baseline": ""}

from tools.corpus import BASE, FAULTS



LOCK = os.path.join(_PROC, ".faultbench.lock")


def _acquire():
    """单实例锁：canary 是共享的单个文件，两个实例并发跑会互相覆盖。

    历史事故：上一轮实例被沙箱中断后仍在后台活着，新实例的 baseline()
    刚写完干净基线，就被旧实例的注入覆盖成带 os.sep 的版本，
    于是报"基准不可信 / 动态 False"——看起来像工具有病，实际是自己踩自己。
    """
    stale = False
    if os.path.exists(LOCK):
        try:
            with open(LOCK, "r", encoding="utf-8") as f:
                pid = int((f.read().strip() or "0"))
            if pid and pid != os.getpid():
                # 只认"确实在跑 faultbench"的 pid：os.kill(pid,0) 对任意
                # 存活进程都成功，pid 复用会把别的进程误判成并发实例，
                # 于是工具拒绝启动（锁看着像活的，实际没人持锁）。
                try:
                    with open("/proc/%d/cmdline" % pid, "rb") as cf:
                        cmd = cf.read().decode("utf-8", "replace")
                except OSError:
                    cmd = ""
                if "faultbench" in cmd:
                    return False, pid
                stale = True
        except (OSError, ValueError):
            stale = True
        if stale:
            # 为什么用 suppress 而不是裸 except pass：
            # 陈旧锁要么已被抢占者删掉（FileNotFoundError），要么无权限（PermissionError）。
            # 两种情况都会在下方 os.open(O_EXCL) 处真实暴露并报错，
            # 因此这里不掩盖并发冲突——它掩盖不了。
            with contextlib.suppress(OSError):
                os.remove(LOCK)
    fd = os.open(LOCK, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()))
    return True, 0


def _release():
    # 同 _acquire：锁可能已被抢占者删除。真正的冲突在 _acquire 的 O_EXCL 暴露，
    # 这里 suppress 不会掩盖它。
    with contextlib.suppress(OSError):
        os.remove(LOCK)


def _write(src):
    """写入 canary 源码。

    必须显式 close + fsync：历史上写成 io.open(...).write(src)（无 close），
    缓冲区未落盘时子进程读到的是上一轮的旧内容，导致基线被判"不可信"，
    而单独重跑又通过 —— 典型的时隐时现假失败。
    """
    with io.open(CANARY, "w", encoding="utf-8") as fh:
        fh.write(src)
        fh.flush()
        os.fsync(fh.fileno())


def _run_check():
    """跑静态检查，返回 (问题数增量, 是否提到 canary)。

    超时返回 None 而非 0 —— 2026-10-11 修：
    历史上超时被返回 0，上层当成"工具没抓到"（SURVIVED），
    实际是"工具没跑完"。这违反铁律 1（UNVERIFIED ≠ PASS）：
    没验成就是没验成，不能冒充成"验过了、没抓到"。
    """
    try:
        p = subprocess.run(
            [sys.executable, "check.py",
             "--files=" + os.path.basename(CANARY)], cwd=_PROC,
            timeout=120, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT)
        out = p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return None, False
    # 只认 [R..] / [缺..] 这类问题行；INDEX 表格行含文件名但不是报错
    hit = 0
    for ln in out.splitlines():
        s = ln.strip()
        if not s.startswith("["):
            continue
        if s.startswith("[已知债务"):
            continue
        if "_canary" in s:
            hit += 1
    return hit, hit > 0


def _run_smell():
    """跑代码异味检查，返回命中 canary 的条数。"""
    try:
        p = subprocess.run([sys.executable, "tools/smell.py",
                            "--files=" + os.path.basename(CANARY)], cwd=_PROC,
                           timeout=300, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
        out = p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return None  # 超时≠零命中，见 _run_check 的说明
    return sum(1 for ln in out.splitlines()
               if ln.strip().startswith("[S") and "_canary" in ln)


def _run_complexity():
    """跑 lizard 圈复杂度/长度门禁，返回命中 canary 的条数。

    2026-10-10 补: R3(函数<=50行)已从 check.py 迁至 tools/complexity.py(lizard)。
    迁移时漏了在本基准里补这个探针，导致 F12 函数超长从 KILLED 变 SURVIVED，
    而基准仍自称"全绿"——工具换了，基准没跟着换，是静默失效。
    """
    try:
        p = subprocess.run([sys.executable, "tools/complexity.py",
                            "--files=" + os.path.basename(CANARY)], cwd=_PROC,
                           timeout=300, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT)
        out = p.stdout.decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return None  # 超时≠零命中，见 _run_check 的说明
    return sum(1 for ln in out.splitlines() if "_canary" in ln)


def _run_dynamic():
    """实跑 canary 的 self_check 与 import，返回 (ok, 错误信息)。"""
    try:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        p = subprocess.run(
            [sys.executable, "-B", "-c",
             "import _canary_faultbench as m; r=m.self_check(); "
             "assert all(v for _, v in r), 'self_check FAIL: %s' % r; "
             "print('OK')"],
            cwd=_PROC, timeout=60, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, env=env)
        out = p.stdout.decode("utf-8", "replace")
        return p.returncode == 0, out.strip()[-200:]
    except subprocess.TimeoutExpired:
        return False, "timeout"


def baseline():
    """干净基线的表现：必须全绿，否则基准本身不可信。

    返回 (静态命中数, 动态是否通过, 动态错误信息)；任一项超时返回 None 命中。
    2026-10-11 修：原实现只跑 check+complexity，而 _verdict_of 还跑 smell，
    基线口径比判定口径窄 —— 基线没验证 smell 是否干净，
    却允许"注入后 smell 命中"算作 killed。现三者口径统一。
    历史上动态失败被打印成裸 False，查不出原因，故必须带出原始报错。
    """
    _write(BASE)
    hit, _ = _run_check()
    sm = _run_smell()
    cx = _run_complexity()
    ok, msg = _run_dynamic()
    if hit is None or sm is None or cx is None:
        return None, ok, msg or "探针超时，基线不可信（未验成≠通过）"
    return hit + sm + cx, ok, msg


def _how_of(hit, sm, cx, dok):
    """判定由哪类工具抓到（用于人读输出归因）。"""
    if hit > 0:
        return "静态"
    if cx > 0:
        return "复杂度"
    if sm > 0:
        return "异味"
    return "动态" if not dok else ""


def _verdict_of(mutated, fid, cat, desc, base):
    """注入一个缺陷 → 判定它是否被工具抓到。

    mutated == base 说明注入器没改动源码（锚点与基线不匹配），此时必须判
    SURVIVED 并写明"注入器失效"，绝不能当成"工具盲区"。
    """
    if mutated == base:
        return {"id": fid, "cat": cat, "desc": desc, "killed": False,
                "how": "注入器失效",
                "detail": "注入未改动源码，锚点与基线不匹配"}
    _write(mutated)
    hit, _ = _run_check()
    sm = _run_smell()
    cx = _run_complexity()
    dok, dmsg = _run_dynamic()
    if hit is None or sm is None or cx is None:
        # 探针超时：既不能判 KILLED（没证据说抓到了），
        # 也不能判 SURVIVED（那等于宣称"验过了、工具是瞎的"）。
        return {"id": fid, "cat": cat, "desc": desc, "killed": False,
                "timeout": True, "how": "探针超时",
                "detail": "探针未跑完，结论无效（铁律1：未验成≠通过）"}
    return {"id": fid, "cat": cat, "desc": desc,
            "killed": (hit > 0) or sm > 0 or (cx > 0) or (not dok),
            "how": _how_of(hit, sm, cx, dok), "timeout": False,
            "detail": dmsg}


def residue():
    """磁盘残留：上一轮异常退出（超时/被杀）时 canary 没被回收。

    残留会被 check/smell/complexity 当成普通模块扫描，污染门禁结果，
    且它身上带着未回滚的注入缺陷（如 F05 的 *100），报出来全是假信号。
    历史事故：一次中断留下的残留带 F05，smell 报 S07 浮点相等，
    看起来像项目有新缺陷，实际是基准自己的垃圾没扫干净。
    """
    if not os.path.exists(CANARY):
        return {"exists": False, "bytes": 0, "injected": False}
    try:
        with open(CANARY, "r", encoding="utf-8") as f:
            s = f.read()
    except OSError:
        return {"exists": True, "bytes": 0, "injected": False}
    # 与 BASE 不同 = 带着未回滚的注入
    return {"exists": True, "bytes": len(s), "injected": s != BASE}


def _clean_residue():
    """开局先清残留：上一轮被杀/超时留下的 canary 带着未回滚的注入缺陷。

    为什么必须在 run() 里自动清而不是只报错：
    本工具在本环境经常跑不完（OOM/超时被杀），每次中断必留一个带缺陷的 canary，
    随后 smell/docsync/reach 把它当普通模块扫，报出一堆与项目无关的假信号
    （实测：S04 'os' 未绑定、INDEX 记录 64 行但文件不存在、孤立文件数 +1）。
    只报错不清理 = 污染会一路蔓延到 README 数字。
    """
    r = residue()
    if not r["exists"]:
        return 0
    n = 0
    # 为什么 suppress：文件可能已被抢先删掉（FileNotFoundError）或无权限；
    # 残留没清掉会在下一轮继续污染扫描，而"清不掉"这件事本身会在
    # residue() 里作为 exists=True 重新报出来，不会被这里吞掉。
    import glob
    for path in [CANARY, CANARY + "c"] + glob.glob(
            os.path.join(os.path.dirname(CANARY),
                         "__pycache__", "_canary_faultbench*.pyc")):
        with contextlib.suppress(OSError):
            os.remove(path)
            n += 1
    return n


def run(ids=None):
    """ids: 只跑指定缺陷（分批用）。

    为什么要分批：每条缺陷要跑 check/smell/complexity 三个全项目扫描，
    14 条 × 3 次超过了单批时限。历史上因此只能跑一半就超时，
    而超时又被当成"工具没抓到"，报出的召回率是假的。
    现在超时如实报 TIMEOUT，配合 ids 分批可跑完全部。
    """
    # canary 必须无条件回收：中途异常/被中断/超时都会留下残留文件，
    # 残留会污染 baseline/complexity 的扫描结果（历史上因此误报过一次）
    _clean_residue()
    try:
        bh, bok, bmsg = baseline()
        if bh != 0 or not bok:
            _LAST_ERR["baseline"] = bmsg
            return None, bh, bok
        rows = []
        for fid, cat, desc, inject in FAULTS:
            if ids and fid not in ids:
                continue
            rows.append(_verdict_of(inject(BASE), fid, cat, desc, BASE))
        return rows, bh, bok
    finally:
        _cleanup()


def _recall_asserts(rows, k):
    """召回相关的三条判据。

    2026-10-11 修：原第三条写成 `len(valid)==len(rows) or k<=len(valid)`，
    后半支在正常路径下恒真，断言等于没有——与抽象包里 `assert blocking >= 0`
    是同一类"用恒真式冒充验证"。换成"KILLED 不得来自超时样本"，
    这条才真能抓到"没跑完却算抓到"的错。
    """
    return [
        ("至少抓到一半缺陷", k >= len(rows) / 2),
        ("每条缺陷都有判定结果",
         all(r.get("timeout") or r["how"] for r in rows)),
        ("KILLED 全部来自未超时样本（超时≠抓到，铁律1）",
         all((not r["killed"]) or (not r.get("timeout")) for r in rows)),
    ]


def self_check():
    """自检：基准本身必须可信——干净基线全绿、且能抓到大多数人造缺陷。"""
    out = []
    # 先看残留：必须在 run() 之前查，run() 的 finally 会把 canary 清掉
    rs = residue()
    out.append(("无残留 canary（上一轮异常退出）",
                not rs["exists"] and not rs["injected"]))
    rows, bh, bok = run()
    out.append(("基线干净无缺陷", rows is not None and bh == 0 and bok))
    if rows:
        k = sum(1 for r in rows if r["killed"])
        out.extend(_recall_asserts(rows, k))
    _cleanup()
    return out


def _cleanup():
    if os.path.exists(CANARY):
        os.remove(CANARY)
    # 陈旧字节码会让"文件已改写"在子进程里不生效，必须一并清除
    for d in ("__pycache__",):
        pc = os.path.join(_PROC, d, "_canary_faultbench.cpython-310.pyc")
        if os.path.exists(pc):
            os.remove(pc)
    _release()


# 双保险：进程正常退出/异常退出都回收 canary
atexit.register(_cleanup)


def _on_signal(signum, _frame):
    """被 timeout / Ctrl-C 杀掉时 atexit 不会跑，锁和 canary 都会残留。

    残留的锁会让后续实例误以为有并发而拒绝启动，残留的 canary 会被
    check/smell 当成普通模块扫出假缺陷 —— 两者都曾真实发生过。
    """
    _cleanup()
    sys.exit(128 + signum)


for _sig in (getattr(signal, "SIGTERM", None), getattr(signal, "SIGINT", None)):
    if _sig is not None:
        # 为什么 suppress：非主线程注册 signal 必然抛 ValueError，属环境限制不是故障；
        # 且 atexit 钩子仍然生效，canary 照样回收，不掩盖回收失败。
        with contextlib.suppress(ValueError, OSError):
            signal.signal(_sig, _on_signal)


def _m_json(rows, killed, total):
    """--json 输出。"""
    print(json.dumps({"total": total, "killed": killed,
                      "recall": round(killed / total, 3),
                      "rows": rows}, ensure_ascii=False, indent=2))


def _row_flag(r):
    """单条缺陷的状态标记。"""
    if r.get("timeout"):
        return "TIMEOUT"
    return "KILLED" if r["killed"] else "SURVIVED"


def _m_blind(rows, total):
    """盲区清单 + 超时提示（超时项结论无效，不计入口径）。"""
    valid = [r for r in rows if not r.get("timeout")]
    if len(valid) != total:
        print("\u26a0 其中 %d 条探针超时，结论无效，未计入口径（铁律1）"
              % (total - len(valid)))
    surv = [r for r in rows if not r["killed"] and not r.get("timeout")]
    if not surv:
        return
    print("盲区清单:")
    for r in surv:
        print("    %s %s \u2014\u2014 %s" % (r["id"], r["cat"], r["desc"]))


def _m_human(rows, killed, total):
    """人读输出：逐条 KILLED/SURVIVED，末尾列盲区清单。"""
    print("=" * 66)
    print("R18 缺陷注入基准 \u2014\u2014 工具矩阵的检错召回率")
    print("=" * 66)
    for r in rows:
        print("  [%s] %s %-6s %-32s %s" %
              (_row_flag(r), r["id"], r["cat"], r["desc"], r["how"] or "\u2014"))
    print("-" * 66)
    print("召回率 %d/%d = %.0f%%   (SURVIVED = 工具盲区，须补工具)" %
          (killed, total, 100.0 * killed / total))
    _m_blind(rows, total)


def _parse_ids(argv):
    """解析 --ids=F01,F02（不传则跑全部）。"""
    for a in argv:
        if a.startswith("--ids="):
            return [s.strip() for s in a.split("=", 1)[1].split(",") if s.strip()]
    return None


def main(argv):
    ok, pid = _acquire()
    if not ok:
        print("已有 faultbench 实例在运行（pid=%d），拒绝并发启动。" % pid)
        print("canary 是共享单文件，并发写会互相覆盖导致假失败。")
        print("先结束旧实例，或确认其已死后删除 %s" % LOCK)
        return 2
    rows, bh, bok = run(ids=_parse_ids(argv))
    if rows is None:
        # bh 可能是 None（探针超时），不能按 %d 格式化，否则 TypeError 掩盖真正的原因
        print("基准不可信：干净基线命中 %s / 动态 %s" %
              ("未验成(探针超时)" if bh is None else "%d 条" % bh, bok))
        if _LAST_ERR["baseline"]:
            print("动态检查原始报错：%s" % _LAST_ERR["baseline"])
        _cleanup()
        return 1
    killed = sum(1 for r in rows if r["killed"])
    total = len(rows)
    if "--json" in argv:
        _m_json(rows, killed, total)
    else:
        _m_human(rows, killed, total)
    _cleanup()
    return 0 if killed == total else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
