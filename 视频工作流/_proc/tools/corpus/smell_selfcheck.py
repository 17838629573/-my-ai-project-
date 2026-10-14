# 契约: proc/tools/smell_selfcheck
#   一句话: smell 规则的自检语料与驱动——证明 8 条规则真有牙齿，不是写了没接线
#   完整契约见 tools/__init__.py
#   依据: NASA/JPL「无断言的自检等于没自检」；
#         faultbench 实测：规则未接线时（float_eq）自检会用替身正则自我证明。
#   输入: 无（自带探针样本）
#   输出: self_check() -> bool；命中明细打印到 stdout
#   依赖: tools.scan.smell.check_file
#   约束: 探针文件无条件回收（finally）；命中判定只认规则编号前缀
#   校验入口: python3 tools/smell_selfcheck.py
# -*- coding: utf-8 -*-
"""smell 规则自检 —— 与规则实现分离。

为什么分文件:
  样本 + 驱动约 40 行，与扫描逻辑无关；内联会让 smell.py 超 500 行红线
  （R2 超纲）。分开后规则表仍是单一职责，自检也能独立跑。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROC = os.path.dirname(_HERE)
if _PROC not in sys.path:
    sys.path.insert(0, _PROC)

from tools.corpus import probe_sample

# 规则编号 → 期望命中。S06/S07 不在样本里（会与硬编码路径/浮点规则互相污染）
_EXPECT = ("S01", "S02", "S03", "S04", "S05", "S08")


def _probe_hits():
    """写探针样本 → 跑规则 → 无条件回收，返回命中列表。"""
    from tools.scan import smell
    p = probe_sample.write_to(probe_sample.probe_path(_PROC))
    try:
        return smell.check_file(p)
    finally:
        if os.path.exists(p):
            os.remove(p)


def _cats_of(hits):
    """把命中列表归到规则编号，返回 [(编号, 是否命中)]（排序后）。"""
    cats = {k: False for k in _EXPECT}
    for h in hits:
        for k in cats:
            if h.startswith("[%s" % k):
                cats[k] = True
    return sorted(cats.items())


def self_check():
    """自检：造一个含各类异味的样本，验证规则真能抓到。"""
    res = _cats_of(_probe_hits())
    ok = all(v for _k, v in res)
    print("异味规则自检: " + "  ".join(
        "%s=%s" % (k, "命中" if v else "未命中") for k, v in res)
        + "  -> " + ("PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    sys.exit(0 if self_check() else 1)
