[S] cloth_wire @ATOM/aero  d2  in=3  gen:contract_gen
does: cloth_wire — 布料（衣摆/幡/旗）的气动受力接线层
api: garment_geom, garment_state, garment_amp_m, self_check
impl: self_check → garment_amp_m → garment_geom → garment_state；内部helper 1个
up: cloth_aero,param_decl,wind_response
down: build_phase_setup,build_util,build_video
edit: build_phase_setup,build_util,build_video,cloth_aero,param_decl,wind_response   # 改cloth_wire须同步核对这些文件
rule: T32 T99 T102 T103
why : IMPROVE_cloth_wire.md
