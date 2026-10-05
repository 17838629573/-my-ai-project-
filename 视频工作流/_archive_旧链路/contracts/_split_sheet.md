[S] _split_sheet @OPS/tool  d2  in=0  gen:contract_gen
does: 合图切分：网格定序 + 连通域定界（铁律44）
api: split_grid, self_check
const: RAW, OUT, TRIM_BORDER_PX, CLEAN_EDGE_DEPTH, MIN_AREA, KEY_DIST, DARK, PLAN
impl: self_check → split_grid；内部helper 1个
up: chroma
edit: chroma   # 改_split_sheet须同步核对这些文件
rule: T44
why : IMPROVE__split_sheet.md
