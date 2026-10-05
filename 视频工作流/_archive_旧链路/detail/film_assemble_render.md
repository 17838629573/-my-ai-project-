[FACT] film_assemble_render   187行   机器生成，勿手改
doc: film_assemble 分镜渲染与自检（原 165 行抽出）。
api:
  L21 self_check()  # 只读自检，不渲染（ffmpeg 子进程慢且不必要）。返回 (ok, 项数)
  L120 render_one(p,out_mp4,W,H,fps,bg_speed,bob,step_frames,cam_pull,cam_push,crf)
calls_out: META,SHEET,bad,canvas,cv2,inspect,m,np,os,out,proc,roi,subprocess,v
guard: raise@L123
up: character_sheet,chroma,film_assemble,framerate,photo_rules,subtitle
down: film_assemble
