[S] solver_check @SOLVE/check  d8  in=1  gen:contract_gen
does: solver 自检编排器（从 solver.py 拆出，业界：preserve public exports）。
api: self_check
const: DOMAINS
impl: 入口 self_check
up: _chk_assemble,_chk_base,_chk_chain,_chk_motion,_chk_multi,_chk_pack,_chk_physics,_chk_reuse,_chk_sheet,_chk_survey
down: solver
edit: _chk_assemble,_chk_base,_chk_chain,_chk_motion,_chk_multi,_chk_pack,_chk_physics,_chk_reuse,_chk_sheet,_chk_survey,solver   # 改solver_check须同步核对这些文件
why : IMPROVE_solver_check.md
