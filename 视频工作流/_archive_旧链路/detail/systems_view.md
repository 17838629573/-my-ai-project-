[FACT] systems_view   149行   机器生成，勿手改
doc: systems 的自检/检查逻辑（由 _extract_tool.py 从 systems.py 抽出）
api:
  L16 update_composite(ctx,i,t)  # 分层合成：背景滚动 + 骨架贴图
  L65 update_subtitle(ctx,i,t)  # 【关键优化】无文字时立即返回 —— 实测 0.58ms -> 0.01ms
internal:
  L100 _make_subtitle_rgba(text,W,H)
calls_in: update_subtitle→_make_subtitle_rgba
calls_out: Image,ImageDraw,a,canvas,ctx,cv2,d,font,lines,np,ph,text,xs,ys
up: framerate,physics,physics_rules,skeleton_runtime,subtitle
down: systems
