[S] loop_engine @SHOT/loop  d1  in=1  gen:contract_gen
does: 按需调度引擎 —— 解决"全量跑"问题
api: self_check
impl: 入口 self_check
up: framerate
down: render_v4
edit: framerate,render_v4   # 改loop_engine须同步核对这些文件
rule: T26 T28
why : IMPROVE_loop_engine.md
