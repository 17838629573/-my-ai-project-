[FACT] shot_plan   230行   机器生成，勿手改
doc: 镜头规划 / 生图任务包：告诉 AI 路画在哪、物体多大、落在哪、提示词怎么写。
api:
  L22 build_scale(scene)
  L27 path_hint(pts,half_width_m,px_per_m,persp)  # 路径在背景图上的像素提示。pts 为像素控制点。
  L64 locate(kind,real_m,anchor_xy,px_per_m,src_shape,scale)  # 单个物体的落位矩形（铁律84：不手填，一律走 placement.place）。
  L80 path_prompt(ph,material)  # 路面几何提示（铁律97）：必须让 AI 画出"走向 + 纵深透视"。
  L98 obj_prompt(name,real_m,ph,kind,on_path)  # 物体落位提示。on_path 默认改为 False（铁律100）：
  L114 material_name(ph)
  L121 on_path_by_family(fam,declared)  # 是否允许落在路径上，按族判定（铁律100）。
  L134 plan_shot(bg_shape,scene,objects,families)  # objects: [{name, kind, real_m, on_path, s, offset, anchor_xy
  L171 self_check()
internal:
  L15 _need(d,keys,where)
calls_in: path_hint→_need, obj_prompt→material_name, plan_shot→_need, plan_shot→build_scale, plan_shot→locate, plan_shot→obj_prompt, plan_shot→on_path_by_family, plan_shot→path_hint, plan_shot→path_prompt, self_check→build_scale, self_check→path_hint, self_check→plan_shot
calls_out: PA,PL,SM,o,objs,prompts,pts
guard: raise@L17, raise@L34, raise@L36, return@L127, return@L129, raise@L140
const: _PATH_FAMILIES[3]
main: __main__@L229  self_check@L171
up: path,placement,scale_map,wind_sway
down: build_phase_gen,build_util,build_video
