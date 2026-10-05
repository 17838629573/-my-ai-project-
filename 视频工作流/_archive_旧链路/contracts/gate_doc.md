[S] gate_doc @GATE/size  d0  in=0  gen:contract_gen
does: 文档体积门禁：防止主干/契约无限膨胀（瘦身成果已回归两次）
api: sz, self_check
const: LIMIT, CONTRACT_LIMIT, CONTRACT_TOTAL
impl: self_check → sz
why : IMPROVE_gate_doc.md
