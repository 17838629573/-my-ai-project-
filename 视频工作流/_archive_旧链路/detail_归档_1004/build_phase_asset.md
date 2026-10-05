[FACT] build_phase_asset   37行   机器生成，勿手改
doc: 出片前置：素材加载与预处理。
api:
  L16 load_flag_sheet(px_per_m,path,grid,take)
  L21 load_man_sheet(px_per_m,path,grid,take)
  L26 load_tree(px_per_m,path)  # 树：缺素材非致命但必须明示（铁律31/99 禁静默）。
calls_out: CH,Image,np,os,xs,ys
guard: return@L29
up: _px,build_util,chroma
down: build_video
