[FACT] render_v4   123行   机器生成，勿手改
doc: 渲染 v4 —— 按需调度版
api:
  L44 make_parts()  # 程序化生成身体部件（赭黄僧袍配色）
  L64 build_engine()
  L78 check_all_shots()  # 渲染前硬校验：分镜声明的动作，代码必须能驱动
  L106 self_check(*a,**k)
  L110 main(*a,**k)
internal:
  L90 _load_seq(chdir,base_file)
calls_out: actors,cv2,eng,glob,np,os,out,re,s_
guard: raise@L83
const: BASE, BG_DIR, OUT, ENC_IN[18], ENC_OUT[8], SHOTS[8], LEGACY_OUT_NAMES[4]
main: __main__@L117  self_check@L106
up: actors,film_assemble,framerate,loop_engine,photo_rules,physics,render_v4_main,systems
down: render_desert_banner,render_gate_banner,render_v4_main
