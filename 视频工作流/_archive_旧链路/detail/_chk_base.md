[FACT] _chk_base   96行   机器生成，勿手改
doc: solver 自检公共层：共享 import + _r 断言器。
internal:
  L44 _src_of(*names)
  L64 _strip_examples(src)
  L84 _logic_src(src)
  L94 _r(name,cond,note)
calls_out: n,out,src
guard: return@L88
const: BASE_SPEC[5], SOLVER_MODULES[10], SOLVER_SRC, SOLVER_LOGIC
up: _solver_base,_solver_chain,_solver_probe,_solver_reuse,_solver_run,_solver_sheet,anchor,framerate,physics,solver_survey
down: _chk_assemble,_chk_chain,_chk_motion,_chk_multi,_chk_pack,_chk_physics,_chk_reuse,_chk_sheet,_chk_survey,solver_check
