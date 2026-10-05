# 契约: proc/base
#   一句话: 最底层的零依赖公共设施——任何层(含 shape/tools)都可依赖它，它不依赖任何层
#   完整契约见 base/__init__.py
#   判据口径依据:
#     - import-linter / Clean Architecture: 依赖方向必须单向，越底层越稳定；
#       被所有人使用的公共设施应置于最底，避免"上层反向依赖工具层"
#     - 本层由真实事故催生: 统一断言执行器原放在 tools/(检查者层, 最上),
#       导致 motion/showreel 的 self_check 反向依赖 tools，产生 8 条 R1。
#       下沉为独立叶子层后，依赖方向恢复单向。

"""base —— 零依赖公共设施层（依赖图最底）。

为什么单列一层:
  self_check 是本项目约定: 每个模块自带自检。自检要共用"统一断言执行器",
  而该执行器零项目依赖。若放在 tools/(检查者层, 位于最上),
  motion/showreel 反向依赖 tools —— 违反 R1 单向依赖, 且会让
  "生产代码依赖检查者"成为常态。独立成最底叶子层后方向恢复单向。

本层约束:
  1) base 内模块不得 import 任何上层(shape/color/scene/motion/showreel/tests/tools)
  2) base 内模块不得 import 第三方包以外的项目代码
  3) 新增模块须登记进 check.py 的 ALLOW["base"] 可依赖列表(为空集即不可依赖任何人)
"""
