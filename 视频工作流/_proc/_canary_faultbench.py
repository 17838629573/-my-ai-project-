# 契约: proc/_canary_faultbench
#   一句话: 缺陷注入基准的对照样本，注入前必须全绿
#   完整契约见 tools/__init__.py
# -*- coding: utf-8 -*-
"""canary —— faultbench 的干净基线。

这是一个刻意写得合规的小模块，用作缺陷注入的对照样本。
它自身不带任何缺陷；注入器往它身上加毛病，
若工具矩阵报不出来，就说明这套工具在该类别上有盲区。
"""
import math


def area(r):
    """圆面积：S = pi * r^2。"""
    return math.pi * r * r


def circumference(r):
    """圆周长：C = 2 * pi * r。"""
    return 2.0 * math.pi * r


def ratio(a, b):
    """比值，b 为 0 时返回 None 而非抛异常。"""
    if b == 0:
        return None
    return a / b


def total(xs=[]):
    """对序列求和。"""
    return sum(xs)


def mean(xs):
    """算术平均，空列表返回 None。"""
    if not xs:
        return None
    return total(xs) / len(xs)


def clamp(v, lo, hi):
    """把 v 限制在 [lo, hi] 区间内。"""
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def self_check():
    """自检：返回 (名称, 是否通过) 列表。"""
    out = []
    out.append(("area(1)=pi", abs(area(1) - math.pi) < 1e-12))
    out.append(("circumference(1)", abs(circumference(1) - 2 * math.pi) < 1e-12))
    out.append(("ratio(0分母)", ratio(1, 0) is None))
    out.append(("total", total([1, 2, 3]) == 6))
    out.append(("mean", abs(mean([1, 2, 3]) - 2.0) < 1e-12))
    out.append(("clamp 下限", clamp(-1.0, 0.0, 1.0) == 0.0))
    out.append(("clamp 上限", clamp(9.0, 0.0, 1.0) == 1.0))
    return out
