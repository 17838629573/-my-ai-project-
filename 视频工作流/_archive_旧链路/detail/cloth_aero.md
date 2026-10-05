[FACT] cloth_aero   176行   机器生成，勿手改
doc: cloth_aero — 布料/衣物气动受力（"衣服被风吹飞"这类需求）
api:
  L51 wind_force(area_m2,v_wind,nx,ny,v_face)  # 布料面元所受气动合力（物理正确量纲版）。
  L94 will_blow_off(area_m2,v_wind,mass_kg,nx,ny)  # 衣物是否被吹飞：升力 > 重力即离体。
  L111 self_check()
internal:
  L33 _cd()
  L39 _cl()
  L45 _rho()
calls_in: wind_force→_cd, wind_force→_cl, wind_force→_rho, will_blow_off→wind_force, self_check→_rho, self_check→will_blow_off, self_check→wind_force
calls_out: PD,e,math,ok
guard: return@L70, return@L117
const: G=9.80665
main: __main__@L170  self_check@L111
up: param_decl
down: cloth_wire
