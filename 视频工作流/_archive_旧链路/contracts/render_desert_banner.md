[S] render_desert_banner @OPS/demo  d6  in=0  gen:contract_gen
does: 沙漠幡旗 —— 独立验证项目（不复用大唐偷渡客的任何分镜）
api: check_actors, build_ctx, main
const: OUT, SECONDS, SHOTS
impl: main → build_ctx → check_actors
up: actors,character_sheet,framerate,physics,render_v4,systems
edit: actors,character_sheet,framerate,physics,render_v4,systems   # 改render_desert_banner须同步核对这些文件
rule: T28
why : IMPROVE_render_desert_banner.md
