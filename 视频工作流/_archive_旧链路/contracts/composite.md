[S] composite @ATOM/img  d0  in=6  gen:contract_gen
does: 提供 build_plate, difference_matte, matte_auto, contact_shadow, porter_duff_over, composite_layers
api: build_plate, difference_matte, matte_auto, contact_shadow, porter_duff_over, composite_layers, self_check
const: PLATE_REAL, PLATE_SYNTH
impl: self_check → build_plate → composite_layers → contact_shadow；内部helper 4个
down: _layer_style,_matting,build_util,build_video,chroma,systems_view
edit: _layer_style,_matting,build_util,build_video,chroma,systems_view   # 改composite须同步核对这些文件
why : IMPROVE_composite.md
