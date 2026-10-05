[S] render_gate_banner @OPS/demo  d6  in=0  gen:contract_gen
does: 沙漠幡旗 —— 独立验证项目（不复用大唐偷渡客的任何分镜）
api: check_actors, build_ctx, main
const: SCENE_SPEC, OUT, SECONDS, SHOTS
impl: main → build_ctx → check_actors；内部helper 1个
up: actors,character_sheet,framerate,physics,render_v4,systems
edit: actors,character_sheet,framerate,physics,render_v4,systems   # 改render_gate_banner须同步核对这些文件
rule: T20 T23 T28
why : IMPROVE_render_gate_banner.md
