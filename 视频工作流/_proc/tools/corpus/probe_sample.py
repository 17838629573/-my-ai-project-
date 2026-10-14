# 契约: proc/tools/corpus/probe_sample
#   一句话: smell 规则的探针样本源码——一段刻意写满异味的合规外形代码
#   完整契约见 tools/__init__.py
#   依据: NASA/JPL「无断言的自检等于没自检」；
#         变异测试惯例：样本与判定分离，规则改动不必动样本。
#   输入: 无
#   输出: SELF_SAMPLE(str) 可直接落盘的 Python 源码
#   依赖: 无（纯数据）
#   约束: 覆盖 S01/S02/S03/S04/S05/S08 各一；S06/S07 不进此样本
#         （硬编码路径与浮点相等会与其余规则互相污染命中判定）
#   校验入口: python3 tools/scan/smell.py --self-check
# -*- coding: utf-8 -*-
"""规则探针样本 —— 纯数据，与驱动分离。

为什么写成多行三引号而不是转义单行:
  转义版无法人读、改一处要数半天 \\n，且会让 R2 有效代码行判成 0（空壳）。
"""

import io
import os

SELF_SAMPLE = '''\
# 契约: proc/_smell_probe
# -*- coding: utf-8 -*-
import math


def f(xs=[]):
    try:
        return 1 / 0
    except Exception:
        pass


def g(a, b):
    return a / r


def self_check():
    if True:
        return []
    out = []
    out.append(("t", True))
    out.append(("big", abs(math.pi - 3.14) < 1e6))
    out.append(("eq", f([]) == 1.0))
    return out
'''


def write_to(path):
    """把样本写到 path，返回路径。

    为什么由数据模块自己落盘: 样本的持久化与转义细节只应有一处知道，
    驱动层不必关心它是单行转义串还是多行三引号。
    """
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(SELF_SAMPLE)
    return path


def probe_path(root=None):
    """探针文件的落盘位置（默认 _proc 下）。"""
    root = root or os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    return os.path.join(root, "_smell_probe.py")
