[S] _build32 @OPS/demo  d2  in=0  gen:contract_gen
does: 提供 key_color_of, key_alpha, prep, sh_of
api: key_color_of, key_alpha, prep, sh_of
const: BATCH, FPS, DUR, SPEED, OUT_W, PX_PER_M, BASE_Y
impl: 入口 _imread；内部helper 1个
up: _layer_style
edit: _layer_style   # 改_build32须同步核对这些文件
why : IMPROVE__build32.md
