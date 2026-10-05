"""solver 自检编排器（从 solver.py 拆出，业界：preserve public exports）。

依赖: _chk_base + 9 个检查域子模块（_chk_physics/_chk_chain/_chk_assemble/
      _chk_survey/_chk_motion/_chk_multi/_chk_sheet/_chk_reuse/_chk_pack）
被依赖: 无（仅 __main__ 或门禁懒加载调用，避免成环）
改进措施记录: IMPROVE_solver_check.md（改前必读）

历史坑（改前必读）：
  1) solve 原未导入 -> self_check 第 1 项即 NameError，56 项从未真正跑通。
     已在 _chk_base 补 from _solver_chain import solve。
  2) 原无 __main__ 入口 -> 自检从未被独立执行，崩了也没人发现。已补。
  3) #21/#51 原用 src.split("def self_check") 自指扫描，搬入子模块后失效，
     须改为扫描 solver 系真实逻辑模块源码。
"""
from _chk_base import _r
from _chk_physics import check as chk_physics
from _chk_chain import check as chk_chain
from _chk_assemble import check as chk_assemble
from _chk_survey import check as chk_survey
from _chk_motion import check as chk_motion
from _chk_multi import check as chk_multi
from _chk_sheet import check as chk_sheet
from _chk_reuse import check as chk_reuse
from _chk_pack import check as chk_pack

# 检查域执行序（顺序即依赖序，勿乱）
DOMAINS = [
    ("物性换算/帧数/相位", chk_physics),
    ("chain/transient", chk_chain),
    ("组装与动静划分", chk_assemble),
    ("问卷与示例", chk_survey),
    ("扬角/振幅/风向", chk_motion),
    ("多驱动叠加/循环", chk_multi),
    ("图集容纳性/探针", chk_sheet),
    ("复用规划/镜像", chk_reuse),
    ("帧数封顶/图集打包", chk_pack),
]


def self_check():
    ok = True
    ctx = {}
    for label, fn in DOMAINS:
        try:
            sub = fn(ctx)
        except Exception as e:
            print("FAIL [%s] 域自检异常: %s: %s" % (label, type(e).__name__, e))
            sub = False
        ok &= bool(sub)
    print("\n%d 个检查域 -> %s" % (len(DOMAINS), "PASS" if ok else "FAIL"))
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if self_check() else 1)
