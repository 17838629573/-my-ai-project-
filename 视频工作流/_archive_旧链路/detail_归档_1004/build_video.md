[FACT] build_video   155行   机器生成，勿手改
doc: 合成出片：探测基线 + 路径约束 + 语义落位 + 程序化风摆。
api:
  L40 load_sheet(*a,**k)
  L53 resize_h(*a,**k)
  L58 sway_image(*a,**k)
  L63 over(*a,**k)
  L68 place_at(*a,**k)
  L87 apply_garment_wind(*a,**k)
  L91 main()  # 编排器：只做阶段串接，各阶段实现见 build_phase_*.py。
internal:
  L48 _resize_cs(*a,**k)
  L73 _need(*a,**k)
  L81 _joint_seq(*a,**k)
  L142 _flag_xy(spec,bg,H)
calls_in: main→_flag_xy
calls_out: BPA,BPG,BPR,BPS,BPT,SF,cv2,json,spec
guard: raise@L95
const: FPS, OUT='玄奘西行_城墙成片.mp4'
main: __main__@L154
up: _surface,build_phase_asset,build_phase_gen,build_phase_render,build_phase_setup,build_phase_time,build_util,chroma,cloth_wire,composite,framerate,genqueue,groundline,path,placement,scale_map,shot_plan,wind_sway
down: -
