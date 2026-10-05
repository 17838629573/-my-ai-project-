[FACT] rain_layer   82行   机器生成，勿手改
doc: rain_layer.py — 雨层渲染（复用 water.py 全部公式，本模块不含任何物性常数）
api:
  L14 rain_drops(R_mm_h,wind_ms,W,H,px_per_m,seed,depth_m)  # 按 Marshall-Palmer 滴谱抽样雨滴 -> [(x0,y0,D_mm,V_ms,ang_rad,len_px
  L34 draw_rain(frame,drops,t,wind_ms,px_per_m,color)  # 把雨画到一帧上（BGR,numpy）。位置 = 初值 + 速度*t，出界回绕。
  L47 cv2_line(img,p1,p2,color,thick,ang)
  L52 self_check()
calls_in: draw_rain→cv2_line, self_check→draw_rain, self_check→rain_drops
calls_out: _common,cv2,f,np,out,rng,water
const: DEPTH_M=0.05
main: __main__@L81  self_check@L52
up: _common,water
down: -
