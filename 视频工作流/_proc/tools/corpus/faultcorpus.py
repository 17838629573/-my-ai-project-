# 契约: proc/tools/faultcorpus
#   一句话: faultbench 的缺陷语料——干净基线样本 + 14 条注入器定义
#   完整契约见 tools/__init__.py
#   依据: 变异测试惯例（注入已知缺陷、验证工具能否抓到）；
#         每条 FAULT 对应 smell/check/complexity 的一类静态盲区。
#   输入: 无
#   输出: BASE(str) 干净样本源码；FAULTS(list) (id, 类别, 说明, 注入器)
#   依赖: 无（纯数据）
#   约束: 注入器必须是纯函数 src->new_src，不得有副作用
#   校验入口: python3 tools/faultbench.py
# -*- coding: utf-8 -*-
"""缺陷语料 —— 与注入/判定逻辑分离。

为什么分文件:
  BASE 65 行 + FAULTS 36 行共百余行纯数据，与跑测逻辑无关；
  内联会让 faultbench.py 超 500 行红线（R2 超纲）。
"""

# 基线 canary：一个干净、无缺陷的合规样本（>50 行，避免 R2 过短误报）
BASE = '''# 契约: proc/_canary_faultbench
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


def total(xs):
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
    # 浮点比较用容差：BASE 自称"干净基线、注入前必须全绿"，
    # 若这里写 ==，S07 会把基线本身报成有缺陷，基准的自证就不成立
    out.append(("clamp 下限", abs(clamp(-1.0, 0.0, 1.0) - 0.0) < 1e-12))
    out.append(("clamp 上限", abs(clamp(9.0, 0.0, 1.0) - 1.0) < 1e-12))
    return out
'''

# (id, 类别, 说明, 注入器)  注入器: src -> new_src
FAULTS = [
    ("F01", "静默异常", "except Exception: pass 吞掉错误",
     lambda s: s.replace('import math\n\n\ndef area(r):',
                         'import math\n\n\ndef risky():\n    try:\n        return 1 / 0\n    except Exception:\n        pass\n\n\ndef area(r):')),
    ("F02", "漏导入", "用未导入的名字",
     lambda s: s.replace("return math.pi * r * r", "return math.pi * r * r + os.sep")),
    ("F03", "判据恒真", "self_check 用 True 代替真判据",
     lambda s: s.replace('out.append(("area(1)=pi", abs(area(1) - math.pi) < 1e-12))',
                         'out.append(("area(1)=pi", True))')),
    ("F04", "阈值放宽", "阈值从 1e-12 放宽到 1e6，判据形同虚设",
     lambda s: s.replace("< 1e-12", "< 1e6")),
    ("F05", "单位错用", "米当像素，结果放大 100 倍",
     lambda s: s.replace("return math.pi * r * r", "return math.pi * r * r * 100  # px")),
    ("F06", "复制粘贴", "ratio 里误用 area 的变量名",
     lambda s: s.replace("    if b == 0:\n        return None\n    return a / b",
                         "    if b == 0:\n        return None\n    return a / r")),
    ("F07", "除零", "去掉零分母保护",
     lambda s: s.replace("    if b == 0:\n        return None\n    return a / b",
                         "    return a / b")),
    ("F08", "索引越界", "访问列表第 999 项",
     lambda s: s.replace("    return sum(xs)", "    return xs[999] + sum(xs)")),
    ("F09", "可变默认参数", "def f(xs=[]) 共享状态",
     lambda s: s.replace("def total(xs):", "def total(xs=[]):")),
    ("F10", "契约缺失", "删掉契约块首行",
     lambda s: s.replace("# 契约: proc/_canary_faultbench\n", "")),
    ("F11", "硬编码路径", "写死 /data/workspace 绝对路径",
     lambda s: s.replace('import math\n\n\ndef area(r):',
                         'import math\nROOT = "/data/workspace/视频工作流"\n\n\ndef area(r):')),
    ("F12", "函数超长", "塞入 60 行空逻辑，触发 R3",
     lambda s: s.replace("def self_check():",
                         "def big():\n" + "".join("    x%d = %d\n" % (i, i) for i in range(60)) + "\n\ndef self_check():")),
    ("F13", "浮点相等", "用 == 比较浮点结果",
     lambda s: s.replace("total([1, 2, 3]) == 6", "area(2) == 12.566370614359172")),
    ("F14", "自检空转", "self_check 直接返回空列表",
     lambda s: s.replace("    out = []\n    out.append", "    out = []\n    return out\n    out.append")),
]
