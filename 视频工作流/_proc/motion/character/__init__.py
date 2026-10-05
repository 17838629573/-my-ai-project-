"""中模块 motion/character —— 人物（L-C 每帧全算层）

一句话：用 SDF 场构造人物形体（不做部件拼接）+ 步态驱动 + 布料二级运动。

契约: proc/motion/character
  输入: 画布、镜头参数、身高像素、步态相位、风矢量、dt
  输出: 绘制好的人物；gait() 返回关节字典
  依赖: motion.camera, scene.kit(仅自检用)
  被依赖: motion.run, motion.stage, motion.beat
  约束: 步长必须与 0.414×身高 交叉校验（两条独立来源）;
        支撑脚世界坐标 CV≈0（打滑即 bug）; 脚掌角由实测关键点插值，禁止对称正弦;
        披帛根必须抓在肩关节上，禁止固定像素偏移（否则飘出身体）
  校验: python -m character.selfcheck

小模块（依赖单向，自上而下）:
  sdf.py          SDF 场原语 + BODY_SPEC 胶囊装配清单(11条,带region标签)
  proportions.py  人体比例常数与步频常量
  joints.py       关节表、躯干摆动、步态预设
  leg.py          腿：两骨 IK、踝高、脚掌俯仰
  gait.py         步态主函数(Composed Method: root→legs→spine→arms)
  render.py       投影、场栅格化、法线着色
  cloth.py        Verlet 链与 draw_character 入口
  sit.py          坐下/站起（7 关键姿态 + 三相位）
  gesture.py      手势与注视（敲击 snappy、翻页、gaze shift）
  prop.py         道具交接四相位 + 世界/身体坐标反算 + 双手换手
  turn.py         原地转身（速率分档 + smoothstep + 换步抬脚）
  jump.py         原地跳跃（蹬伸匀加速/腾空解析抛物线/落地匀减速）
  crouch.py       下蹲与拾取（蹲到底肩物距 ≤ 臂展）
  run.py          跑步与急停（腾空弹道 + 制动 a=2V/T ≤ μg）
  carry.py        抱箱搬运（NIOSH 贴躯干 + 半蹲举 + 四相位所有权）
  selfcheck.py    自检脚本
"""
import os
import sys
_P = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _P not in sys.path:
    sys.path.insert(0, _P)

from .proportions import *
from .joints import *
from .leg import *
from .gait import *
from .render import *
from .cloth import *
from .sit import *
from .gesture import *
from .prop import *
from .turn import *
# 注意: run/jump/crouch 三个模块里的动作函数与模块同名,
#   import * 会把包属性覆盖成函数, 令 motion.character.jump 取到函数而非模块。
#   故星号导入后再显式取回子模块对象(契约: 包属性=子模块, 动作函数一律走 CAP 注册表)
from . import jump as jump, crouch as crouch, run as run  # noqa: F401 取回子模块对象
# carry 同理: carry_box 与模块同名, 星号导入会覆盖包属性
from . import carry as carry  # noqa: F401 取回子模块对象

__all__ = [n for n in dir() if not n.startswith("_")]

# throw/catch: 模块名与能力名同名, 星号导入会覆盖包属性, 必须显式取回
from . import throw as throw
from . import catch as catch
