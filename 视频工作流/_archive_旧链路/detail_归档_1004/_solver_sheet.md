[FACT] _solver_sheet   223行   机器生成，勿手改
doc: 图集规划与绘制：网格选择、布局、骨架图集渲染。
api:
  L18 sheet_layout(ans)  # 【铁律41】素材张数 + 排布 + 每格相位，代码算出来必须发给 AI。
  L34 sheet_plan(ans,spec,max_cells,cell_px,bg,aspect)  # 【铁律54-57】把「生成张数」翻译成「画几张图集、每张几格、每格多大」。
  L110 draw_sheet(ans,prefix,cw,ch,cols,rows)  # 按答案包的几何画骨架图集（供图生图作参考）
internal:
  L187 _draw_one(curve,idx,cw,ch,dr,L_px,half_w,ox,oy,bh_px)
calls_in: draw_sheet→_draw_one
calls_out: _glob,_os,ans,cv2,dn,dr,files,g,math,np,sheets,up
guard: raise@L47
up: _solver_base
down: _chk_base,_chk_pack,_chk_physics,_chk_sheet,_solver_run,solver
