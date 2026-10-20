# 契约: proc/tools/faultlock
#   一句话: 缺陷基准装置：单实例锁 + canary 源码落盘，保证注入实验互不踩踏
#   完整契约见 tools/__init__.py
#   依据: flock/O_EXCL 单实例互斥；fsync 保证子进程读到已落盘内容
# -*- coding: utf-8 -*-
"""缺陷基准装置 —— 从 faultbench.py 拆出。

为什么单独成模块:
  这一段只负责「装置」——谁能跑（单实例锁）、canary 怎么落盘，
  与「缺陷判多少条」无关。抽出后 faultbench 回到 500 行模块红线内
  （实测 518 → 459），装置逻辑也更容易单独自检。
"""
import contextlib
import io
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROC = os.path.dirname(_HERE)


CANARY = os.path.join(_PROC, "_canary_faultbench.py")
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
