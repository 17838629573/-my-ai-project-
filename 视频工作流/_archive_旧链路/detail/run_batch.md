[FACT] run_batch   97行   机器生成，勿手改
doc: run_batch.py —— 分批自检跑批器
api:
  L32 probe(mod)
  L60 main()
calls_in: main→probe
calls_out: enforce,json,layer,os,out,r,subprocess,sys,time
guard: return@L34, return@L37, return@L40, return@L61, return@L73
const: BASE, OUT, TIMEOUT=45, BATCH_SIZE=4
main: __main__@L96
up: enforce
down: -
