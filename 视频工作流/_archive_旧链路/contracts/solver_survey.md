[S] solver_survey @SOLVE/spec  d5  in=4  gen:contract_gen
does: solver_survey —— 从 solver.py 切出（业界：文件 150-500 行最优）。
api: survey, inventory, scale_question, assemble, briefing_text
const: KINDS, PART_ROLES, DRIVE_SOURCES, SLOT_TEMPLATE, EXAMPLES, HOWTO
impl: 入口 survey；内部helper 1个
up: driver
down: _chk_assemble,_chk_base,_chk_survey,solver
edit: _chk_assemble,_chk_base,_chk_survey,driver,solver   # 改solver_survey须同步核对这些文件
rule: T29 T30 T31 T33 T35 T36 T63 T64
why : IMPROVE_solver_survey.md
