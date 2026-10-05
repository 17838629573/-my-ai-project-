[FACT] _split_sheet   237行   机器生成，勿手改
doc: 合图切分：网格定序 + 连通域定界（铁律44）
api:
  L56 split_grid(bgra,cols,rows,names,anchor_edge,trim_px,clean_depth,min_area,cell,fit)  # 返回 [{"name":..., "img":BGRA}, ...]，画布统一 + 锚点对齐。
  L126 self_check()
internal:
  L29 _clean_edges(bgra,depth,key_ref)
calls_in: split_grid→_clean_edges, self_check→split_grid
calls_out: a,bgra,chroma,crops,cv2,np,ys
guard: return@L31, raise@L65
const: RAW='assets_tang/_raw', OUT='assets_tang/char', TRIM_BORDER_PX=4, CLEAN_EDGE_DEPTH=3, MIN_AREA=10, KEY_DIST=150, DARK=40, PLAN[4]
main: __main__@L219  self_check@L126
up: chroma
down: -
