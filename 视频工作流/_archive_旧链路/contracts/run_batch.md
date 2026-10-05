[S] run_batch @OPS/demo  d5  in=0  gen:contract_gen
does: run_batch.py —— 分批自检跑批器
api: probe, main
const: BASE, OUT, TIMEOUT, BATCH_SIZE
impl: main → probe
up: enforce
edit: enforce   # 改run_batch须同步核对这些文件
why : IMPROVE_run_batch.md
