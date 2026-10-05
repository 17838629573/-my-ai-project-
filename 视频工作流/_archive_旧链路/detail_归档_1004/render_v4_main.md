[FACT] render_v4_main   210行   机器生成，勿手改
doc: render_v4 自检与出片主流程（原 182 行上帝函数抽出）。
api:
  L27 self_check()  # 只读自检，不渲染。返回 (ok: bool, 检查项数)
  L88 main()
calls_out: a,actors,c,css,cv2,eng,f,only,os,ph,proc,s,segs,subprocess,time
up: actors,character_sheet,film_assemble,framerate,photo_rules,physics,render_v4,systems
down: render_v4
