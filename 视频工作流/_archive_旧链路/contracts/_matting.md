[S] _matting @ATOM/img  d1  in=0  gen:contract_gen
does: 抠图/matting：从 sprite 单格提取软 alpha 前景。
api: auto_trimap, grabcut_alpha, keep_center_component, feather_alpha, matte_cell, split_sheet
impl: 入口 _border_ring；内部helper 1个
up: composite
edit: composite   # 改_matting须同步核对这些文件
rule: T111 T112
why : IMPROVE__matting.md
