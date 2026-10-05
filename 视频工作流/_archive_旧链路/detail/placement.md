[FACT] placement   199行   机器生成，勿手改
doc: 语义定位点：把一个语义点 → 世界坐标落位。
api:
  L22 semantic_point(kind,canvas_w,canvas_h,shape)  # 源画布内语义点像素坐标。shape 仅 attach 需要：{"ratio":(rx,ry)}
  L38 attach_point(kind,canvas_w,canvas_h,ratio)  # 附着类语义点。ratio=(rx,ry) 由 AI 声明。
  L43 place(regpoint,target_xy,scale)  # 把 regpoint 的语义点落到 target_xy，返回落位矩形 {x0,y0,w,h}。
  L82 verify(regpoint,target_xy,rect,tol)  # 反算：给定落位矩形，语义点是否真的在 target_xy 上。
  L97 self_check()
calls_in: attach_point→semantic_point, place→semantic_point, verify→semantic_point, self_check→place, self_check→semantic_point, self_check→verify
calls_out: drift,fails,math,regpoint,worlds
guard: raise@L24, raise@L27, raise@L49, raise@L52, raise@L56, raise@L62, raise@L73
const: SEMANTIC_KINDS[5], _SPEC[5]
main: __main__@L197  self_check@L97
up: -
down: build_util,build_video,shot_plan
