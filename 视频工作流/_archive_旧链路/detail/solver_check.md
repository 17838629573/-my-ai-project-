[FACT] solver_check   56行   机器生成，勿手改
doc: solver 自检编排器（从 solver.py 拆出，业界：preserve public exports）。
api:
  L40 self_check()
const: DOMAINS[9]
main: __main__@L54  self_check@L40
up: _chk_assemble,_chk_base,_chk_chain,_chk_motion,_chk_multi,_chk_pack,_chk_physics,_chk_reuse,_chk_sheet,_chk_survey
down: solver
