[FACT] subtitle   323行   机器生成，勿手改
doc: 字幕渲染层 —— 修一个真 bug
api:
  L37 get_font(size)
  L54 wrap(text,font,max_w,max_chars)  # 断行：优先按【语义】断（标点/连词），其次按像素宽度，并受字数上限约束。
  L113 draw_subtitle(bgr,text,alpha,font_size,margin_bottom,box_w,max_chars,stroke)  # 在 BGR 帧上叠加字幕。返回 BGR。
  L179 subtitle_alpha(local_frame,total_frames,fade_frames)  # 字幕淡入淡出。
  L196 check_timing(seconds,chars,fps)  # 字幕时序自检（行业标准）：
  L222 self_check()  # 只读自检，不渲染。返回 (ok, 项数)
calls_in: draw_subtitle→get_font, draw_subtitle→wrap, self_check→check_timing, self_check→draw_subtitle, self_check→get_font, self_check→subtitle_alpha, self_check→wrap
calls_out: Image,ImageDraw,ImageFont,_IF,d,fixed,font,inspect,issues,lines,merged,np,os,out
guard: return@L38, return@L125, return@L187, return@L189, return@L191
const: _FONT_CANDIDATES[4], _FONT_CACHE[0], FADE_FRAMES=6, MIN_GAP_FRAMES=2, MIN_DURATION_S, MAX_DURATION_S=7.0
main: __main__@L320  self_check@L222
up: framerate
down: film_assemble,film_assemble_render,systems_view
