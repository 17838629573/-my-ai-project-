[S] shot_plan @SHOT/gen  d3  in=3  gen:contract_gen
does: 镜头规划 / 生图任务包：告诉 AI 路画在哪、物体多大、落在哪、提示词怎么写。
api: build_scale, path_hint, locate, path_prompt, obj_prompt, material_name, on_path_by_family, plan_shot, self_check
const: _PATH_FAMILIES
impl: self_check → build_scale → path_hint → plan_shot；内部helper 1个
up: path,placement,scale_map,wind_sway
down: build_phase_gen,build_util,build_video
edit: build_phase_gen,build_util,build_video,path,placement,scale_map,wind_sway   # 改shot_plan须同步核对这些文件
rule: T31 T76 T78 T84 T85 T97 T100
why : IMPROVE_shot_plan.md
