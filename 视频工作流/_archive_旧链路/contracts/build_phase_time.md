[S] build_phase_time @BUILD/phase  d2  in=1  gen:contract_gen
does: 出片前置：周期与步态时间参数。
api: flag_period_s, gait_time, durations, durations_for
impl: 入口 flag_period_s
up: wind_response
down: build_video
edit: build_video,wind_response   # 改build_phase_time须同步核对这些文件
rule: T29
why : IMPROVE_build_phase_time.md
