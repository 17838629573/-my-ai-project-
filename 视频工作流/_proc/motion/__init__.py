"""中模块 motion —— 跑起来（第三层后段）

一句话：把形体和背景放进相机与时间线，逐帧渲染出片。

契约: proc/motion
  输入: shape 的形体、color 的着色、scene 的烘焙背景、镜头脚本（beat 列表）
  输出: 帧序列与 mp4
  依赖: shape, color, scene
  被依赖: （入口层，无上层）
  约束: 人物与路必须共用同一台相机（px_per_m(Z)），否则"人走的和路不匹配";
        步长由骨架反推并与 0.414×身高 交叉校验，两条独立来源必须吻合;
        支撑脚世界坐标 CV 必须接近 0，否则视为打滑;
        边界帧不许淡入淡出同时为 0（会出现空档）
  校验: python -m motion 或 check.py

小模块:
  camera.py   相机：视高/焦距/px_per_m(Z)/反投影            182 行
  run.py      时间线与出片                                  236 行
  stage.py    场景合成：烘焙 + 人物 + 出片                   299 行
  beat.py     节拍时间线：prep→stroke→relax 串多段动作       355 行
  wind.py     风场：主弯曲 + 细节弯曲（Crysis 式）           134 行
"""
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

__all__ = ["camera", "run", "stage", "beat", "wind"]


# ---- 能力表归一（capbridge）----
# 不这样做会怎样：CAP 名义是「姿态函数」，实际混了物理仿真/增量/求解器/群体函数，
# 时间线拿到非姿态返回值当关节字典遍历，要么崩要么把标量混进骨架。
# 导入失败登记簿 —— 绝不静默吞掉
# 为什么不写 except: pass —— 这正是「climb 白写」事故的机制性根因：
# climb.py 写好了、self_check 也过，但导入时炸了被 pass 吞掉，
# 外界看到的不是「导入失败」，而是「STUB 缺能力」，误导排查方向整整一轮。
# 出处: Python 官方 logging 教程「记录异常供诊断，不要用裸 except 吞掉」；
#       IEEE Software 对 silent failure 的归类即为 anti-pattern。
IMPORT_ERRS = []


def init_capabilities(verbose=False):
    from . import beat as _b, capbridge as _cb
    import importlib
    del IMPORT_ERRS[:]
    # 为什么改成 (包前缀, 模块名) 两张表：
    # 上轮把 7 个形体模块下沉到 character/body/ 后，循环里仍写 ".character.gait"，
    # 于是 gait 导入失败被登记，walk 的底层实现缺失却只表现为「子模块导入失败 1 项」。
    # 同时 push/quadruped/roll/constraint_ext/physics_ext 五个模块**根本不在循环里**，
    # 它们的 @capability 永不注册，外界看到的是「STUB 缺能力」——
    # 与 climb 事故同源：函数写好了，只是没人 import 它。
    # 出处: Python importlib 官方文档（动态导入需完整包路径）；
    #      silent failure 归类见 IEEE Software anti-pattern。
    # 为什么改成自动遍历而不是继续维护显式清单：
    # 显式清单要手工同步，一旦新增模块忘加进来，@capability 就永不注册，
    # 外界看到的是「STUB 缺能力」而非「没人 import 它」——这是「白写」类事故的
    # 机制性根因，本项目已复发五次（climb、push/quadruped/roll、phenom、
    # H40/P41-P45 未登记进 CASES、本次默认路径只注册 1/51）。
    # 修补清单只能救一次，自动遍历才能根治：pkgutil.walk_packages 发现全部子模块，
    # 新增模块无需改任何清单即可注册。
    # 出处: Python 官方 pkgutil 文档（walk_packages 递归遍历包内所有模块）；
    #      silent failure 归类见 IEEE Software anti-pattern。
    import pkgutil
    _seen = set()
    # 必须按 name 排序而非直接 sorted(namedtuple)：ModuleInfo 含 module_finder
    # 字段，直接比较会撞 TypeError（FileFinder 不可比较）。
    for _mi in sorted(pkgutil.walk_packages(__path__, __name__ + "."),
                      key=lambda _m: _m.name):
        _seen.add(_mi.name)
        try:
            importlib.import_module(_mi.name)
        except Exception as _e:
            IMPORT_ERRS.append((_mi.name, repr(_e)))
    # 为什么不保留「清单反向校验」：曾试图用旧清单检查是否有模块被删/改名，
    # 但 walk_packages 不把子包本身（如 motion.rigid2d）作为模块 yield，
    # 于是 12 个包级条目被误报成「未被发现」——校验本身成了噪音源。
    # 而噪音比缺失更危险：真失败会淹没在 12 条假失败里。
    # 既然已自动遍历，清单连同其校验一并移除，不留第二处需要同步的地方。
    if IMPORT_ERRS:
        # 不抛异常：能力表应尽力注册齐其余部分；但必须留下可读证据
        print("[motion] 子模块导入失败 %d 项（能力会被误报为 STUB）:" % len(IMPORT_ERRS))
        for _n, _e in IMPORT_ERRS:
            print("   %s -> %s" % (_n, _e))
    return _cb.normalize(_b.CAP, _b.CAP_SRC, _b.CAP_GROUP, verbose=verbose)


# ---- 导入即注册 ----
# 为什么不要求调用方显式调 init_capabilities()：
# 2026-10-11 实测 `import motion` 后 CAP 只注册 1/51 —— 51 个能力全部写好、
# self_check 全过，但默认路径下拿不到 40 个。README 却写着「全部注册」。
# 与 climb 事故同源第六次：能力存在，只是没人 import。
# 改为导入包即自动注册，调用方无需知道有这张表。
# 出处: Python 官方 pkgutil 文档；silent failure 见 IEEE Software anti-pattern。
_AUTO_INIT_ERR = None
if not os.environ.get("MOTION_NO_AUTOINIT"):
    try:
        init_capabilities()
    except Exception as _e:      # 绝不静默：登记并打印，供门禁捕获
        _AUTO_INIT_ERR = repr(_e)
        IMPORT_ERRS.append(("init_capabilities(自动)", _AUTO_INIT_ERR))
        print("[motion] 自动注册失败（能力会被误报为 STUB）: %s" % _AUTO_INIT_ERR)
