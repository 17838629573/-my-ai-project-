[FACT] cloth_wire   213行   机器生成，勿手改
doc: cloth_wire — 布料（衣摆/幡/旗）的气动受力接线层
api:
  L32 garment_geom(spec_obj)  # 从物体声明里取布料几何，缺失即反问（铁律103）。
  L63 garment_state(area_m2,mass_kg,v_wind,nx,ny)  # 布料在风中的受力状态与摆角。全部由 cloth_aero 运算，本层不重算物理。
  L91 garment_amp_m(spec_obj,v_wind,family,L_char_m,nx,ny)  # 衣摆最终幅值（米）：气动比值驱动，不是魔法数（铁律102）。
  L135 self_check()  # 自检：含证伪 —— 必须能抓到「没接 cloth_aero」的假实现。
internal:
  L55 _blowoff_ratio()
calls_in: garment_state→_blowoff_ratio, garment_amp_m→garment_geom, garment_amp_m→garment_state, self_check→garment_amp_m, self_check→garment_geom, self_check→garment_state
calls_out: CA,PD,WR,ast,g,magic,math,ok,spec_obj,t,wr
main: __main__@L211  self_check@L135
up: cloth_aero,param_decl,wind_response
down: build_phase_setup,build_util,build_video
