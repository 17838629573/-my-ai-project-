[S] run_gen_queue @OPS/demo  d6  in=0  gen:contract_gen
does: Stage 3.5：驱动生图队列，打印代码下发的参数与提示词。
const: U
up: build_phase_gen
edit: build_phase_gen   # 改run_gen_queue须同步核对这些文件
rule: T81 T97
why : IMPROVE_run_gen_queue.md
