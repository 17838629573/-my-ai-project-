[FACT] build_util   205行   机器生成，勿手改
doc: build_video 的自检/检查逻辑（由 _extract_tool.py 从 build_video.py 抽出）
api:
  L23 load_sheet(path,grid,take)  # 图集 -> 逐帧 RGBA。连通域定界 + 跨帧统一包围框（pivot 稳定）。
  L82 resize_h(frame,target_h)
  L90 sway_image(rgb,a,t,wind,world_xy,amp_px)  # 程序化风摆：按高度权重做逐行横向位移（铁律79/80，根部不动）。
  L116 over(canvas,rgb,a,x,y)
  L131 place_at(kind,rgb,a,target_xy)  # 语义点落到 target_xy -> 左上角（铁律84）。
  L183 apply_garment_wind(rgb,a,t_s,gr,px_per_m,wind_dir)  # 衣摆受风：对人物下部做水平剪切位移，权重自 y0 线性增至底部。
internal:
  L67 _resize_cs(rgb,size)
  L138 _need(d,key,where)
  L143 _joint_seq(spec,height_m,n_key)
calls_in: resize_h→_resize_cs, _joint_seq→_need
calls_out: C,CH,Image,PL,WS,_cv,_np,a,gait,gr,map_y,np,os,out,pose,wt,xs,ys,ys_rows
guard: raise@L25, return@L74, return@L96, return@L123, raise@L139
const: KEYJOINTS[6]
up: _common,chroma,cloth_wire,composite,framerate,genqueue,groundline,path,placement,pose,scale_map,shot_plan,wind_sway
down: build_phase_asset,build_phase_gen,build_phase_render,build_phase_setup,build_video
