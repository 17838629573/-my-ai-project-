[FACT] build_phase_render   70行   机器生成，勿手改
doc: 出片：逐帧合成循环。
api:
  L27 render(ctx)  # 逐帧合成。ctx 键: bg W H FPS OUT flag_frames man_frames
internal:
  L18 _open_writer(path,fps,W,H)
calls_in: render→_open_writer
calls_out: FR,PA,bg,cv2,vw
up: build_util,framerate,path
down: build_video
