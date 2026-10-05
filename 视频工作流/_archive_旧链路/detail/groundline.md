[FACT] groundline   169行   机器生成，勿手改
doc: 地基线探测：从背景图自动找出"人能站在哪条水平线上"。
api:
  L23 probe(bgr,y,band_px)  # 返回指定行的双侧窄带颜色对比度，供 AI 复核某条候选。
  L57 detect(bgr,band_px,top_n,y_range,sigma)  # 自动探测地基线。
  L104 self_check()
internal:
  L11 _row_strength(bgr,sigma)
  L39 _multiscale_contrast(bgr,y,band_px)
calls_in: _multiscale_contrast→probe, detect→_multiscale_contrast, detect→_row_strength, detect→probe, self_check→_multiscale_contrast, self_check→_row_strength, self_check→detect, self_check→probe
calls_out: bgr,cands,cv2,np,r,rows,sob,st,vals
guard: return@L68
const: MULTI_SCALE[3]
main: __main__@L167  self_check@L104
up: -
down: build_phase_setup,build_util,build_video
