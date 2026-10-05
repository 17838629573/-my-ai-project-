[FACT] photo_rules   251行   机器生成，勿手改
doc: 摄影规则确定性层
api:
  L149 body_pixels(shot,H,headroom)  # 由景别反算人物像素高度。
  L165 ground_y(shot,H,char_h,footroom)  # 脚底在画面中的 y（可能 > H，即出画）
  L171 head_top_y(shot,H,char_h,ground)
  L176 validate_shot(shot_type,angle,movement,H,W)  # 单镜头校验。返回问题列表，空 = 通过。
  L204 validate_sequence(seq)  # 序列校验（剪辑相邻原则）：
calls_in: validate_shot→body_pixels, validate_shot→ground_y
calls_out: SHOT_TYPES,a,b,errs
guard: return@L158, return@L181, return@L183, return@L185
const: BODY[13], JOINTS, SHOT_TYPES[8], ANGLES[5], MOVEMENTS[7]
main: __main__@L229
up: -
down: character_sheet,film_assemble,film_assemble_render,render_v4,render_v4_main
