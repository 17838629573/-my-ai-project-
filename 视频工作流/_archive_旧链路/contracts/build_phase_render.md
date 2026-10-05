[S] build_phase_render @BUILD/phase  d5  in=1  gen:contract_gen
does: 出片：逐帧合成循环。
api: render
impl: 入口 _open_writer；内部helper 3个
up: _ground_arc,build_util,framerate,path
down: build_video
edit: _ground_arc,build_util,build_video,framerate,path   # 改build_phase_render须同步核对这些文件
rule: T76 T77 T79
why : IMPROVE_build_phase_render.md
