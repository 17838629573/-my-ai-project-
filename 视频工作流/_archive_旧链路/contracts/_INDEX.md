# INDEX（机器生成，勿手改）

两层分离：contracts/<m>.md 定位（含 impl 粗略实现）→ IMPROVE_<m>.md 依据（人工，脚本从不覆盖）
detail/ 事实层已停用（全量 AST 转储维护成本高、正文价值低），细节直接读源码。
读法：先查 FILEMAP.md 按用途定位文件 → [L] 大模块 → [M] 中模块 → [S] 具体模块 → 按 why 指针取依据。
改任一模块前，看该契约的 edit: 行——列出必须同步核对的文件，禁止一次性读全量。

## ATOM  (9M / 39S)
  math       <- _common,_common_selfcheck,_px
  phys       <- physics,physics_rules,zmp,contact_plan,contact_ik,oneshot
  frame      <- framerate,_loopspec
  aero       <- cloth_aero,cloth_wire,wind_response,wind_sway
  water      <- water,rain_layer
  cam        <- _camera,_camera_selfcheck,_perspective,_surface,_wall_geom
  path       <- path,path_align,groundline,scale_map,placement,anchor,_ground_arc
  img        <- chroma,chroma_selfcheck,composite,_layer_style,_matting,_despill
  rule       <- photo_rules,param_decl,actors,_family_map

## SOLVE  (5M / 22S+TOP)
  spec       <- solver_survey,driver,gen_chain
  base       <- _solver_base,_solver_chain_aux,_solver_geom
  chain      <- _solver_chain,_solver_probe
  sheet      <- _solver_sheet,_solver_reuse,_solver_run
  check      <- _chk_base,_chk_physics,_chk_chain,_chk_assemble,_chk_survey,_chk_motion,_chk_multi,_chk_sheet,_chk_reuse,_chk_pack,solver_check
  [TOP] solver

## BUILD  (2M / 6S+TOP)
  util       <- build_util
  phase      <- build_phase_time,build_phase_setup,build_phase_asset,build_phase_gen,build_phase_render
  [TOP] build_video

## SHOT  (7M / 19S+TOP)
  skel       <- skeleton_runtime,skeleton_runtime_selfcheck,pose,pose_selfcheck,pose_prompt,foot_lock,puppet
  sheet      <- character_sheet
  sys        <- systems,systems_phys,systems_view,systems_selfcheck
  loop       <- loop_engine
  sub        <- subtitle
  gen        <- genqueue,prompt_tpl,shot_plan
  assemble   <- film_assemble,film_assemble_render
  [TOP] render_v4,render_v4_main

## GATE  (2M / 5S)
  core       <- enforce,enforce_cmds
  size       <- gate_module,gate_doc,gate_size

## OPS  (3M / 20S)
  audit      <- _audit_dead,_audit_dup,_import_sweep,_actor_audit
  tool       <- _extract_tool,_extract2,_migrate_common,_split_sheet,_split_tool,_split_plan
  demo       <- render_gate_banner,render_desert_banner,_build32,run_batch,run_gen_queue,environment,motion_lib,_问卷,占位音轨,骨架_行走

## 工具
  python3 contract_gen.py          # 全量重生成（改代码后必跑）
  python3 contract_gen.py physics  # 只生成一个
