# 契约: proc/tools
#   一句话: 长期自检工具箱：契约检查(R0-R16)、判据变异(R13)、三表一致(R14)、有效帧率(R15)、豁免复现(R17)
#   完整契约见本文件「工具清单」
#   依据: gosec/semgrep/import-linter 的 suppress 需 rule-scoped + justification；
#         变异测试(PIT/mutmut)用存活率衡量检错力；eFPS 用重复帧判定真实动态。
# -*- coding: utf-8 -*-
"""proc.tools —— 长期自检工具箱（禁止临时脚本）。

工具清单（每个工具都有 self_check，跑得通才算数）：
  check.py        R0-R16 契约/结构检查，退出码 1 表示有问题
  mutate.py       R13 判据效力：注入必错坏输入，仍 PASS 即判据无牙齿
  consistency.py  R14 三表一致：注册/用例/桥接器互为闭包
  efps.py         R15 有效帧率：渲染 N 帧 ≠ 画面动了 N 帧
  repro.py        R17 豁免验证：声称假阳性必须附可执行最小复现
  capaudit.py     能力可驱动性审计（口径须走 capbridge.normalize）
  reach.py        可达性分析：从活跃入口出发判死代码
  presearch.py    前置检索：先查本地登记库，未命中才联网
  clone.py        仓库克隆校验

统一入口：python3 tools/gate.py [--json]
"""
