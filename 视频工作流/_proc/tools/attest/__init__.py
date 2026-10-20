# 契约: proc/tools/attest
#   一句话: 自证类工具子包：出处核验 / 阈值溯源 / 外部锚点 / 豁免复现
#   完整契约见 tools/__init__.py
#   依据: 四者同属「验证声明是否真实」——输入都是别人写下的断言（引用、
#         阈值、出处、假阳性申诉），输出都是 VERIFIED/UNVERIFIED/FAIL；
#         与扫描类(scan)、测量类(measure)、判定类(tools 顶层)职责不同层。
#         归入子包后 tools 直接成员从 21 回到 18（R4 上帝包上限 20）。
#   输入: 项目源码 / 判据表 / 外部文献 URL / 豁免登记册
#   输出: 各工具 self_check 的 PASS/FAIL 与核验条目
#   依赖: 被 gate.py 调用；provenance 依赖 anchors
#   约束: UNVERIFIED 不得记为 PASS（铁律 1）；零核验必须判失败（铁律 3）
#   校验入口: python3 tools/attest/refcheck.py 等各文件均可独立执行
# -*- coding: utf-8 -*-
"""自证类工具（从 tools/ 顶层下沉，避免 tools 包成员超 R4 上限）。

  refcheck.py    出处核验：引用的 arXiv/DOI 是否真实、标题是否与判据语义相关
  provenance.py  阈值溯源：判据阈值与其出处自洽，并探测 HARKing 行为
  anchors.py     外部锚点：只登记可复核的业界数值与口径，供 provenance 比对
  repro.py       豁免复现：声称假阳性必须附可执行最小复现，跑不通按真问题处理

为什么四者同包：它们都不产生新事实，只判定已有声明是否站得住。
"""

from . import anchors, provenance, refcheck, repro          # noqa: F401
