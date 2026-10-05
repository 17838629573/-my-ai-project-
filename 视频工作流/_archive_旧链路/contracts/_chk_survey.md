[S] _chk_survey @SOLVE/check  d7  in=1  gen:contract_gen
does: 检查域4：源码禁硬编码物体名/survey 只问不猜/示例覆盖。
api: check
impl: 入口 check
up: _chk_base,solver_survey
down: solver_check
edit: _chk_base,solver_check,solver_survey   # 改_chk_survey须同步核对这些文件
rule: T36
why : IMPROVE__chk_survey.md
