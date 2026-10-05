[FACT] gate_size   37行   机器生成，勿手改
doc: 产物体积门禁：防止媒体产物无上限增长（回归过两次）
api:
  L14 dir_mb(d)
  L20 self_check()
calls_in: self_check→dir_mb
calls_out: LIMIT_MB,os,r,subprocess
guard: return@L15
const: LIMIT_MB[11], DUPLICATE_GROUPS[1]
main: __main__@L36  self_check@L20
up: -
down: -
