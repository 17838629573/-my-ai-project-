"""程序化动画引擎（大模块 / 根）

三层结构：本文件是大模块，只登记契约、不装实现；
中模块是 shape/color/scene/motion 四个目录；小模块是目录里的 .py 文件。
用法：看契约读本文件即可，访问属性时才真正加载实现（PEP 562 惰性导入）。

流水线：画线(shape) -> 填色(color) -> 装背景(scene) -> 跑起来(motion)

┌ 中模块 ─── 一句话职责 ────────── 小模块 ─────────── 依赖 ──── 被依赖 ┐
│ shape    骨架模板/胶囊形体/SDF/线稿  line, character      -          motion
│ color    色库与按 region 着色       paint                 -          motion
│ scene    背景元件/近处细节/背景包    kit, detail, bgpack   detail     motion
│ motion   相机/时间线/合成/风/节拍    camera, run, stage,   shape      (入口)
│                                     beat, wind            color
│                                                           scene
└──────────────────────────────────────────────────────────────────┘

根层保留：formula.py(公式门禁) prompt2spec.py(提示词对照) check.py(契约扫描)

约束：
  1. 依赖单向 大->中->小，禁止反向（反向即"结"，不再是层）
  2. 小文件 >500 行必须下沉拆分（当前 character.py / kit.py 超标，见 check.py）
  3. 每个文件顶部必须有契约块：输入/输出/依赖/被依赖/约束
  4. 缺公式必须 formula.require 抛错，禁止凭记忆写近似值
"""
import os
import sys

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

__all__ = ["shape", "color", "scene", "motion", "formula", "check"]

# 中模块登记表：名字 -> (一句话职责, 小模块元组)
REGISTRY = {
    "shape":  ("画线：骨架模板 → 胶囊形体 → SDF → 线稿（无色）", ("line", "character")),
    "color":  ("填色：色库 → 按胶囊 region 着色", ("paint",)),
    "scene":  ("背景：元件库 / 近处细节 / 背景包", ("kit", "detail", "bgpack")),
    "motion": ("跑起来：相机 / 合成 / 场景 / 节拍 / 风",
               ("camera", "run", "stage", "beat", "wind")),
}

_ROOT_ONLY = ("formula", "check")


def __getattr__(name):
    """惰性加载：不访问就不导入，省上下文也省启动开销。"""
    if name in REGISTRY:
        import importlib
        return importlib.import_module(name)
    if name in _ROOT_ONLY:
        import importlib
        return importlib.import_module(name)
    raise AttributeError(f"proc 没有属性 {name!r}，可用：{list(REGISTRY) + list(_ROOT_ONLY)}")


def tree():
    """打印三层树与每节点一句话职责。"""
    out = [f"proc/  {__doc__.splitlines()[0]}"]
    for mid, (desc, subs) in REGISTRY.items():
        out.append(f"├─ {mid}/   {desc}")
        for s in subs:
            out.append(f"│    └─ {s}.py")
    return "\n".join(out)
