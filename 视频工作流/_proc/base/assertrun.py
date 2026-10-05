# 契约: proc/base/assertrun
#   一句话: 统一断言执行器——各模块 self_check 改写为"计算抽 helper + 数据表 chk"
#   完整契约见 base/__init__.py
#   判据口径依据:
#     - xUnit Test Patterns / JUnit: assertion 应带 message，失败时定位到具体断言
#       而非"文件里某一行炸了"（Assertion Roulette 反模式）
#     - pytest 参数化: 用例与执行分离，同一执行器可跑任意模块的断言表
#     - Google Truth / assertj: 断言表返回 (name, pass, info) 三元组便于汇总

"""统一断言执行器。

背景（债务来源）:
  各模块 self_check 原本是"一串裸 assert + 计算过程混写"，天然偏长，
  触发 R3 函数过长。8 个模块因此挂债务，清零条件写明"统一执行器落地后清零"。

本模块提供 Checker：把"算"与"判"分离——
  算的过程抽成模块内 helper（或 inline 在 self_check 前段），
  判的部分变成一行 chk(name, cond, info)，执行器统一打印与汇总。

用法::

    from tools.assertrun import Checker

    def self_check():
        c = Checker("turn")            # 模块名，用于表头
        c.chk("90° 应用基础速率", abs(turn_speed(90) - BASE) < 1e-9)
        c.chk("180° 峰值不超生理上限", pk <= LIMIT, "%.1f°/s" % pk)
        c.note("180°=%.3fs  90°=%.3fs" % (d180, d90))   # 纯信息行
        return c.report()              # 全通过返回 True

report() 返回 bool，与旧 self_check 的返回语义兼容（多数返回 True/ok）。
少数模块旧返回值是 (passed, total) 元组或 list，改造时统一为 bool。
"""

from __future__ import annotations


class Checker(object):
    """断言收集 + 统一打印 + 汇总判定。"""

    def __init__(self, mod="", width=62):
        self.mod = mod
        self.width = width
        self.rows = []          # [(name, passed, info)]
        self.notes = []         # [str]

    # ---- 断言 ----------------------------------------------------
    def chk(self, name, cond, info=""):
        """登记一条断言。cond 可为 bool 或返回 bool 的可调用对象。"""
        try:
            v = cond() if callable(cond) and not isinstance(cond, (bool, int)) else cond
        except Exception as e:                      # 断言自身炸了 → 记 FAIL 不吞
            self.rows.append((name, False, "EXC %s: %s" % (type(e).__name__, e)))
            return False
        v = bool(v)
        self.rows.append((name, v, "" if info is None else str(info)))
        return v

    # 语义别名（读起来更顺）
    ok = chk
    assert_ = chk

    def note(self, text):
        """纯信息行，不参与判定，跟在断言表后面打印。"""
        self.notes.append(str(text))
        return self

    # ---- 汇总 ----------------------------------------------------
    @property
    def failed(self):
        return [r for r in self.rows if not r[1]]

    @property
    def passed(self):
        return sum(1 for r in self.rows if r[1])

    @property
    def total(self):
        return len(self.rows)

    def report(self, verbose=True):
        """打印断言表，返回 bool（全通过 True）。"""
        if verbose:
            bar = "-" * self.width
            print(bar)
            if self.mod:
                print("  %s 自检" % self.mod)
                print(bar)
            for name, ok_, info in self.rows:
                print("  %-26s %s %s" % (name, "PASS" if ok_ else "FAIL", info))
            for t in self.notes:
                print("  %s" % t)
            print(bar)
            print("  SELF_CHECK: %s (%s)  %d/%d"
                  % ("PASS" if not self.failed else "FAIL",
                     self.mod or "-", self.passed, self.total))
        return not self.failed


def run(mod, fn, verbose=True):
    """跑一个模块的 self_check 并兜住异常（异常判 FAIL，不静默通过）。"""
    try:
        return bool(fn())
    except Exception as e:
        print("  SELF_CHECK: FAIL (%s)  EXC %s: %s" % (mod, type(e).__name__, e))
        return False


if __name__ == "__main__":
    # 自检：执行器自身的牙齿——失败必须真失败，异常必须真失败
    c = Checker("assertrun")
    c.chk("通过项计为 PASS", True)
    c.chk("失败项计为 FAIL", False, "这是故意造的坏值")
    c.chk("异常项计为 FAIL 不吞", lambda: (_ for _ in ()).throw(ValueError("x")))
    c.chk("可调用对象被求值", lambda: 1 + 1 == 2)
    bad = c.report(verbose=False)
    assert bad is False, "有失败项时 report() 必须返回 False"
    assert c.passed == 2 and c.total == 4, (c.passed, c.total)
    assert len(c.failed) == 2, c.failed
    assert c.failed[0][0] == "失败项计为 FAIL"
    assert "EXC" in c.failed[1][2], c.failed[1]

    g = Checker("assertrun")
    g.chk("全通过", True)
    g.chk("也全通过", True)
    assert g.report(verbose=False) is True
    assert run("assertrun", lambda: True) is True
    assert run("assertrun", lambda: (_ for _ in ()).throw(RuntimeError("boom"))) is False
    print("  assertrun: 失败/异常均真 FAIL，通过均真 PASS")
    print("SELF_CHECK: PASS (assertrun)")
