[S] build_phase_gen @BUILD/phase  d5  in=2  gen:contract_gen
does: 出片前置：生图任务包 + 生图顺序队列。
api: plan_shots, emit_gen_queue
impl: 入口 plan_shots；内部helper 2个
up: _common,build_util,genqueue,pose,prompt_tpl,shot_plan,wind_response
down: build_video,run_gen_queue
edit: _common,build_util,build_video,genqueue,pose,prompt_tpl,run_gen_queue,shot_plan,wind_response   # 改build_phase_gen须同步核对这些文件
rule: T29 T31 T81 T97
why : IMPROVE_build_phase_gen.md
