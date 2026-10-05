[S] genqueue @SHOT/gen  d3  in=4  gen:contract_gen
does: genqueue · 生图任务队列（铁律81-85）
api: plan, build_prompt, next_task, accept, reject, self_check
const: _KIND, _ID_KEYS
impl: self_check → _chk → build_prompt → next_task；内部helper 2个
up: pose,prompt_tpl
down: build_phase_gen,build_util,build_video,driver
edit: build_phase_gen,build_util,build_video,driver,pose,prompt_tpl   # 改genqueue须同步核对这些文件
rule: T31 T68 T81
why : IMPROVE_genqueue.md
