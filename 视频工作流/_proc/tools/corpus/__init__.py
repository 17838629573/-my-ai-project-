# 契约: proc/tools/corpus
#   一句话: 工具的语料与自检样本——缺陷注入定义、规则探针样本
#   完整契约见 tools/__init__.py
#   依据: 变异测试惯例（缺陷语料与判定逻辑分离）；
#         NASA/JPL「无断言的自检等于没自检」。
#   输入: 无
#   输出: faultcorpus.BASE/FAULTS；smell_selfcheck.self_check()
#   依赖: faultcorpus 无依赖；smell_selfcheck 依赖 tools.smell.check_file
#   约束: 注入器为纯函数 src->new_src；探针文件无条件回收
#   校验入口: python3 tools/smell.py --self-check
# -*- coding: utf-8 -*-
"""语料层 —— 与跑测/扫描逻辑分离。

为什么单独成包:
  语料是数据不是逻辑。混在工具里会让工具文件超 500 行（R2 超纲），
  也让 tools 包条目超 20（R4 上帝包）。
"""
from . import faultcorpus, probe_sample, smell_selfcheck
from .faultcorpus import BASE, FAULTS
from .probe_sample import SELF_SAMPLE

__all__ = ["faultcorpus", "probe_sample", "smell_selfcheck",
           "BASE", "FAULTS", "SELF_SAMPLE"]
