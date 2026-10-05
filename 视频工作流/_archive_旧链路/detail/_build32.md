[FACT] _build32   68行   机器生成，勿手改
api:
  L8 key_color_of(im)
  L12 key_alpha(cell,key)
  L34 prep(item,th)
  L50 sh_of(al,i)
calls_in: prep→key_alpha
calls_out: L,cell,cv2,np,xs,ys
guard: return@L38
const: BATCH[4], FPS=32, DUR=8.0, SPEED=1.5, OUT_W=576, PX_PER_M, BASE_Y
up: _layer_style
down: -
