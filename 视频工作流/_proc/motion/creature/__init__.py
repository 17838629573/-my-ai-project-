# -*- coding: utf-8 -*-
# 契约: proc/motion/creature
#   一句话: 非人生物运动：攀岩（不规则支点）与鱼游（行波推进）
#   依赖: base, color, shape
#   被依赖: tests
#   允许被测试: True
#   不变量: 链段等弧长（鱼）、三点支撑（攀岩）
#   对外接口: 见各模块 self_check()
#   契约与代码不一致时，以代码为准并修契约

"""非人生物运动包。

与 character（人形/四足骨架）分开的原因：
  攀岩依赖环境查询（不规则支点），鱼游依赖流体行波推进，
  二者都不是 character 的"固定骨架 + 周期性相位"范式。
"""

_MODULES = ("climb_rock", "fish_swim", "quadruped")

from motion.creature.climb_rock import climb_rock  # noqa: F401
from motion.creature.fish_swim import fish_swim, fish_strouhal  # noqa: F401
from motion.creature.quadruped import quadruped_sim, foot_slip  # noqa: F401


def self_check():
    from base.assertrun import Checker
    import importlib
    c = Checker("motion.creature")
    for nm in _MODULES:
        mod = importlib.import_module("motion.creature." + nm)
        c.chk("%s.self_check" % nm, bool(mod.self_check()),
              "子模块自检须全通过")
    return not c.failed
