"""中模块 motion/character/body —— 人物形体与渲染内核（L-C 每帧全算层）

一句话：用 SDF 场构造人物形体（不做部件拼接），并把它栅格化着色到画布。

契约: proc/motion/character/body
  输入: 画布、镜头参数、身高像素、关节字典、风矢量
  输出: 绘制好的人物；各原语为上层动作模块提供形体与比例常量
  依赖: numpy
  被依赖: motion.character.*（全部动作模块）、motion.layer、tests.harness
  约束: 本子包只管“形体与渲染”，一律不含动作编排；
        动作模块不得反向依赖 body 之外的具体动作（依赖单向）
  校验: python -m character.selfcheck

小模块（依赖单向，自上而下）:
  sdf.py          SDF 场原语 + BODY_SPEC 胶囊装配清单(11条,带region标签)
  proportions.py  人体比例常数与步频常量
  joints.py       关节表、躯干摆动、步态预设
  leg.py          腿：两骨 IK、踝高、脚掌俯仰
  render.py       投影、场栅格化、法线着色
  cloth.py        Verlet 链与 draw_character 入口
"""
from .sdf import *            # noqa: F401,F403
from .proportions import *    # noqa: F401,F403
from .joints import *         # noqa: F401,F403
from .leg import *            # noqa: F401,F403
from .gait import *          # noqa: F401,F403
from .render import *         # noqa: F401,F403
from .cloth import *          # noqa: F401,F403

__all__ = [n for n in dir() if not n.startswith("_")]

MOVED_TO_BODY = frozenset({
    "sdf", "proportions", "joints", "leg", "gait", "render", "cloth",
})
"""形体核心层下沉登记表：这 7 个模块已从 motion.character.* 移到
motion.character.body.*，同包内 _m(name) 动态导入靠本表重定向，
避免包拆分后静默 ModuleNotFoundError。"""
