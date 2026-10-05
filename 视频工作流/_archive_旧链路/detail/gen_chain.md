[FACT] gen_chain   47行   机器生成，勿手改
doc: 链式参考图生成调度：上一批输出 = 下一批参考图
api:
  L13 frames_for(period_s,fps)  # 一周期应采样帧数(铁律100)
  L18 batches_for(n,per)  # 分批次, 每批 per 格
  L22 chain_prompt(family,obj_desc,frame_ids,pose_desc,keep)  # 组装单批提示词. keep = 必须保持不变的项(画风/服饰/配色)
  L33 self_check()
calls_in: self_check→batches_for, self_check→chain_prompt, self_check→frames_for
calls_out: ck
const: FPS_TARGET=32, CELLS_PER_BATCH=8, DENOISE_BEST[2]
up: -
down: -
