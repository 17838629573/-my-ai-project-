[FACT] gate_doc   49行   机器生成，勿手改
doc: 文档体积门禁：防止主干/契约无限膨胀（瘦身成果已回归两次）
api:
  L13 sz(p)  # 字符数，非字节数。
  L26 self_check()
calls_in: self_check→sz
calls_out: LIMIT,f,glob,os
guard: return@L21
const: LIMIT[4], CONTRACT_LIMIT=4000, CONTRACT_TOTAL=70000
main: __main__@L48  self_check@L26
up: -
down: -
