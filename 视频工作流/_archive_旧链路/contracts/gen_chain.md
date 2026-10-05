[S] gen_chain @SOLVE/spec  d0  in=0  gen:contract_gen
does: 链式参考图生成调度：上一批输出 = 下一批参考图
api: frames_for, batches_for, chain_prompt, self_check
const: FPS_TARGET, CELLS_PER_BATCH, DENOISE_BEST
impl: self_check → batches_for → chain_prompt → frames_for
rule: T100
why : IMPROVE_gen_chain.md
