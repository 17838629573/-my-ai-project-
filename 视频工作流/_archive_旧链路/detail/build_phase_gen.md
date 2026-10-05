[FACT] build_phase_gen   136行   机器生成，勿手改
doc: 出片前置：生图任务包 + 生图顺序队列。
api:
  L17 plan_shots(spec,W,H,baseline_y)  # 生图任务包：代码告诉 AI 路画在哪（铁律97）。
  L81 emit_gen_queue(spec,U)  # 生图顺序：一次只生成一种物体的一类图（铁律81），禁混用提示词。
internal:
  L34 _solve_structural(fam,spec,o,U)
  L61 _cloth_phys_points(solved,real_m,n)
calls_in: emit_gen_queue→_cloth_phys_points, emit_gen_queue→_solve_structural
calls_out: GQ,PT,SP,_C,_anc,_done,_g,_pts,_qobjs,_solved,math,o,spec,spec_d
guard: raise@L84
up: _common,build_util,genqueue,pose,prompt_tpl,shot_plan,wind_response
down: build_video,run_gen_queue
