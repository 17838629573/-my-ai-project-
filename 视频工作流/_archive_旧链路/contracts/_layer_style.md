[S] _layer_style @ATOM/img  d1  in=1  gen:contract_gen
does: 分层合成四要素（铁律101）：投影/环境反光/正片叠底/全局色彩平衡
api: contact_shadow, env_reflection, multiply_shade, global_grade, bg_tint_of, over
impl: 入口 _soft；内部helper 1个
up: composite
down: _build32
edit: _build32,composite   # 改_layer_style须同步核对这些文件
rule: T101
why : IMPROVE__layer_style.md
