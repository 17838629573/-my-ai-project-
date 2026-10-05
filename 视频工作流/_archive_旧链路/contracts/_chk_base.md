[S] _chk_base @SOLVE/check  d6  in=10  gen:contract_gen
does: solver 自检公共层：共享 import + _r 断言器。
const: BASE_SPEC, SOLVER_MODULES, SOLVER_SRC, SOLVER_LOGIC
impl: 入口 _src_of；内部helper 4个
up: _solver_base,_solver_chain,_solver_probe,_solver_reuse,_solver_run,_solver_sheet,anchor,framerate,physics,solver_survey
down: _chk_assemble,_chk_chain,_chk_motion,_chk_multi,_chk_pack,_chk_physics (+4)
edit: _chk_assemble,_chk_chain,_chk_motion,_chk_multi,_chk_pack,_chk_physics,_chk_reuse,_chk_sheet,_chk_survey,_solver_base,_solver_chain,_solver_probe,_solver_reuse,_solver_run,_solver_sheet,anchor,framerate,physics,solver_check,solver_survey   # 改_chk_base须同步核对这些文件
rule: T89
why : IMPROVE__chk_base.md
