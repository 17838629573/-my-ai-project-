# 契约: proc/tools/scan
#   一句话: 源码扫描器——跨项目克隆检测、能力出处 AST 扫描
#   完整契约见 tools/__init__.py
#   依据: 两者皆为"读源码找模式"的扫描器，与跑测/测量无关，故与工具主体分层；
#         归入子包后 tools 直接成员回到 20 以内（R4 上帝包）。
#   输入: 项目根目录
#   输出: clone.main() 克隆报告；capsrc 无出处能力清单
#   依赖: clone 无外部依赖；capsrc 被 check.py 引用
#   约束: 扫描结果不写回源码；只读
#   校验入口: python3 tools/scan/clone.py / python3 tools/scan/capsrc.py
# -*- coding: utf-8 -*-
"""源码扫描层 —— 与工具主体分离。

为什么分文件/分包:
  tools 直接成员曾达 21（>20 上限）。clone 与 capsrc 同属"扫描源码"职责，
  语义内聚，归入本包后 tools 归位，且两者仍可独立执行。
"""
