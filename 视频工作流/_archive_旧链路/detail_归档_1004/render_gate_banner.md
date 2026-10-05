[FACT] render_gate_banner   188行   机器生成，勿手改
doc: 沙漠幡旗 —— 独立验证项目（不复用大唐偷渡客的任何分镜）
api:
  L67 check_actors()
  L81 build_ctx(s)
  L143 main()
internal:
  L40 _banner_phys()
calls_in: build_ctx→_banner_phys, main→build_ctx, main→check_actors
calls_out: R,a,actors,c,css,cv2,eng,f,os,ph,proc,s,segs,subprocess,sys,time
guard: raise@L100
const: SCENE_SPEC[1], OUT='城墙幡旗.mp4', SECONDS=4.0, SHOTS[1]
main: __main__@L187
up: actors,character_sheet,framerate,physics,render_v4,systems
down: -
