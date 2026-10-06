# 契约: proc/tests
#   一句话: 门检用例层：22 项 PASS + 13 项 STUB 的执行体与判据接线
#   完整契约见本文件「用例清单」
#   依据: 测试包须为真实包（有 __init__.py）才能被静态分析工具（grimp/import-linter）
#         建图；此前缺失导致 layers 契约报 "module _proc.tests does not exist"，
#         是靠 sys.path 自举块伪装的运行时包（与 tools/__init__.py 缺失同类病）。
# -*- coding: utf-8 -*-
"""proc.tests —— 门检用例层。

用例清单（按组）：
  run_all.py      入口与调度：EXEC 表、main()、F35 漂移、E28 爬梯
  common.py       共享常量与世界构建（_world）
  cases_base.py   A 组（A1-A7）+ B8/B9
  cases_throw.py  B10 扔球 / B11 接球
  cases_carry.py  B12-B14 道具 / E26 搬运箱子
  cases_crowd.py  D21-D24 多主体
  cases_phys.py   C15-C20 刚体物理
  cases_pass.py   D22 两人传球
  cases.py        历史遗留聚合
  harness.py      判据库（每条判据带出处）
  gen.py          渲染器与剪影判据
  gen_doc.py      文档生成

运行：
  python3 _proc/tests/run_all.py        # 直接跑（有 __file__ 自举块，无需 PYTHONPATH）
  python3 -m _proc.tests.run_all        # 亦可作为包运行
"""
