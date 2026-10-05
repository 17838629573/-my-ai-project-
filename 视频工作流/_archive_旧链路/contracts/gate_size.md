[S] gate_size @GATE/size  d0  in=0  gen:contract_gen
does: 产物体积门禁：防止媒体产物无上限增长（回归过两次）
api: dir_mb, self_check
const: LIMIT_MB, DUPLICATE_GROUPS
impl: self_check → dir_mb
why : IMPROVE_gate_size.md
